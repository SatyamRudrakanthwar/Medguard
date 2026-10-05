"""
MCP Tool: get_drug_information
Fetches normalized drug info from OpenFDA via the MedicationService.
"""
import logging
from typing import Annotated

from fastmcp import Context

from app.services.openfda_client import OpenFDAClient
from app.services.rxnorm_client import RxNormClient

logger = logging.getLogger(__name__)

_openfda = OpenFDAClient()
_rxnorm = RxNormClient()


async def get_drug_information(
    drug_name: Annotated[str, "The medication name to look up (brand or generic)"],
    ctx: Context,
) -> dict:
    """
    Retrieve comprehensive information about a medication including
    indications, contraindications, warnings, and common side effects.
    Sources: OpenFDA drug label database + RxNorm normalization.
    """
    await ctx.info(f"Looking up drug information for: {drug_name}")

    norm = await _rxnorm.normalize(drug_name)
    normalized = norm["normalized_name"]
    rxcui = norm.get("rxcui")

    await ctx.info(f"Normalized '{drug_name}' → '{normalized}' (RXCUI: {rxcui})")

    label = await _openfda.get_drug_label(normalized.lower())
    if not label:
        label = await _openfda.get_drug_label(drug_name.lower())

    if not label:
        return {
            "found": False,
            "drug_name": drug_name,
            "normalized_name": normalized,
            "rxcui": rxcui,
            "message": (
                f"No FDA label data found for '{drug_name}'. "
                "This may be a very new drug, supplement, or the name may be misspelled."
            ),
        }

    info = _openfda.extract_drug_info(label)

    return {
        "found": True,
        "drug_name": drug_name,
        "normalized_name": normalized,
        "rxcui": rxcui,
        "drug_class": info.get("drug_class"),
        "brand_names": info.get("brand_names", [])[:3],
        "generic_names": info.get("generic_names", [])[:3],
        "indications": _truncate_list(info.get("indications", []), 3, 300),
        "contraindications": _truncate_list(info.get("contraindications", []), 3, 300),
        "warnings": _truncate_list(info.get("warnings", []), 3, 300),
        "common_side_effects": _truncate_list(info.get("adverse_reactions", []), 3, 300),
        "known_drug_interactions": _truncate_list(info.get("drug_interactions", []), 3, 300),
        "source": "OpenFDA",
    }


def _truncate_list(items: list[str], max_items: int, max_chars: int) -> list[str]:
    result = []
    for item in items[:max_items]:
        text = str(item).strip()
        result.append(text[:max_chars] + "..." if len(text) > max_chars else text)
    return result
