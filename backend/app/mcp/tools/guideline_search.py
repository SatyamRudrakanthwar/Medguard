"""
MCP Tool: search_guidelines
Searches for clinical safety guidelines from OpenFDA drug safety communications
and a local curated knowledge base.
In Stage 6, this will also query Qdrant for embedded guideline documents.
"""
import logging
from typing import Annotated

import httpx
from fastmcp import Context

logger = logging.getLogger(__name__)

OPENFDA_SAFETY = "https://api.fda.gov/drug/enforcement.json"

# Curated safety rules — deterministic, always returned for matching drugs
# This is intentional: certain well-known interactions are hard-coded as
# ground truth so the system works even without API calls.
CURATED_GUIDELINES: list[dict] = [
    {
        "title": "Warfarin + NSAIDs Bleeding Risk",
        "drugs": ["warfarin", "ibuprofen", "naproxen", "aspirin", "diclofenac"],
        "severity": "high",
        "guideline": (
            "Concurrent use of warfarin with NSAIDs significantly increases bleeding risk. "
            "Monitor INR closely. Consider GI protective therapy if combination is necessary."
        ),
        "source": "FDA Drug Safety Communication",
    },
    {
        "title": "Metformin + Contrast Media — Lactic Acidosis Risk",
        "drugs": ["metformin"],
        "severity": "high",
        "guideline": (
            "Metformin should be withheld before and after administration of iodinated contrast media "
            "in patients with eGFR 30–60 mL/min/1.73m² due to lactic acidosis risk."
        ),
        "source": "FDA Label Guidance",
    },
    {
        "title": "ACE Inhibitors + Potassium-Sparing Diuretics — Hyperkalemia",
        "drugs": ["lisinopril", "enalapril", "ramipril", "spironolactone", "eplerenone"],
        "severity": "moderate",
        "guideline": (
            "Combination of ACE inhibitors with potassium-sparing diuretics increases risk of "
            "hyperkalemia. Monitor serum potassium regularly."
        ),
        "source": "FDA Label Guidance",
    },
    {
        "title": "Statins + CYP3A4 Inhibitors — Myopathy Risk",
        "drugs": ["simvastatin", "atorvastatin", "lovastatin", "clarithromycin", "itraconazole"],
        "severity": "moderate",
        "guideline": (
            "Strong CYP3A4 inhibitors can increase statin plasma levels, raising myopathy and "
            "rhabdomyolysis risk. Dose reduction or alternative statin may be required."
        ),
        "source": "FDA Drug Safety Communication",
    },
    {
        "title": "SSRIs + MAOIs — Serotonin Syndrome",
        "drugs": ["fluoxetine", "sertraline", "paroxetine", "phenelzine", "tranylcypromine", "selegiline"],
        "severity": "critical",
        "guideline": (
            "Concomitant use of SSRIs and MAOIs is contraindicated due to severe serotonin syndrome risk. "
            "A washout period of at least 14 days is required when switching."
        ),
        "source": "FDA Black Box Warning",
    },
    {
        "title": "Fluoroquinolones — QT Prolongation",
        "drugs": ["ciprofloxacin", "levofloxacin", "moxifloxacin"],
        "severity": "moderate",
        "guideline": (
            "Fluoroquinolones can prolong QT interval. Use with caution in patients with known QT "
            "prolongation, hypokalemia, or concurrent QT-prolonging drugs."
        ),
        "source": "FDA Drug Safety Communication",
    },
]


async def search_guidelines(
    drug_names: Annotated[list[str], "List of medication names to search guidelines for"],
    query: Annotated[str, "Optional additional context for guideline search"] = "",
    ctx: Context = None,
) -> dict:
    """
    Search for clinical safety guidelines relevant to the given medications.
    Returns curated FDA safety guidelines, drug safety communications,
    and relevant enforcement records.
    """
    if ctx:
        await ctx.info(f"Searching guidelines for: {', '.join(drug_names)}")

    drug_names_lower = [d.lower() for d in drug_names]

    # 1. Match against curated guidelines
    matched = _match_curated(drug_names_lower)

    # 2. Search OpenFDA drug enforcement/safety communications
    fda_results = await _search_fda_safety(drug_names)

    if ctx:
        await ctx.info(f"Found {len(matched)} curated + {len(fda_results)} FDA safety records")

    return {
        "drugs_searched": drug_names,
        "curated_guidelines": matched,
        "fda_safety_communications": fda_results,
        "total_found": len(matched) + len(fda_results),
        "source": "FDA Safety Communications + Curated Guidelines",
        "note": (
            "Guidelines are for informational purposes only. "
            "Clinical decisions should involve a licensed healthcare professional."
        ),
    }


def _match_curated(drug_names_lower: list[str]) -> list[dict]:
    matched = []
    for guideline in CURATED_GUIDELINES:
        guideline_drugs = [d.lower() for d in guideline["drugs"]]
        matching = [d for d in drug_names_lower if any(gd in d or d in gd for gd in guideline_drugs)]
        if matching:
            matched.append({**guideline, "matched_drugs": matching})
    return matched


async def _search_fda_safety(drug_names: list[str]) -> list[dict]:
    results = []
    for drug in drug_names[:3]:  # limit API calls
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    OPENFDA_SAFETY,
                    params={
                        "search": f'product_description:"{drug}"',
                        "limit": 2,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("results", []):
                        results.append({
                            "drug": drug,
                            "reason": item.get("reason_for_recall", "")[:300],
                            "status": item.get("status", ""),
                            "recalling_firm": item.get("recalling_firm", ""),
                            "classification": item.get("classification", ""),
                            "source": "FDA Enforcement Records",
                        })
        except Exception as e:
            logger.warning("FDA safety search error for %s: %s", drug, e)
    return results
