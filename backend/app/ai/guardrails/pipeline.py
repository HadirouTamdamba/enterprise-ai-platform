"""Guardrail pipeline (F-17): input and output safety checks.

Heuristic, deterministic first line of defence that works offline; an optional
LLM-judge layer can be added per-check via the gateway. Every block increments
metrics and is auditable by callers.
"""

import re
from dataclasses import dataclass, field

from app.core.exceptions import GuardrailViolation
from app.infrastructure.observability.metrics import GUARDRAIL_BLOCKS

# --- Prompt injection -------------------------------------------------------
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts?)",
    r"disregard\s+(your|the)\s+(instructions|system\s+prompt)",
    r"you\s+are\s+now\s+(in\s+)?(dan|developer)\s*mode",
    r"reveal\s+(your\s+)?(system\s+prompt|instructions)",
    r"pretend\s+(you\s+are|to\s+be)\s+(?!a\s+helpful)",
    r"jailbreak",
    r"</?(system|assistant)>",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

# --- PII --------------------------------------------------------------------
_PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?\d{1,3}[ .-]?)?(?:\(\d{1,4}\)[ .-]?)?\d{2,4}([ .-]?\d{2,4}){2,4}\b"),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}[ ]?(?:[A-Z0-9]{4}[ ]?){2,7}[A-Z0-9]{1,4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "ssn_fr": re.compile(r"\b[12]\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}\b"),
}

# --- Toxicity (minimal deterministic list; extend per deployment locale) -----
_TOXIC_TERMS = {"kill yourself", "i will hurt you", "bomb making", "how to make a weapon"}


@dataclass(slots=True)
class GuardrailReport:
    passed: bool = True
    triggered: list[str] = field(default_factory=list)
    redacted_text: str = ""
    pii_found: dict[str, int] = field(default_factory=dict)


def check_prompt_injection(text: str) -> bool:
    """True when the text looks like an injection/jailbreak attempt."""
    return bool(_INJECTION_RE.search(text))


def redact_pii(text: str) -> tuple[str, dict[str, int]]:
    """Replace detected PII with typed placeholders; returns (redacted, counts)."""
    counts: dict[str, int] = {}
    redacted = text
    for kind, pattern in _PII_PATTERNS.items():
        redacted, n = pattern.subn(f"[{kind.upper()}_REDACTED]", redacted)
        if n:
            counts[kind] = n
    return redacted, counts


def check_toxicity(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in _TOXIC_TERMS)


def validate_input(text: str, *, redact: bool = True, raise_on_block: bool = True) -> GuardrailReport:
    """Run input guardrails: injection → toxicity → PII redaction."""
    report = GuardrailReport(redacted_text=text)
    if check_prompt_injection(text):
        report.passed = False
        report.triggered.append("prompt_injection")
        GUARDRAIL_BLOCKS.labels("prompt_injection").inc()
    if check_toxicity(text):
        report.passed = False
        report.triggered.append("toxicity")
        GUARDRAIL_BLOCKS.labels("toxicity").inc()
    if redact:
        report.redacted_text, report.pii_found = redact_pii(text)
        if report.pii_found:
            report.triggered.append("pii_redacted")
    if not report.passed and raise_on_block:
        raise GuardrailViolation(
            "Request blocked by security guardrails",
            details={"triggered": report.triggered},
        )
    return report


def validate_output(text: str) -> GuardrailReport:
    """Run output guardrails: PII leakage + toxicity on model output."""
    report = GuardrailReport(redacted_text=text)
    report.redacted_text, report.pii_found = redact_pii(text)
    if report.pii_found:
        report.triggered.append("pii_output_redacted")
        GUARDRAIL_BLOCKS.labels("pii_output").inc()
    if check_toxicity(text):
        report.passed = False
        report.triggered.append("toxic_output")
        GUARDRAIL_BLOCKS.labels("toxic_output").inc()
    return report


def groundedness_score(answer: str, contexts: list[str]) -> float:
    """Lexical groundedness: share of informative answer tokens found in context.

    A fast, deterministic hallucination signal (0..1). Evaluation suites add an
    LLM-judge for semantic faithfulness; this guard runs on every RAG answer.
    """
    answer_tokens = {t for t in re.findall(r"[a-zA-ZÀ-ÿ0-9]{4,}", answer.lower())}
    if not answer_tokens:
        return 1.0
    context_text = " ".join(contexts).lower()
    grounded = sum(1 for token in answer_tokens if token in context_text)
    return round(grounded / len(answer_tokens), 4)
