#!/usr/bin/env python3
"""Load KOSIS metadata into PostgreSQL with embeddings.

This script loads the kosis_metadata_final.json file into the database
and generates OpenAI embeddings for semantic search.

Features:
- Robust: Supports resume after interruption
- Incremental: Only generates embeddings for records without them
- Batch processing with retry logic for API failures

Usage:
    # Full load with embeddings (requires OPENAI_API_KEY)
    uv run python scripts/load_metadata.py

    # Resume mode: skip records with existing embeddings
    uv run python scripts/load_metadata.py --resume

    # Load without embeddings (faster, for testing)
    uv run python scripts/load_metadata.py --skip-embeddings

    # Force re-generate all embeddings
    uv run python scripts/load_metadata.py --force

    # Load specific number of records (for testing)
    uv run python scripts/load_metadata.py --limit 1000

Environment Variables:
    DATABASE_URL: PostgreSQL connection URL
    OPENAI_API_KEY: OpenAI API key (required for embeddings)
"""

import os
import sys
import json
import asyncio
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Load KOSIS metadata into PostgreSQL")
    parser.add_argument(
        "--json-path",
        default="data/metadata_api/tables.json",
        help="Path to metadata JSON file (default: tables.json with 252K tables)",
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip embedding generation (faster, for testing)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume mode: skip records that already have embeddings",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-generate embeddings for all records",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of records to load (for testing)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size for database inserts",
    )
    parser.add_argument(
        "--embedding-batch-size",
        type=int,
        default=100,
        help="Batch size for OpenAI API calls",
    )
    parser.add_argument(
        "--create-indexes",
        action="store_true",
        help="Create indexes after loading (recommended)",
    )
    parser.add_argument(
        "--retry-count",
        type=int,
        default=3,
        help="Number of retries for API failures (default: 3)",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=5.0,
        help="Delay between retries in seconds (default: 5.0)",
    )
    return parser.parse_args()


def create_search_text(record: dict) -> str:
    """Create combined search text from metadata record.

    Supports both uppercase (legacy) and lowercase (new) field names.
    """
    parts = []
    # Support both uppercase and lowercase field names
    fields = [
        ("tbl_nm", "TBL_NM"),
        ("org_nm", "ORG_NM"),
        ("contents", "CONTENTS"),
        ("item03", "ITEM03"),
        ("mt_atitle", "MT_ATITLE"),
        ("stats_nm", None),  # new field: 통계명
        ("writing_purps", None),  # new field: 조사목적
    ]
    for lower, upper in fields:
        value = record.get(lower) or (record.get(upper) if upper else None) or ""
        value = str(value).strip()
        if value:
            parts.append(value)

    text = " ".join(parts)
    return text[:15000] if len(text) > 15000 else text


async def get_existing_tbl_ids_with_embeddings() -> set:
    """Get set of tbl_ids that already have embeddings."""
    from kosis_tools.database import DatabasePool

    rows = await DatabasePool.fetch(
        "SELECT tbl_id FROM kosis_tables WHERE embedding IS NOT NULL"
    )
    return {row["tbl_id"] for row in rows}


async def load_metadata(
    json_path: str,
    skip_embeddings: bool = False,
    resume: bool = False,
    force: bool = False,
    limit: Optional[int] = None,
    batch_size: int = 500,
    embedding_batch_size: int = 100,
    create_indexes: bool = False,
    retry_count: int = 3,
    retry_delay: float = 5.0,
):
    """Load metadata into database.

    Args:
        json_path: Path to metadata JSON file
        skip_embeddings: Skip embedding generation entirely
        resume: Skip records that already have embeddings (incremental update)
        force: Force re-generate embeddings for all records
        limit: Limit number of records to process
        batch_size: Batch size for database inserts
        embedding_batch_size: Batch size for OpenAI API calls
        create_indexes: Create indexes after loading
        retry_count: Number of retries for API failures
        retry_delay: Delay between retries in seconds
    """
    import time
    from kosis_tools.database import DatabasePool, DatabaseError

    # Load JSON file
    json_file = Path(json_path)
    if not json_file.exists():
        logger.error(f"JSON file not found: {json_path}")
        sys.exit(1)

    logger.info(f"Loading JSON from {json_path}...")
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Support both formats:
    # - New format: {"tables": [...], "metadata": {...}}
    # - Legacy format: [...]
    if isinstance(data, dict) and "tables" in data:
        records = data["tables"]
        if "metadata" in data:
            logger.info(f"Metadata version: {data['metadata'].get('version', 'unknown')}")
    else:
        records = data

    total_records = len(records)
    if limit:
        records = records[:limit]

    logger.info(f"Total records in file: {total_records:,}")
    logger.info(f"Records to process: {len(records):,}")

    # Resume mode: filter out records that already have embeddings
    existing_with_embeddings = set()
    if resume and not skip_embeddings and not force:
        try:
            await DatabasePool.initialize()
            existing_with_embeddings = await get_existing_tbl_ids_with_embeddings()
            logger.info(f"Found {len(existing_with_embeddings):,} records with existing embeddings")

            # Helper to get tbl_id from record
            def get_tbl_id(rec):
                return rec.get("tbl_id") or rec.get("TBL_ID")

            original_count = len(records)
            records = [r for r in records if get_tbl_id(r) not in existing_with_embeddings]
            skipped = original_count - len(records)
            logger.info(f"Resume mode: skipping {skipped:,} records, processing {len(records):,}")
            await DatabasePool.close()
        except Exception as e:
            logger.warning(f"Could not get existing embeddings: {e}")
            logger.info("Proceeding with all records")

    # Initialize database
    try:
        await DatabasePool.initialize()
        logger.info("Database connection established")
    except DatabaseError as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)

    # Initialize embedder if needed
    embedder = None
    if not skip_embeddings:
        try:
            from kosis_tools.embeddings import EmbeddingGenerator
            embedder = EmbeddingGenerator()
            logger.info("Embedding generator initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize embedder: {e}")
            logger.warning("Proceeding without embeddings")
            skip_embeddings = True

    # Log start
    start_time = datetime.now()
    await DatabasePool.execute(
        """
        INSERT INTO data_load_logs (load_type, records_processed, started_at)
        VALUES ($1, $2, $3)
        """,
        "metadata_full" if not skip_embeddings else "metadata_no_embeddings",
        len(records),
        start_time,
    )

    # Process in batches
    success_count = 0
    error_count = 0

    for batch_start in range(0, len(records), batch_size):
        batch_end = min(batch_start + batch_size, len(records))
        batch = records[batch_start:batch_end]

        # Prepare search texts
        search_texts = [create_search_text(r) for r in batch]

        # Generate embeddings if enabled (with retry logic)
        embeddings = None
        if embedder and not skip_embeddings:
            for attempt in range(retry_count):
                try:
                    def progress_cb(done, total):
                        pass  # Silent progress

                    embeddings = embedder.create_embeddings_batch(
                        search_texts,
                        batch_size=embedding_batch_size,
                        progress_callback=progress_cb,
                    )
                    break  # Success, exit retry loop
                except Exception as e:
                    if attempt < retry_count - 1:
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(
                            f"Embedding API failed (attempt {attempt + 1}/{retry_count}): {e}"
                        )
                        logger.info(f"Retrying in {wait_time:.1f}s...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Embedding generation failed after {retry_count} attempts: {e}")
                        embeddings = None

        # Helper to get field value (supports both lowercase and uppercase)
        def get_field(rec, lower_key, upper_key=None):
            upper_key = upper_key or lower_key.upper()
            return rec.get(lower_key) or rec.get(upper_key)

        # Insert batch
        try:
            async with DatabasePool.connection() as conn:
                for i, record in enumerate(batch):
                    try:
                        embedding = embeddings[i] if embeddings else None

                        await conn.execute(
                            """
                            INSERT INTO kosis_tables (
                                tbl_id, org_id, stat_id, tbl_nm, org_nm, stat_nm,
                                mt_atitle, contents, item03, strt_prd_de, end_prd_de,
                                link_url, search_text, embedding
                            ) VALUES (
                                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
                            )
                            ON CONFLICT (tbl_id) DO UPDATE SET
                                search_text = EXCLUDED.search_text,
                                embedding = EXCLUDED.embedding,
                                updated_at = NOW()
                            """,
                            get_field(record, "tbl_id"),
                            get_field(record, "org_id"),
                            get_field(record, "stat_id"),
                            get_field(record, "tbl_nm"),
                            get_field(record, "org_nm"),
                            get_field(record, "stat_nm", "STAT_NM") or get_field(record, "stats_nm"),
                            get_field(record, "mt_atitle"),
                            get_field(record, "contents"),
                            get_field(record, "item03"),
                            get_field(record, "strt_prd_de"),
                            get_field(record, "end_prd_de"),
                            get_field(record, "link_url") or get_field(record, "tbl_view_url"),
                            search_texts[i],
                            embedding,
                        )
                        success_count += 1
                    except Exception as e:
                        tbl_id = get_field(record, "tbl_id")
                        logger.debug(f"Failed to insert {tbl_id}: {e}")
                        error_count += 1

        except Exception as e:
            logger.error(f"Batch insert failed: {e}")
            error_count += len(batch)

        # Progress report
        progress = (batch_end / len(records)) * 100
        logger.info(
            f"Progress: {batch_end:,}/{len(records):,} ({progress:.1f}%) "
            f"- Success: {success_count:,}, Errors: {error_count:,}"
        )

    # Create indexes if requested
    if create_indexes:
        logger.info("Creating indexes (this may take a while)...")
        try:
            async with DatabasePool.connection() as conn:
                # GIN index for full-text search
                logger.info("Creating GIN index for search_vector...")
                await conn.execute(
                    """
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_kosis_search_vector
                    ON kosis_tables USING GIN (search_vector)
                    """
                )

                # HNSW index for vector search (only if embeddings exist)
                if not skip_embeddings:
                    logger.info("Creating HNSW index for embeddings...")
                    await conn.execute(
                        """
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_kosis_embedding
                        ON kosis_tables USING hnsw (embedding vector_cosine_ops)
                        WITH (m = 16, ef_construction = 64)
                        """
                    )
            logger.info("Indexes created successfully")
        except Exception as e:
            logger.warning(f"Index creation failed: {e}")

    # Log completion
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    await DatabasePool.execute(
        """
        UPDATE data_load_logs
        SET records_success = $1, records_failed = $2,
            completed_at = $3, duration_seconds = $4
        WHERE load_type = $5 AND started_at = $6
        """,
        success_count,
        error_count,
        end_time,
        duration,
        "metadata_full" if not skip_embeddings else "metadata_no_embeddings",
        start_time,
    )

    # Summary
    logger.info("=" * 50)
    logger.info("LOAD COMPLETE")
    logger.info(f"  Total processed: {len(records):,}")
    logger.info(f"  Success: {success_count:,}")
    logger.info(f"  Errors: {error_count:,}")
    logger.info(f"  Duration: {duration:.1f} seconds")
    logger.info(f"  Embeddings: {'Generated' if not skip_embeddings else 'Skipped'}")
    if embedder:
        stats = embedder.get_stats()
        logger.info(f"  API calls: {stats['requests']}")
        logger.info(f"  Total tokens: {stats['total_tokens']:,}")
        logger.info(f"  Estimated cost: ${stats['estimated_cost_usd']:.4f}")
    logger.info("=" * 50)

    await DatabasePool.close()


if __name__ == "__main__":
    args = parse_args()

    asyncio.run(
        load_metadata(
            json_path=args.json_path,
            skip_embeddings=args.skip_embeddings,
            resume=args.resume,
            force=args.force,
            limit=args.limit,
            batch_size=args.batch_size,
            embedding_batch_size=args.embedding_batch_size,
            create_indexes=args.create_indexes,
            retry_count=args.retry_count,
            retry_delay=args.retry_delay,
        )
    )
