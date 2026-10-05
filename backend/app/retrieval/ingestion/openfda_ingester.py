"""
OpenFDA ingester — fetches drug labels and embeds them into Qdrant.
Processes one drug at a time to stay within free API rate limits.
"""
import asyncio
import logging
from app.services.openfda_client import OpenFDAClient
from app.services.rxnorm_client import RxNormClient
from app.retrieval.document_processor import process_openfda_label
from app.retrieval.qdrant_store import upsert_documents

logger = logging.getLogger(__name__)

_openfda = OpenFDAClient()
_rxnorm = RxNormClient()

# Seed list — common medications that appear in demos and interactions
SEED_DRUGS = [
    "aspirin", "warfarin", "metformin", "lisinopril", "atorvastatin",
    "amlodipine", "omeprazole", "metoprolol", "levothyroxine", "clopidogrel",
    "ibuprofen", "acetaminophen", "sertraline", "fluoxetine", "simvastatin",
    "losartan", "gabapentin", "furosemide", "prednisone", "amoxicillin",
    "ciprofloxacin", "diazepam", "alprazolam", "naproxen", "enalapril",
]


async def ingest_openfda_labels(drug_names: list[str] | None = None) -> int:
    """
    Fetch and embed OpenFDA drug labels.
    Uses SEED_DRUGS if no list provided.
    Returns total chunk count stored.
    """
    targets = drug_names or SEED_DRUGS
    total = 0

    for drug in targets:
        try:
            # Normalize first
            norm = await _rxnorm.normalize(drug)
            normalized = norm["normalized_name"].lower()

            # Fetch label
            label = await _openfda.get_drug_label(normalized)
            if not label:
                label = await _openfda.get_drug_label(drug.lower())
            if not label:
                logger.warning("No label found for: %s", drug)
                continue

            # Process into chunks
            docs = process_openfda_label(label, normalized)
            if docs:
                stored = await upsert_documents(docs)
                total += stored
                logger.info("Ingested %s: %d chunks", drug, stored)

            # Be polite to the free API
            await asyncio.sleep(0.3)

        except Exception as e:
            logger.error("OpenFDA ingestion error for %s: %s", drug, e)

    return total
