"""Hybrid Search for KOSIS metadata.

Combines BM25 full-text search with vector similarity search using
Reciprocal Rank Fusion (RRF) for optimal results.

Usage:
    searcher = await HybridSearcher.create()
    results = await searcher.search("경제 성장률 추이")

    # With custom weights
    results = await searcher.search(
        "출산율 감소",
        fts_weight=0.3,
        vector_weight=0.7,
    )
"""

import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Single search result."""
    tbl_id: str
    tbl_nm: str
    org_nm: Optional[str]
    org_id: Optional[str]
    rrf_score: float
    fts_rank: int
    vec_rank: int
    period: Optional[str] = None
    contents: Optional[str] = None
    link_url: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "tbl_id": self.tbl_id,
            "tbl_nm": self.tbl_nm,
            "org_nm": self.org_nm,
            "org_id": self.org_id,
            "score": round(self.rrf_score, 4),
            "fts_rank": self.fts_rank,
            "vec_rank": self.vec_rank,
            "period": self.period,
            "contents": self.contents,
            "link_url": self.link_url,
        }


class HybridSearcher:
    """Hybrid search combining FTS and vector similarity.

    Uses RRF (Reciprocal Rank Fusion) to combine rankings from:
    - PostgreSQL full-text search (BM25-like via ts_rank)
    - pgvector cosine similarity search
    """

    def __init__(self, embedder=None):
        """Initialize searcher.

        Args:
            embedder: EmbeddingGenerator instance. If None, will create one.
        """
        self._embedder = embedder
        self._initialized = False

    @classmethod
    async def create(cls, embedder=None) -> "HybridSearcher":
        """Create and initialize a HybridSearcher.

        Args:
            embedder: Optional EmbeddingGenerator instance.

        Returns:
            Initialized HybridSearcher.
        """
        instance = cls(embedder)
        await instance._initialize()
        return instance

    async def _initialize(self):
        """Initialize embedder if needed."""
        if self._initialized:
            return

        if self._embedder is None:
            try:
                from .embeddings import EmbeddingGenerator
                self._embedder = EmbeddingGenerator()
                logger.info("HybridSearcher: Embedder initialized")
            except Exception as e:
                logger.warning(f"HybridSearcher: Failed to initialize embedder: {e}")
                logger.warning("HybridSearcher: Vector search will be disabled")

        self._initialized = True

    async def search(
        self,
        query: str,
        limit: int = 20,
        fts_weight: float = 0.5,
        vector_weight: float = 0.5,
        fts_only: bool = False,
        vector_only: bool = False,
    ) -> List[SearchResult]:
        """Perform hybrid search.

        Args:
            query: Search query (natural language).
            limit: Maximum number of results.
            fts_weight: Weight for FTS results in RRF (0-1).
            vector_weight: Weight for vector results in RRF (0-1).
            fts_only: Use only full-text search.
            vector_only: Use only vector search.

        Returns:
            List of SearchResult objects sorted by relevance.
        """
        from .database import DatabasePool

        if not self._initialized:
            await self._initialize()

        # Validate weights
        if fts_weight + vector_weight == 0:
            raise ValueError("At least one weight must be > 0")

        # Decide search mode
        use_fts = not vector_only and fts_weight > 0
        use_vector = not fts_only and vector_weight > 0 and self._embedder is not None

        if not use_fts and not use_vector:
            logger.warning("No search method available")
            return []

        # Generate query embedding if needed
        query_embedding = None
        if use_vector:
            try:
                query_embedding = self._embedder.create_embedding(query)
            except Exception as e:
                logger.warning(f"Failed to create query embedding: {e}")
                use_vector = False

        # Build and execute query
        if use_fts and use_vector:
            results = await self._hybrid_search(
                query, query_embedding, limit, fts_weight, vector_weight
            )
        elif use_fts:
            results = await self._fts_search(query, limit)
        else:
            results = await self._vector_search(query_embedding, limit)

        return results

    async def _hybrid_search(
        self,
        query: str,
        embedding: List[float],
        limit: int,
        fts_weight: float,
        vector_weight: float,
    ) -> List[SearchResult]:
        """Execute hybrid search with RRF combination."""
        from .database import DatabasePool

        # RRF constant (standard value)
        k = 60

        # Convert embedding list to pgvector string format
        embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

        sql = """
        WITH
        -- Full-text search results
        fts_results AS (
            SELECT
                tbl_id,
                ROW_NUMBER() OVER (
                    ORDER BY ts_rank(search_vector, plainto_tsquery('simple', $1)) DESC
                ) AS fts_rank
            FROM kosis_tables
            WHERE search_vector @@ plainto_tsquery('simple', $1)
            LIMIT 100
        ),
        -- Vector similarity results
        vector_results AS (
            SELECT
                tbl_id,
                ROW_NUMBER() OVER (
                    ORDER BY embedding <=> $2::vector
                ) AS vec_rank
            FROM kosis_tables
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $2::vector
            LIMIT 100
        ),
        -- RRF combination
        combined AS (
            SELECT
                COALESCE(f.tbl_id, v.tbl_id) AS tbl_id,
                f.fts_rank,
                v.vec_rank,
                COALESCE($3::float / ($5 + f.fts_rank), 0) +
                COALESCE($4::float / ($5 + v.vec_rank), 0) AS rrf_score
            FROM fts_results f
            FULL OUTER JOIN vector_results v ON f.tbl_id = v.tbl_id
        )
        -- Join with main table for metadata
        SELECT
            c.tbl_id,
            t.tbl_nm,
            t.org_nm,
            t.org_id,
            c.rrf_score,
            COALESCE(c.fts_rank, 0) AS fts_rank,
            COALESCE(c.vec_rank, 0) AS vec_rank,
            t.strt_prd_de,
            t.end_prd_de,
            t.contents,
            t.link_url
        FROM combined c
        JOIN kosis_tables t ON c.tbl_id = t.tbl_id
        ORDER BY c.rrf_score DESC
        LIMIT $6
        """

        rows = await DatabasePool.fetch(
            sql, query, embedding_str, fts_weight, vector_weight, k, limit
        )

        return [
            SearchResult(
                tbl_id=row["tbl_id"],
                tbl_nm=row["tbl_nm"],
                org_nm=row["org_nm"],
                org_id=row["org_id"],
                rrf_score=float(row["rrf_score"]),
                fts_rank=row["fts_rank"],
                vec_rank=row["vec_rank"],
                period=f"{row['strt_prd_de'] or ''} ~ {row['end_prd_de'] or ''}".strip(" ~"),
                contents=row["contents"],
                link_url=row["link_url"],
            )
            for row in rows
        ]

    async def _fts_search(self, query: str, limit: int) -> List[SearchResult]:
        """Execute full-text search only."""
        from .database import DatabasePool

        sql = """
        SELECT
            tbl_id,
            tbl_nm,
            org_nm,
            org_id,
            ts_rank(search_vector, plainto_tsquery('simple', $1)) AS score,
            strt_prd_de,
            end_prd_de,
            contents,
            link_url
        FROM kosis_tables
        WHERE search_vector @@ plainto_tsquery('simple', $1)
        ORDER BY score DESC
        LIMIT $2
        """

        rows = await DatabasePool.fetch(sql, query, limit)

        return [
            SearchResult(
                tbl_id=row["tbl_id"],
                tbl_nm=row["tbl_nm"],
                org_nm=row["org_nm"],
                org_id=row["org_id"],
                rrf_score=float(row["score"]),
                fts_rank=i + 1,
                vec_rank=0,
                period=f"{row['strt_prd_de'] or ''} ~ {row['end_prd_de'] or ''}".strip(" ~"),
                contents=row["contents"],
                link_url=row["link_url"],
            )
            for i, row in enumerate(rows)
        ]

    async def _vector_search(
        self, embedding: List[float], limit: int
    ) -> List[SearchResult]:
        """Execute vector similarity search only."""
        from .database import DatabasePool

        # Convert embedding list to pgvector string format
        embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

        sql = """
        SELECT
            tbl_id,
            tbl_nm,
            org_nm,
            org_id,
            1 - (embedding <=> $1::vector) AS score,
            strt_prd_de,
            end_prd_de,
            contents,
            link_url
        FROM kosis_tables
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> $1::vector
        LIMIT $2
        """

        rows = await DatabasePool.fetch(sql, embedding_str, limit)

        return [
            SearchResult(
                tbl_id=row["tbl_id"],
                tbl_nm=row["tbl_nm"],
                org_nm=row["org_nm"],
                org_id=row["org_id"],
                rrf_score=float(row["score"]),
                fts_rank=0,
                vec_rank=i + 1,
                period=f"{row['strt_prd_de'] or ''} ~ {row['end_prd_de'] or ''}".strip(" ~"),
                contents=row["contents"],
                link_url=row["link_url"],
            )
            for i, row in enumerate(rows)
        ]

    async def search_similar(
        self,
        tbl_id: str,
        limit: int = 10,
    ) -> List[SearchResult]:
        """Find tables similar to a given table.

        Args:
            tbl_id: Source table ID.
            limit: Maximum number of results.

        Returns:
            List of similar tables.
        """
        from .database import DatabasePool

        # Get embedding of source table
        source = await DatabasePool.fetchrow(
            "SELECT embedding FROM kosis_tables WHERE tbl_id = $1", tbl_id
        )

        if not source or not source["embedding"]:
            logger.warning(f"Table {tbl_id} not found or has no embedding")
            return []

        # Find similar by vector
        sql = """
        SELECT
            tbl_id,
            tbl_nm,
            org_nm,
            org_id,
            1 - (embedding <=> $1::vector) AS score,
            strt_prd_de,
            end_prd_de,
            contents,
            link_url
        FROM kosis_tables
        WHERE tbl_id != $2
          AND embedding IS NOT NULL
        ORDER BY embedding <=> $1::vector
        LIMIT $3
        """

        rows = await DatabasePool.fetch(sql, source["embedding"], tbl_id, limit)

        return [
            SearchResult(
                tbl_id=row["tbl_id"],
                tbl_nm=row["tbl_nm"],
                org_nm=row["org_nm"],
                org_id=row["org_id"],
                rrf_score=float(row["score"]),
                fts_rank=0,
                vec_rank=i + 1,
                period=f"{row['strt_prd_de'] or ''} ~ {row['end_prd_de'] or ''}".strip(" ~"),
                contents=row["contents"],
                link_url=row["link_url"],
            )
            for i, row in enumerate(rows)
        ]


# Singleton instance for reuse
_searcher_instance: Optional[HybridSearcher] = None


async def get_searcher() -> HybridSearcher:
    """Get or create the global HybridSearcher instance."""
    global _searcher_instance
    if _searcher_instance is None:
        _searcher_instance = await HybridSearcher.create()
    return _searcher_instance


async def search_tables(
    query: str,
    limit: int = 20,
    fts_weight: float = 0.5,
    vector_weight: float = 0.5,
) -> List[Dict[str, Any]]:
    """Convenience function for hybrid search.

    Args:
        query: Search query.
        limit: Max results.
        fts_weight: FTS weight (0-1).
        vector_weight: Vector weight (0-1).

    Returns:
        List of result dicts.
    """
    searcher = await get_searcher()
    results = await searcher.search(
        query,
        limit=limit,
        fts_weight=fts_weight,
        vector_weight=vector_weight,
    )
    return [r.to_dict() for r in results]
