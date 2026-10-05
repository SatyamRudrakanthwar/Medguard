"""
MedGuard semantic retriever — searches Qdrant for relevant evidence.

Two modes:
  semantic_search(query)           — pure vector similarity
  drug_filtered_search(query, drugs) — vector search scoped to specific drug names
"""
import logging
from typing import Optional

from qdrant_client.models import Filter, FieldCondition, MatchAny, ScoredPoint

from app.retrieval.embedder import embed_text
from app.retrieval.qdrant_store import get_async_client, _collection_name, collection_count
from app.models.findings import EvidenceSource

logger = logging.getLogger(__name__)

_qdrant_ready: Optional[bool] = None  # cached after first check


async def is_qdrant_ready() -> bool:
    """Returns True if Qdrant is running and the collection has documents."""
    global _qdrant_ready
    if _qdrant_ready is not None:
        return _qdrant_ready
    try:
        count = await collection_count()
        _qdrant_ready = count > 0
        if _qdrant_ready:
            logger.info("Qdrant ready: %d documents in collection", count)
        else:
            logger.info("Qdrant collection empty — falling back to live PubMed")
    except Exception as e:
        logger.warning("Qdrant not available: %s", e)
        _qdrant_ready = False
    return _qdrant_ready


def reset_qdrant_ready_cache() -> None:
    """Call this after ingestion to re-check Qdrant state."""
    global _qdrant_ready
    _qdrant_ready = None


async def semantic_search(
    query: str,
    top_k: int = 5,
    score_threshold: float = 0.35,
) -> list[EvidenceSource]:
    """Pure semantic search — best for open-ended queries."""
    return await _search(query, top_k, score_threshold, drug_filter=None)


async def drug_filtered_search(
    query: str,
    drug_names: list[str],
    top_k: int = 5,
    score_threshold: float = 0.30,
) -> list[EvidenceSource]:
    """
    Semantic search filtered to documents mentioning specific drug names.
    Falls back to unfiltered search if filtered results are too few.
    """
    drug_names_lower = [d.lower() for d in drug_names]
    drug_filter = Filter(
        must=[
            FieldCondition(
                key="drug_names",
                match=MatchAny(any=drug_names_lower),
            )
        ]
    )

    results = await _search(query, top_k, score_threshold, drug_filter=drug_filter)

    # If we got fewer than 2 results with the filter, fall back to unfiltered
    if len(results) < 2:
        logger.info("Drug-filtered search returned %d results — falling back to unfiltered", len(results))
        unfiltered = await _search(query, top_k, score_threshold, drug_filter=None)
        # Merge, prioritise filtered results
        seen_ids = {e.source_id for e in results}
        for item in unfiltered:
            if item.source_id not in seen_ids:
                results.append(item)
                seen_ids.add(item.source_id)
        results = results[:top_k]

    return results


async def _search(
    query: str,
    top_k: int,
    score_threshold: float,
    drug_filter: Optional[Filter],
) -> list[EvidenceSource]:
    query_vector = embed_text(query)
    name = _collection_name()

    try:
        client = await get_async_client()
        hits: list[ScoredPoint] = await client.search(
            collection_name=name,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=drug_filter,
            with_payload=True,
        )
        await client.close()
    except Exception as e:
        logger.error("Qdrant search error: %s", e)
        return []

    results = []
    for hit in hits:
        payload = hit.payload or {}
        results.append(EvidenceSource(
            source=payload.get("source", "Knowledge Base"),
            source_id=payload.get("source_id", str(hit.id)),
            url=payload.get("url"),
            support_score=round(float(hit.score), 3),
            excerpt=payload.get("text", "")[:400],
        ))

    logger.debug("Qdrant search '%s' → %d results", query[:60], len(results))
    return results
