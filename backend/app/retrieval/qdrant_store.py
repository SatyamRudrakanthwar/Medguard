"""
Qdrant connection and collection management.
Collection schema:
  vector: 384-dim float (all-MiniLM-L6-v2)
  payload:
    text         – the chunk text (used as excerpt in EvidenceSource)
    source       – OpenFDA | PubMed | Guideline
    document_type – drug_label | abstract | guideline
    drug_names   – list[str] normalized drug names in the document
    title        – document/section title
    url          – link to original source (optional)
    source_id    – PMID, NDC, etc. (optional)
"""
import logging
from functools import lru_cache

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchAny,
    CollectionStatus,
)

from app.config.settings import get_settings
from app.retrieval.embedder import EMBEDDING_DIM

logger = logging.getLogger(__name__)

COLLECTION = None  # resolved from settings at runtime


def _collection_name() -> str:
    return get_settings().qdrant_collection_name


@lru_cache(maxsize=1)
def _get_sync_client():
    from qdrant_client import QdrantClient
    s = get_settings()
    return QdrantClient(host=s.qdrant_host, port=s.qdrant_port, timeout=10)


async def get_async_client() -> AsyncQdrantClient:
    s = get_settings()
    return AsyncQdrantClient(host=s.qdrant_host, port=s.qdrant_port, timeout=10)


async def ensure_collection() -> bool:
    """
    Create the Qdrant collection if it doesn't exist.
    Returns True if ready, False if Qdrant is unavailable.
    """
    name = _collection_name()
    try:
        client = await get_async_client()
        existing = await client.get_collections()
        names = [c.name for c in existing.collections]
        if name not in names:
            await client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
            )
            logger.info("Created Qdrant collection: %s", name)
        else:
            logger.info("Qdrant collection exists: %s", name)
        await client.close()
        return True
    except Exception as e:
        logger.warning("Qdrant unavailable: %s", e)
        return False


async def upsert_documents(documents: list[dict]) -> int:
    """
    Embed and upsert a list of documents into Qdrant.
    Each document must have: id (str), text (str), payload (dict).
    Returns count of upserted points.
    """
    if not documents:
        return 0

    from app.retrieval.embedder import embed_batch
    import uuid

    texts = [d["text"] for d in documents]
    vectors = embed_batch(texts)

    points = [
        PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_DNS, d["id"])),
            vector=vectors[i],
            payload={**d.get("payload", {}), "text": d["text"]},
        )
        for i, d in enumerate(documents)
    ]

    name = _collection_name()
    try:
        client = await get_async_client()
        await client.upsert(collection_name=name, points=points, wait=True)
        await client.close()
        logger.info("Upserted %d documents into %s", len(points), name)
        return len(points)
    except Exception as e:
        logger.error("Qdrant upsert error: %s", e)
        return 0


async def collection_count() -> int:
    name = _collection_name()
    try:
        client = await get_async_client()
        info = await client.get_collection(name)
        count = info.points_count or 0
        await client.close()
        return count
    except Exception:
        return 0
