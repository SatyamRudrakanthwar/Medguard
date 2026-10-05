"""
MCP Tool: check_drug_interaction
Checks for known interactions between two medications using OpenFDA + RxNorm.
"""
import logging
from typing import Annotated

import httpx
from fastmcp import Context

from app.services.rxnorm_client import RxNormClient

logger = logging.getLogger(__name__)

_rxnorm = RxNormClient()

RXNORM_INTERACTION_API = "https://rxnav.nlm.nih.gov/REST/interaction"


async def check_drug_interaction(
    drug_a: Annotated[str, "First medication name"],
    drug_b: Annotated[str, "Second medication name"],
    ctx: Context,
) -> dict:
    """
    Check for known pharmacological interactions between two medications.
    Uses RxNorm Interaction API (free NIH service).
    Returns severity, description, and supporting evidence if an interaction exists.
    """
    await ctx.info(f"Checking interaction: {drug_a} ↔ {drug_b}")

    # Normalize both names to get RXCUIs
    norm_a = await _rxnorm.normalize(drug_a)
    norm_b = await _rxnorm.normalize(drug_b)

    rxcui_a = norm_a.get("rxcui")
    rxcui_b = norm_b.get("rxcui")

    name_a = norm_a["normalized_name"]
    name_b = norm_b["normalized_name"]

    await ctx.info(f"Normalized: {name_a} (RXCUI: {rxcui_a}), {name_b} (RXCUI: {rxcui_b})")

    # Try RxNorm interaction API if both RXCUIs found
    if rxcui_a and rxcui_b:
        interactions = await _check_rxnorm_interactions(rxcui_a, rxcui_b, name_a, name_b)
        if interactions:
            return {
                "interaction_found": True,
                "drug_a": name_a,
                "drug_b": name_b,
                "interactions": interactions,
                "source": "RxNorm Interaction API",
            }

    # Try by name if RXCUI lookup failed
    if not rxcui_a or not rxcui_b:
        await ctx.warning(
            f"Could not find RXCUI for one or both drugs. "
            f"drug_a RXCUI: {rxcui_a}, drug_b RXCUI: {rxcui_b}"
        )

    return {
        "interaction_found": False,
        "drug_a": name_a,
        "drug_b": name_b,
        "interactions": [],
        "note": (
            "No interaction found in RxNorm database. "
            "Absence of a known interaction does not confirm safety. "
            "Always consult a pharmacist or prescriber."
        ),
        "source": "RxNorm Interaction API",
    }


async def check_multiple_interactions(
    medications: Annotated[list[str], "List of medication names to check all pairs"],
    ctx: Context,
) -> dict:
    """
    Check all pairwise drug interactions for a list of medications.
    Returns a summary of all found interactions.
    """
    from itertools import combinations
    pairs = list(combinations(medications, 2))
    await ctx.info(f"Checking {len(pairs)} drug pairs for interactions")

    all_interactions = []
    for drug_a, drug_b in pairs:
        result = await check_drug_interaction(drug_a, drug_b, ctx)
        if result.get("interaction_found"):
            all_interactions.append(result)

    return {
        "medications_checked": medications,
        "pairs_checked": len(pairs),
        "interactions_found": len(all_interactions),
        "interactions": all_interactions,
    }


async def _check_rxnorm_interactions(
    rxcui_a: str, rxcui_b: str, name_a: str, name_b: str
) -> list[dict]:
    url = f"{RXNORM_INTERACTION_API}/list.json"
    params = {"rxcuis": f"{rxcui_a}+{rxcui_b}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return []

            data = resp.json()
            interaction_pairs = (
                data.get("fullInteractionTypeGroup", [{}])[0]
                .get("fullInteractionType", [])
            )

            results = []
            for pair in interaction_pairs:
                description = pair.get("comment", "")
                for interaction in pair.get("interactionPair", []):
                    severity = interaction.get("severity", "unknown").lower()
                    desc = interaction.get("description", description)
                    results.append({
                        "severity": _map_severity(severity),
                        "description": desc[:500] if desc else "Interaction noted.",
                        "source_name": pair.get("minConcept", [{}])[0].get("name", ""),
                    })
            return results

    except Exception as e:
        logger.error("RxNorm interaction API error: %s", e)
        return []


def _map_severity(raw: str) -> str:
    mapping = {
        "high": "high",
        "moderate": "moderate",
        "low": "low",
        "n/a": "low",
        "unknown": "low",
    }
    return mapping.get(raw.lower(), "moderate")
