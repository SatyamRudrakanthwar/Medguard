"""
RxNorm API client — free NIH service, no key required.
Used for normalizing medication names to standard RxNorm concepts.
Docs: https://rxnav.nlm.nih.gov/RxNormAPIs.html
"""
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"
DEFAULT_TIMEOUT = 8.0

# Common name aliases to handle user typos or shorthand
COMMON_ALIASES: dict[str, str] = {
    "tylenol": "acetaminophen",
    "advil": "ibuprofen",
    "motrin": "ibuprofen",
    "aleve": "naproxen",
    "aspirin": "aspirin",
    "glucophage": "metformin",
    "zocor": "simvastatin",
    "lipitor": "atorvastatin",
    "prinivil": "lisinopril",
    "zestril": "lisinopril",
    "norvasc": "amlodipine",
    "coumadin": "warfarin",
    "plavix": "clopidogrel",
    "nexium": "esomeprazole",
    "prilosec": "omeprazole",
    "zoloft": "sertraline",
    "prozac": "fluoxetine",
    "xanax": "alprazolam",
    "valium": "diazepam",
    "synthroid": "levothyroxine",
}


class RxNormClient:
    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self._timeout = timeout

    async def normalize(self, drug_name: str) -> dict:
        """
        Normalize a drug name using RxNorm.
        Returns: { normalized_name, rxcui, found }
        """
        cleaned = drug_name.strip().lower()

        # Check alias table first
        if cleaned in COMMON_ALIASES:
            alias = COMMON_ALIASES[cleaned]
            rxcui = await self._get_rxcui(alias)
            return {
                "input_name": drug_name,
                "normalized_name": alias.title(),
                "rxcui": rxcui,
                "found": True,
                "source": "alias_table",
            }

        # Try RxNorm API
        rxcui = await self._get_rxcui(cleaned)
        if rxcui:
            display_name = await self._get_display_name(rxcui) or drug_name.title()
            return {
                "input_name": drug_name,
                "normalized_name": display_name,
                "rxcui": rxcui,
                "found": True,
                "source": "rxnorm_api",
            }

        # Fallback: title-case the original
        return {
            "input_name": drug_name,
            "normalized_name": drug_name.strip().title(),
            "rxcui": None,
            "found": False,
            "source": "fallback",
        }

    async def _get_rxcui(self, drug_name: str) -> Optional[str]:
        url = f"{RXNORM_BASE}/rxcui.json"
        params = {"name": drug_name, "search": 2}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    rxcui = (
                        data.get("idGroup", {})
                        .get("rxnormId", [None])[0]
                    )
                    return rxcui
        except httpx.TimeoutException:
            logger.warning("RxNorm timeout for: %s", drug_name)
        except Exception as e:
            logger.error("RxNorm error for %s: %s", drug_name, e)
        return None

    async def _get_display_name(self, rxcui: str) -> Optional[str]:
        url = f"{RXNORM_BASE}/rxcui/{rxcui}/properties.json"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("properties", {}).get("name")
        except Exception:
            pass
        return None

    async def get_related_drugs(self, rxcui: str) -> list[str]:
        """Get related drug names (useful for synonym matching)."""
        url = f"{RXNORM_BASE}/rxcui/{rxcui}/related.json"
        params = {"tty": "IN+BN"}  # Ingredient + Brand Name
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    groups = data.get("relatedGroup", {}).get("conceptGroup", [])
                    names = []
                    for group in groups:
                        for concept in group.get("conceptProperties", []):
                            names.append(concept.get("name", ""))
                    return [n for n in names if n]
        except Exception as e:
            logger.error("RxNorm related drugs error for %s: %s", rxcui, e)
        return []
