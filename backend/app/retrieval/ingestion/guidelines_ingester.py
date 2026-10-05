"""
Guidelines ingester — embeds the curated safety guidelines into Qdrant.
This is always the first thing ingested as it requires no external API.
"""
import logging
from app.mcp.tools.guideline_search import CURATED_GUIDELINES
from app.retrieval.document_processor import process_guideline
from app.retrieval.qdrant_store import upsert_documents

logger = logging.getLogger(__name__)


async def ingest_guidelines() -> int:
    """Embed and store all curated safety guidelines. Returns count stored."""
    documents = []
    for guideline in CURATED_GUIDELINES:
        documents.extend(process_guideline(guideline))

    if not documents:
        return 0

    count = await upsert_documents(documents)
    logger.info("Ingested %d guideline chunks", count)
    return count
