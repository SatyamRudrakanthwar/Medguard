"""
Node: execute_research
Runs all MCP tool calls in parallel based on the investigation plan.
This is where the actual data gathering happens — no LLM involved.
"""
import asyncio
import logging
from itertools import combinations

from app.models.state import MedicationReviewState
from app.models.findings import DrugInformation, Interaction, EvidenceSource, SeverityLevel
from app.mcp.client import mcp_client

logger = logging.getLogger(__name__)


async def execute_research(state: MedicationReviewState) -> dict:
    medications = state.get("medications", [])
    plan = state.get("investigation_plan")

    med_names = [m.normalized_name or m.name for m in medications]

    # Run all research in parallel
    drug_info_task = _fetch_drug_info(med_names)
    interaction_task = _check_interactions(med_names)
    guideline_task = mcp_client.search_guidelines(med_names)
    evidence_task = _fetch_literature(med_names, state.get("user_question", ""))

    drug_info_results, interaction_result, guideline_result, lit_result = await asyncio.gather(
        drug_info_task,
        interaction_task,
        guideline_task,
        evidence_task,
        return_exceptions=True,
    )

    # Process drug information
    drug_information = []
    if not isinstance(drug_info_results, Exception):
        drug_information = drug_info_results

    # Process interactions
    interactions = []
    if not isinstance(interaction_result, Exception):
        interactions = interaction_result

    # Convert guideline results to evidence sources
    evidence: list[EvidenceSource] = []
    if not isinstance(guideline_result, Exception):
        for g in guideline_result.get("curated_guidelines", []):
            evidence.append(EvidenceSource(
                source=g.get("source", "Clinical Guideline"),
                support_score=0.95,
                excerpt=g.get("guideline", "")[:400],
            ))
        for fda in guideline_result.get("fda_safety_communications", []):
            evidence.append(EvidenceSource(
                source="FDA Enforcement Records",
                support_score=0.80,
                excerpt=fda.get("reason", "")[:400],
            ))

    # Add PubMed articles as evidence
    if not isinstance(lit_result, Exception):
        for article in lit_result.get("articles", []):
            evidence.append(EvidenceSource(
                source="PubMed",
                source_id=article.get("pmid"),
                url=article.get("url"),
                support_score=article.get("support_score", 0.75),
                excerpt=article.get("title", ""),
            ))

    logger.info(
        "Research complete: %d drug info, %d interactions, %d evidence items",
        len(drug_information), len(interactions), len(evidence),
    )

    return {
        "drug_information": drug_information,
        "interactions": interactions,
        "evidence": evidence,
        "completed_steps": ["execute_research"],
    }


async def _fetch_drug_info(med_names: list[str]) -> list[DrugInformation]:
    results = []
    tasks = [mcp_client.get_drug_information(name) for name in med_names]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(raw_results):
        if isinstance(result, Exception):
            logger.warning("Drug info failed for %s: %s", med_names[i], result)
            continue
        if result.get("found"):
            results.append(DrugInformation(
                medication_name=med_names[i],
                normalized_name=result.get("normalized_name", med_names[i]),
                drug_class=result.get("drug_class"),
                indications=result.get("indications", []),
                contraindications=result.get("contraindications", []),
                common_side_effects=result.get("common_side_effects", []),
                warnings=result.get("warnings", []),
                source="OpenFDA",
            ))
    return results


async def _check_interactions(med_names: list[str]) -> list[Interaction]:
    if len(med_names) < 2:
        return []

    result = await mcp_client.check_multiple_interactions(med_names)
    interactions = []

    for ix_data in result.get("interactions", []):
        for ix in ix_data.get("interactions", []):
            interactions.append(Interaction(
                drug_a=ix_data.get("drug_a", ""),
                drug_b=ix_data.get("drug_b", ""),
                interaction_type=ix.get("source_name", "pharmacodynamic"),
                description=ix.get("description", ""),
                severity=SeverityLevel(ix.get("severity", "moderate")),
            ))
    return interactions


async def _fetch_literature(med_names: list[str], question: str) -> dict:
    query = f"{' '.join(med_names[:3])} {question[:50]} safety"
    return await mcp_client.search_medical_literature(query, max_results=5)
