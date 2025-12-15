"""OpenAI Embedding Generator for KOSIS metadata.

Generates embeddings using text-embedding-3-small model for semantic search.
Supports batch processing with rate limiting.

Usage:
    embedder = EmbeddingGenerator()
    embedding = embedder.create_embedding("출산율 통계")
    embeddings = embedder.create_embeddings_batch(["text1", "text2", ...])
"""

import os
import time
import logging
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Optional import - handle missing openai gracefully
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation."""
    model: str = "text-embedding-3-small"
    dimensions: int = 1536  # Default for text-embedding-3-small
    max_tokens: int = 8191  # Model limit
    batch_size: int = 100   # API allows up to 2048, but 100 is safer
    max_text_length: int = 15000  # Approx chars (~5000 tokens for Korean)
    retry_attempts: int = 3
    retry_delay: float = 1.0  # seconds


class EmbeddingError(Exception):
    """Embedding generation error."""
    pass


class EmbeddingGenerator:
    """OpenAI embedding generator with batching and retry support.

    Attributes:
        config: EmbeddingConfig with model parameters.
        client: OpenAI client instance.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[EmbeddingConfig] = None,
    ):
        """Initialize embedding generator.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env.
            config: Optional configuration. Uses defaults if None.

        Raises:
            EmbeddingError: If openai package not installed or API key missing.
        """
        if not OPENAI_AVAILABLE:
            raise EmbeddingError(
                "openai package not installed. Install with: uv add openai"
            )

        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise EmbeddingError(
                "OpenAI API key not provided and OPENAI_API_KEY not in environment"
            )

        self.config = config or EmbeddingConfig()
        self.client = openai.OpenAI(api_key=key)
        self._request_count = 0
        self._total_tokens = 0

        logger.info(
            f"EmbeddingGenerator initialized: model={self.config.model}, "
            f"dimensions={self.config.dimensions}"
        )

    def _truncate_text(self, text: str) -> str:
        """Truncate text to max length."""
        if len(text) > self.config.max_text_length:
            truncated = text[:self.config.max_text_length]
            logger.debug(f"Truncated text from {len(text)} to {len(truncated)} chars")
            return truncated
        return text

    def create_embedding(self, text: str) -> List[float]:
        """Create embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            List of floats representing the embedding vector.

        Raises:
            EmbeddingError: If API call fails after retries.
        """
        text = self._truncate_text(text.strip())
        if not text:
            raise EmbeddingError("Cannot create embedding for empty text")

        for attempt in range(self.config.retry_attempts):
            try:
                response = self.client.embeddings.create(
                    model=self.config.model,
                    input=text,
                    dimensions=self.config.dimensions,
                )

                self._request_count += 1
                self._total_tokens += response.usage.total_tokens

                return response.data[0].embedding

            except openai.RateLimitError as e:
                if attempt < self.config.retry_attempts - 1:
                    wait_time = self.config.retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limit hit, waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise EmbeddingError(f"Rate limit exceeded: {e}") from e

            except openai.APIError as e:
                if attempt < self.config.retry_attempts - 1:
                    logger.warning(f"API error (attempt {attempt + 1}): {e}")
                    time.sleep(self.config.retry_delay)
                else:
                    raise EmbeddingError(f"API error after {attempt + 1} attempts: {e}") from e

    def create_embeddings_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
        progress_callback: Optional[callable] = None,
    ) -> List[List[float]]:
        """Create embeddings for multiple texts in batches.

        Args:
            texts: List of texts to embed.
            batch_size: Override default batch size.
            progress_callback: Optional callback(processed, total) for progress.

        Returns:
            List of embedding vectors in same order as input texts.

        Raises:
            EmbeddingError: If API call fails.
        """
        if not texts:
            return []

        batch_size = batch_size or self.config.batch_size
        embeddings = []
        total = len(texts)

        # Preprocess texts
        processed_texts = [self._truncate_text(t.strip()) for t in texts]

        for i in range(0, total, batch_size):
            batch = processed_texts[i:i + batch_size]

            # Skip empty texts in batch
            valid_indices = [j for j, t in enumerate(batch) if t]
            valid_texts = [batch[j] for j in valid_indices]

            if not valid_texts:
                # All texts in batch are empty, fill with zero vectors
                embeddings.extend([[0.0] * self.config.dimensions] * len(batch))
                continue

            for attempt in range(self.config.retry_attempts):
                try:
                    response = self.client.embeddings.create(
                        model=self.config.model,
                        input=valid_texts,
                        dimensions=self.config.dimensions,
                    )

                    self._request_count += 1
                    self._total_tokens += response.usage.total_tokens

                    # Map results back to original positions
                    batch_embeddings = [[0.0] * self.config.dimensions] * len(batch)
                    for idx, emb_data in zip(valid_indices, response.data):
                        batch_embeddings[idx] = emb_data.embedding

                    embeddings.extend(batch_embeddings)
                    break

                except openai.RateLimitError as e:
                    if attempt < self.config.retry_attempts - 1:
                        wait_time = self.config.retry_delay * (2 ** attempt)
                        logger.warning(f"Rate limit hit, waiting {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        raise EmbeddingError(f"Rate limit exceeded: {e}") from e

                except openai.APIError as e:
                    if attempt < self.config.retry_attempts - 1:
                        logger.warning(f"API error (attempt {attempt + 1}): {e}")
                        time.sleep(self.config.retry_delay)
                    else:
                        raise EmbeddingError(f"API error: {e}") from e

            # Progress callback
            if progress_callback:
                progress_callback(min(i + batch_size, total), total)

            # Small delay between batches to avoid rate limits
            if i + batch_size < total:
                time.sleep(0.1)

        return embeddings

    def get_stats(self) -> dict:
        """Get usage statistics.

        Returns:
            Dict with request count and total tokens used.
        """
        return {
            "requests": self._request_count,
            "total_tokens": self._total_tokens,
            "estimated_cost_usd": self._total_tokens * 0.00002 / 1000,  # $0.02/1M tokens
        }


def create_search_text(record: dict) -> str:
    """Create combined search text from metadata record.

    Combines relevant fields for embedding:
    - TBL_NM (table name) - highest priority
    - ORG_NM (organization name)
    - CONTENTS (description)
    - ITEM03 (additional info)
    - MT_ATITLE (category path)

    Args:
        record: Metadata record dict with KOSIS fields.

    Returns:
        Combined text string for embedding.
    """
    # Priority order for combining text
    fields = [
        ("TBL_NM", 1.0),     # Table name - most important
        ("ORG_NM", 0.5),     # Organization
        ("CONTENTS", 0.8),  # Description
        ("ITEM03", 0.3),    # Additional info
        ("MT_ATITLE", 0.2), # Category path
    ]

    parts = []
    for field, _ in fields:
        value = record.get(field, "") or ""
        value = value.strip()
        if value:
            parts.append(value)

    # Join with spaces, limit to reasonable length
    text = " ".join(parts)

    # Limit to ~15000 chars (safe for tokenization)
    return text[:15000] if len(text) > 15000 else text


# Utility function for quick embedding check
def test_embedding_connection() -> dict:
    """Test OpenAI API connection and embedding generation.

    Returns:
        Dict with status and sample embedding info.
    """
    try:
        embedder = EmbeddingGenerator()
        test_text = "테스트 텍스트"
        embedding = embedder.create_embedding(test_text)

        return {
            "status": "success",
            "model": embedder.config.model,
            "dimensions": len(embedding),
            "sample_values": embedding[:5],
            "stats": embedder.get_stats(),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }
