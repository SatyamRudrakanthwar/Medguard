"""
Node: validate_input
Deterministic safety checks before any LLM or tool is invoked.
Blocks requests asking for diagnosis, prescription changes, or dosing decisions.
"""
import re
from app.models.state import MedicationReviewState

# Phrases that indicate a clinical decision request — block these
_BLOCKED_PATTERNS = [
    r"\bshould i (stop|start|take|discontinue|change|switch|increase|decrease|reduce)\b",
    r"\bcan i (stop|start|take|discontinue|change|switch|increase|decrease|reduce)\b",
    r"\bis it safe (to stop|to start|to take|for me)\b",
    r"\bdiagnos(e|is|ing)\b",
    r"\bprescri(be|ption|bing)\b",
    r"\bwhat (dosage|dose) should\b",
    r"\bhow much should i take\b",
    r"\btreat(ment|ing|ment plan)\b",
    r"\bcure\b",
    r"\bam i (sick|ill|dying|having)\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _BLOCKED_PATTERNS]


async def validate_input(state: MedicationReviewState) -> dict:
    question = state.get("user_question", "")
    medications = state.get("medications", [])

    # Check for dangerous request patterns
    for pattern in _COMPILED:
        if pattern.search(question):
            return {
                "blocked": True,
                "block_reason": (
                    "Your question appears to be asking for a medical recommendation or "
                    "clinical decision. MedGuard can only provide general medication safety "
                    "information — not advice on whether to start, stop, or change a medication. "
                    "Please consult a licensed healthcare professional for that guidance."
                ),
                "completed_steps": ["validate_input"],
            }

    # Validate we have medications to work with
    if not medications:
        return {
            "blocked": True,
            "block_reason": "No medications provided. Please provide at least one medication name.",
            "completed_steps": ["validate_input"],
        }

    # Check medication count limit
    if len(medications) > 20:
        return {
            "blocked": True,
            "block_reason": "Maximum 20 medications per review. Please reduce the list.",
            "completed_steps": ["validate_input"],
        }

    return {
        "blocked": False,
        "block_reason": None,
        "completed_steps": ["validate_input"],
    }
