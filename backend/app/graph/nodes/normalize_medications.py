"""
Node: normalize_medications
Converts raw user-entered drug names to normalized RxNorm names.
"""
import asyncio
import logging
from app.models.state import MedicationReviewState
from app.models.patient import Medication
from app.services.rxnorm_client import RxNormClient

logger = logging.getLogger(__name__)
_rxnorm = RxNormClient()


async def normalize_medications(state: MedicationReviewState) -> dict:
    medications = state.get("medications", [])

    async def normalize_one(med: Medication) -> Medication:
        try:
            result = await _rxnorm.normalize(med.name)
            return Medication(
                name=med.name,
                normalized_name=result["normalized_name"],
                rxcui=result.get("rxcui"),
                dosage=med.dosage,
                frequency=med.frequency,
            )
        except Exception as e:
            logger.warning("RxNorm normalization failed for %s: %s", med.name, e)
            return Medication(
                name=med.name,
                normalized_name=med.name.strip().title(),
            )

    normalized = await asyncio.gather(*[normalize_one(m) for m in medications])

    logger.info(
        "Normalized %d medications: %s",
        len(normalized),
        [m.normalized_name for m in normalized],
    )

    return {
        "medications": list(normalized),
        "completed_steps": ["normalize_medications"],
    }
