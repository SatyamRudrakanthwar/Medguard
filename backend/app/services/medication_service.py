"""
MedicationService — orchestrates RxNorm normalization + OpenFDA data fetch + DB caching.
This is the primary data layer service consumed by MCP tools in Stage 3.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Medication, DrugInformation
from app.services.openfda_client import OpenFDAClient
from app.services.rxnorm_client import RxNormClient
from app.services.db_models import DrugCacheRecord

logger = logging.getLogger(__name__)

CACHE_TTL_HOURS = 24


class MedicationService:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._openfda = OpenFDAClient()
        self._rxnorm = RxNormClient()

    async def normalize_medications(self, raw_names: list[str]) -> list[Medication]:
        """Convert raw user-entered names to normalized Medication objects."""
        medications = []
        for name in raw_names:
            result = await self._rxnorm.normalize(name)
            medications.append(
                Medication(
                    name=name,
                    normalized_name=result["normalized_name"],
                    rxcui=result.get("rxcui"),
                )
            )
        return medications

    async def get_drug_information(self, medication: Medication) -> DrugInformation:
        """
        Fetch drug information for a medication.
        Cache-first: checks DB, falls back to OpenFDA API.
        """
        lookup_name = (medication.normalized_name or medication.name).lower()

        # Check DB cache first
        cached = await self._get_cached(lookup_name)
        if cached:
            logger.debug("Cache hit for: %s", lookup_name)
            return self._record_to_model(cached, medication.name)

        # Fetch from OpenFDA
        logger.info("Fetching OpenFDA data for: %s", lookup_name)
        label = await self._openfda.get_drug_label(lookup_name)

        if label:
            info = self._openfda.extract_drug_info(label)
            await self._cache_drug(lookup_name, medication.rxcui, info, label)
            return DrugInformation(
                medication_name=medication.name,
                normalized_name=medication.normalized_name or medication.name,
                drug_class=info.get("drug_class"),
                indications=info.get("indications", [])[:5],
                contraindications=info.get("contraindications", [])[:5],
                common_side_effects=info.get("adverse_reactions", [])[:5],
                warnings=info.get("warnings", [])[:5],
                source="OpenFDA",
            )

        # If OpenFDA returns nothing, return minimal record
        logger.warning("No OpenFDA data found for: %s", lookup_name)
        return DrugInformation(
            medication_name=medication.name,
            normalized_name=medication.normalized_name or medication.name,
            source="not_found",
        )

    async def get_bulk_drug_information(
        self, medications: list[Medication]
    ) -> list[DrugInformation]:
        """Fetch information for multiple medications concurrently."""
        import asyncio
        tasks = [self.get_drug_information(med) for med in medications]
        return await asyncio.gather(*tasks)

    async def _get_cached(self, name: str) -> DrugCacheRecord | None:
        cutoff = datetime.utcnow() - timedelta(hours=CACHE_TTL_HOURS)
        result = await self._db.execute(
            select(DrugCacheRecord).where(
                DrugCacheRecord.normalized_name == name,
                DrugCacheRecord.fetched_at >= cutoff,
                DrugCacheRecord.is_valid == True,
            )
        )
        return result.scalar_one_or_none()

    async def _cache_drug(
        self, name: str, rxcui: str | None, info: dict, raw: dict
    ) -> None:
        record = DrugCacheRecord(
            normalized_name=name,
            rxcui=rxcui,
            drug_class=info.get("drug_class"),
            indications=info.get("indications", []),
            contraindications=info.get("contraindications", []),
            common_side_effects=info.get("adverse_reactions", []),
            warnings=info.get("warnings", []),
            raw_openfda=raw,
        )
        self._db.add(record)
        try:
            await self._db.flush()
        except Exception as e:
            logger.warning("Failed to cache drug %s: %s", name, e)
            await self._db.rollback()

    @staticmethod
    def _record_to_model(record: DrugCacheRecord, original_name: str) -> DrugInformation:
        return DrugInformation(
            medication_name=original_name,
            normalized_name=record.normalized_name,
            drug_class=record.drug_class,
            indications=record.indications or [],
            contraindications=record.contraindications or [],
            common_side_effects=record.common_side_effects or [],
            warnings=record.warnings or [],
            source="OpenFDA (cached)",
        )
