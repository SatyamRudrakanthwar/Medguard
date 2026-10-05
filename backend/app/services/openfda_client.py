"""
OpenFDA API client — free, no key required for basic usage.
Docs: https://open.fda.gov/apis/drug/label/
"""
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

OPENFDA_BASE = "https://api.fda.gov/drug"
DEFAULT_TIMEOUT = 10.0


class OpenFDAClient:
    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self._timeout = timeout

    async def get_drug_label(self, drug_name: str) -> Optional[dict]:
        """
        Fetch drug label data from OpenFDA.
        Returns the first matching label result or None.
        """
        url = f"{OPENFDA_BASE}/label.json"
        params = {
            "search": f'openfda.brand_name:"{drug_name}"+openfda.generic_name:"{drug_name}"',
            "limit": 1,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    if results:
                        return results[0]
                elif resp.status_code == 404:
                    # Try generic name search as fallback
                    return await self._search_generic(drug_name)
        except httpx.TimeoutException:
            logger.warning("OpenFDA timeout for drug: %s", drug_name)
        except Exception as e:
            logger.error("OpenFDA error for %s: %s", drug_name, e)
        return None

    async def _search_generic(self, drug_name: str) -> Optional[dict]:
        url = f"{OPENFDA_BASE}/label.json"
        params = {
            "search": f'openfda.generic_name:"{drug_name}"',
            "limit": 1,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    return results[0] if results else None
        except Exception as e:
            logger.error("OpenFDA generic search error for %s: %s", drug_name, e)
        return None

    async def search_drug_interactions(self, drug_name: str) -> list[dict]:
        """Search for known drug interactions via OpenFDA adverse events."""
        url = f"{OPENFDA_BASE}/event.json"
        params = {
            "search": f'patient.drug.medicinalproduct:"{drug_name}"',
            "count": "patient.drug.druginteractiondrug.medicinalproduct.exact",
            "limit": 10,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("results", [])
        except Exception as e:
            logger.error("OpenFDA interaction search error for %s: %s", drug_name, e)
        return []

    @staticmethod
    def extract_drug_info(label: dict) -> dict:
        """Parse an OpenFDA label response into a clean dict."""
        openfda = label.get("openfda", {})

        def first_or_empty(key: str) -> list[str]:
            val = label.get(key, [])
            return val[:3] if val else []

        return {
            "brand_names": openfda.get("brand_name", []),
            "generic_names": openfda.get("generic_name", []),
            "drug_class": openfda.get("pharm_class_epc", [""])[0] if openfda.get("pharm_class_epc") else None,
            "indications": first_or_empty("indications_and_usage"),
            "contraindications": first_or_empty("contraindications"),
            "warnings": first_or_empty("warnings"),
            "adverse_reactions": first_or_empty("adverse_reactions"),
            "drug_interactions": first_or_empty("drug_interactions"),
        }
