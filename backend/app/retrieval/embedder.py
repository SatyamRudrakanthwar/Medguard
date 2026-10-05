"""
Singleton sentence-transformer embedder.
Uses all-MiniLM-L6-v2: 384 dimensions, ~80MB, fast and accurate for medical text.
Loaded once at startup and reused across all requests.
"""
import logging
from functools import lru_cache
import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


@lru_cache(maxsize=1)
def get_embedder():
    """Load the embedding model once and cache it."""
    logger.info("Loading embedding model: %s", EMBEDDING_MODEL)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBEDDING_MODEL)
    logger.info("Embedding model loaded (dim=%d)", EMBEDDING_DIM)
    return model


def embed_text(text: str) -> list[float]:
    """Embed a single text string. Returns a list of floats."""
    model = get_embedder()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_batch(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Embed multiple texts efficiently."""
    model = get_embedder()
    vectors = model.encode(texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]
