"""PII redaction layer for content before it enters brain/agent_memory storage.

Falls back to pure regex when presidio is not installed. Regex patterns cover
the most common structured PII types; presidio adds NER-based name detection.

Public API:
    redact_pii(text)          — scrub a single string
    redact_pii_recursive(obj) — recursively scrub dicts, lists, and strings
"""
from __future__ import annotations

import re
from typing import Any

# ─── Regex patterns ───────────────────────────────────────────────────────────

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # SSN: 123-45-6789 or 123 45 6789 (dashes or single spaces as separators)
    (re.compile(r"\b\d{3}[-\s]\d{2}[-\s]\d{4}\b"), "[SSN]"),
    # Credit card — structured grouping reduces false positives vs a bare 13-19 digit run:
    #   16-digit (Visa/MC/Discover): 4-4-4-4
    #   15-digit (Amex):             4-6-5
    #   13-digit (legacy Visa):      4-4-4-1
    # Separators: optional single space or dash between groups only.
    (
        re.compile(
            r"\b(?:"
            r"(?:\d{4}[- ]?){3}\d{4}"             # 16-digit
            r"|\d{4}[- ]?\d{6}[- ]?\d{5}"         # 15-digit Amex
            r"|\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d"  # 13-digit legacy
            r")\b"
        ),
        "[CARD]",
    ),
    # Email — includes + addressing (user+tag@host.tld)
    (
        re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"),
        "[EMAIL]",
    ),
    # US/CA phone: (555) 123-4567, 555-123-4567, +1 555 123 4567, etc.
    (
        re.compile(
            r"(?<!\d)"
            r"(\+?1[\s.\-]?)?"
            r"(\(?\d{3}\)?[\s.\-]?)"
            r"\d{3}[\s.\-]?\d{4}"
            r"(?!\d)"
        ),
        "[PHONE]",
    ),
    # International phone: +CC followed by ≥2 separator-delimited digit groups.
    # Covers +44 20 7946 0958, +49 30 1234 5678, +33 1 23 45 67 89, +1-800-555-1234.
    # Requires ≥2 groups so a bare country code (+44) doesn't match.
    (
        re.compile(r"\+\d{1,3}(?:[\s.\-]\d{1,8}){2,8}(?!\d)"),
        "[PHONE]",
    ),
]

# ─── Presidio (optional) ──────────────────────────────────────────────────────

try:
    from presidio_analyzer import AnalyzerEngine  # type: ignore
    from presidio_anonymizer import AnonymizerEngine  # type: ignore
    from presidio_anonymizer.entities import OperatorConfig  # type: ignore

    _analyzer = AnalyzerEngine()
    _anonymizer = AnonymizerEngine()
    _PRESIDIO_AVAILABLE = True
except ImportError:
    _PRESIDIO_AVAILABLE = False


def _presidio_redact(text: str) -> str:
    """Run presidio NER + regex-based redaction and return the scrubbed string."""
    results = _analyzer.analyze(
        text=text,
        entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "US_SSN"],
        language="en",
    )
    if not results:
        return text
    operators = {
        "PERSON": OperatorConfig("replace", {"new_value": "[NAME]"}),
        "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "[EMAIL]"}),
        "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[PHONE]"}),
        "CREDIT_CARD": OperatorConfig("replace", {"new_value": "[CARD]"}),
        "US_SSN": OperatorConfig("replace", {"new_value": "[SSN]"}),
    }
    return _anonymizer.anonymize(text=text, analyzer_results=results, operators=operators).text


def _regex_redact(text: str) -> str:
    """Apply all regex patterns in order and return the scrubbed string."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ─── Public API ───────────────────────────────────────────────────────────────


def redact_pii(text: str) -> str:
    """Return text with PII replaced by typed placeholders.

    Uses presidio (NER + regex) when available, regex-only otherwise.
    Always safe to call — returns input unchanged on any internal error.
    """
    if not isinstance(text, str) or not text:
        return text
    try:
        if _PRESIDIO_AVAILABLE:
            return _presidio_redact(text)
        return _regex_redact(text)
    except Exception:
        return text


def redact_pii_recursive(obj: Any) -> Any:
    """Recursively redact PII in dicts, lists, and strings.

    Handles arbitrary nesting so it can sanitize Supabase payload dicts or
    lists of memory entries before insertion. Non-string leaf values (int, bool,
    None, etc.) pass through unchanged.
    """
    if isinstance(obj, str):
        return redact_pii(obj)
    if isinstance(obj, dict):
        return {k: redact_pii_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_pii_recursive(item) for item in obj]
    return obj
