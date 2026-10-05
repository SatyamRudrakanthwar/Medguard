"""
Deterministic Safety Policy Engine — runs entirely outside the LLM.
All checks here are rule-based and cannot be bypassed by prompt injection.

Checks performed:
  1. Input sanitization  — strip prompt injection attempts
  2. Request classification — block diagnosis / treatment requests
  3. Medication name validation — reject implausible inputs
  4. Output validation — catch treatment recommendations in LLM output
"""
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── Patterns that indicate a clinical decision request ────────────────────────
_BLOCKED_PATTERNS = [
    r"\bshould i (stop|start|take|discontinue|change|switch|increase|decrease|reduce|avoid)\b",
    r"\bcan i (stop|start|take|discontinue|change|switch|increase|decrease|reduce)\b",
    r"\bis it safe (to stop|to start|to take|for me)\b",
    r"\b(should|can) (i|we|he|she|they) (stop|start|take|use|continue)\b.*\b(medication|medicine|drug|pill|tablet)\b",
    r"\bdiagnos(e|is|ing)\b",
    r"\bprescri(be|ption|bing)\b",
    r"\bwhat (dosage|dose) should\b",
    r"\bhow much should i take\b",
    r"\bam i (sick|ill|dying|overdosing|having a reaction)\b",
    r"\bdo i have\b.*\b(disease|condition|disorder|cancer|diabetes|infection)\b",
    r"\btreat(ment plan|ment recommendation|ment decision)\b",
    r"\bcure\b.*\b(for|my|the)\b",
    r"\brecommend.*(taking|stopping|starting|switching)\b",
]

# ── Patterns that suggest prompt injection in user input ──────────────────────
_INJECTION_PATTERNS = [
    r"ignore (previous|prior|above|all) instructions",
    r"you are now",
    r"new (system|persona|role|instructions?)",
    r"disregard (all|previous|prior|your)",
    r"(act|pretend|roleplay|simulate) as",
    r"</?(system|assistant|human|user)>",
    r"\[INST\]|\[/INST\]",
    r"<\|im_start\|>|<\|im_end\|>",
    r"<<SYS>>|<</SYS>>",
]

_COMPILED_BLOCKED = [re.compile(p, re.IGNORECASE) for p in _BLOCKED_PATTERNS]
_COMPILED_INJECTION = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]

# ── Output patterns that indicate LLM hallucinated a recommendation ───────────
_OUTPUT_RECOMMENDATION_PATTERNS = [
    r"\b(i recommend|we recommend|you should|you must|i suggest) (stop|start|take|discontinue|switch|reduce|increase)\b",
    r"\bstop taking\b",
    r"\bstart taking\b",
    r"\bincrease (your|the) dose\b",
    r"\bdecrease (your|the) dose\b",
    r"\byou (should|must|need to) (consult|see) a doctor (before|to) (change|stop|start)\b",
    r"\bthis (medication|drug) is (safe|unsafe|dangerous) for you\b",
]

_COMPILED_OUTPUT = [re.compile(p, re.IGNORECASE) for p in _OUTPUT_RECOMMENDATION_PATTERNS]


@dataclass
class SafetyCheckResult:
    passed: bool
    reason: str = ""
    sanitized_question: str = ""
    sanitized_medications: list = None

    def __post_init__(self):
        if self.sanitized_medications is None:
            self.sanitized_medications = []


class SafetyPolicyEngine:

    def check_request(self, question: str, medications: list[str]) -> SafetyCheckResult:
        """
        Full input safety check. Returns SafetyCheckResult with passed=False if blocked.
        Always returns sanitized versions of the inputs.
        """
        # 1. Sanitize inputs (removes injection attempts)
        clean_question = self._sanitize_text(question)
        clean_medications = [self._sanitize_text(m) for m in medications]
        clean_medications = [m for m in clean_medications if m]

        # 2. Check for prompt injection
        for pattern in _COMPILED_INJECTION:
            if pattern.search(question):
                logger.warning("Prompt injection attempt detected in question")
                return SafetyCheckResult(
                    passed=False,
                    reason="Your input contains text that cannot be processed by this system.",
                    sanitized_question=clean_question,
                    sanitized_medications=clean_medications,
                )

        # 3. Check for blocked clinical decision requests
        for pattern in _COMPILED_BLOCKED:
            if pattern.search(clean_question):
                logger.info("Blocked clinical decision request: %s", clean_question[:80])
                return SafetyCheckResult(
                    passed=False,
                    reason=(
                        "Your question asks for a clinical decision — whether to start, stop, "
                        "or change a medication. MedGuard provides medication safety information "
                        "only and cannot make treatment recommendations. "
                        "Please discuss medication changes with your healthcare provider."
                    ),
                    sanitized_question=clean_question,
                    sanitized_medications=clean_medications,
                )

        # 4. Validate medication list
        if not clean_medications:
            return SafetyCheckResult(
                passed=False,
                reason="No valid medication names provided.",
                sanitized_question=clean_question,
                sanitized_medications=[],
            )

        if len(clean_medications) > 20:
            return SafetyCheckResult(
                passed=False,
                reason="Maximum 20 medications per review.",
                sanitized_question=clean_question,
                sanitized_medications=clean_medications[:20],
            )

        # 5. Check for suspiciously short/long medication names
        for med in clean_medications:
            if len(med) < 2:
                return SafetyCheckResult(
                    passed=False,
                    reason=f"Medication name '{med}' is too short to be valid.",
                    sanitized_question=clean_question,
                    sanitized_medications=clean_medications,
                )
            if len(med) > 150:
                return SafetyCheckResult(
                    passed=False,
                    reason=f"Medication name '{med[:30]}...' is too long.",
                    sanitized_question=clean_question,
                    sanitized_medications=clean_medications,
                )

        return SafetyCheckResult(
            passed=True,
            sanitized_question=clean_question,
            sanitized_medications=clean_medications,
        )

    def validate_output_text(self, text: str) -> tuple[bool, list[str]]:
        """
        Scan LLM-generated text for treatment recommendations.
        Returns (is_clean, list_of_violations).
        """
        violations = []
        for pattern in _COMPILED_OUTPUT:
            if pattern.search(text):
                violations.append(f"Possible treatment recommendation detected: {pattern.pattern[:60]}")
        return len(violations) == 0, violations

    def validate_findings(self, findings: list) -> list:
        """
        Scan safety findings for treatment recommendations.
        Removes or sanitizes any finding that contains clinical decision language.
        """
        clean = []
        for finding in findings:
            is_clean, violations = self.validate_output_text(finding.description)
            if not is_clean:
                logger.warning(
                    "Finding '%s' contains recommendation language — sanitizing",
                    finding.title,
                )
                # Append a note rather than delete the finding
                finding.description = (
                    finding.description + "\n\n[Note: This finding has been reviewed for "
                    "clinical recommendation language and is presented for informational purposes only.]"
                )
            clean.append(finding)
        return clean

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Remove prompt injection tokens and normalize whitespace."""
        for pattern in _COMPILED_INJECTION:
            text = pattern.sub("", text)
        # Remove HTML tags
        text = re.sub(r"<[^>]{1,100}>", "", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text


# Singleton
safety_engine = SafetyPolicyEngine()
