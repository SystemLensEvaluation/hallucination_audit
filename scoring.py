from __future__ import annotations

import re
from typing import Optional

from .types import EvidenceSnippet, Risk, Verdict

_NUM_RE = re.compile(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b")
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")

_HIGH_RISK_TERMS = {
    "soc 2",
    "iso 27001",
    "hipaa",
    "gdpr",
    "compliant",
    "certified",
    "lawsuit",
    "indicted",
    "convicted",
    "killed",
    "dead",
    "deaths",
    "confirmed",
}

_NEGATION = {"not", "no", "never", "none", "without", "denied"}

_STOP = {
    "the","a","an","and","or","to","of","in","on","for","with","by","as","at","from","that","this","it","is","are",
    "was","were","be","been","being","will","would","could","should","may","might","can"
}


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def risk_level(claim: str) -> Risk:
    c = _normalize(claim)
    if _NUM_RE.search(c) or _YEAR_RE.search(c):
        return Risk.HIGH
    if any(term in c for term in _HIGH_RISK_TERMS):
        return Risk.HIGH
    if any(w in c for w in ["will", "plans to", "expected to", "reportedly", "sources said"]):
        return Risk.MED
    return Risk.LOW


def _tokens(s: str) -> list[str]:
    return [t for t in re.findall(r"[A-Za-z0-9]+", s.lower()) if t not in _STOP]


def _token_set(s: str) -> set[str]:
    return set(_tokens(s))


def _overlap_ratio(a: str, b: str) -> float:
    ta = _token_set(a)
    tb = _token_set(b)
    if not ta:
        return 0.0
    return len(ta & tb) / max(1, len(ta))


def _has_negation(s: str) -> bool:
    return any(w in _token_set(s) for w in _NEGATION)

def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]

def _best_sentence_for_claim(claim: str, evidence_snippet: str) -> tuple[str, float]:
    best = ""
    best_overlap = 0.0
    for sent in _split_sentences(evidence_snippet):
        ov = _overlap_ratio(claim, sent)
        if ov > best_overlap:
            best_overlap = ov
            best = sent
    return best or evidence_snippet, best_overlap

def classify_verdict(
    claim: str,
    trusted: list[EvidenceSnippet],
    untrusted: list[EvidenceSnippet],
) -> tuple[Verdict, Optional[str]]:

    # If we have trusted evidence, prefer it
    if trusted:
        top_snip = trusted[0].snippet
        best_sent, overlap = _best_sentence_for_claim(claim, top_snip)

        if overlap >= 0.55 and (_has_negation(claim) != _has_negation(best_sent)):
            return Verdict.CONTRADICTED, (
                f"Trusted sentence overlaps but negation mismatches (overlap={overlap:.2f})."
            )

        if overlap >= 0.62:
            return Verdict.SUPPORTED, (
                f"Supported by trusted evidence (overlap={overlap:.2f})."
            )

        if overlap >= 0.40:
            return Verdict.UNCLEAR, (
                f"Trusted evidence is related but not strong (overlap={overlap:.2f})."
            )

        return Verdict.UNCLEAR, (
            f"Trusted evidence overlap is weak (overlap={overlap:.2f})."
        )

    # If no trusted evidence but untrusted evidence exists
    if untrusted:
        top_snip = untrusted[0].snippet
        best_sent, overlap = _best_sentence_for_claim(claim, top_snip)
        return Verdict.UNCLEAR, (
            f"No trusted support found. Untrusted overlap={overlap:.2f}."
        )

    # Nothing found at all
    return Verdict.UNCLEAR, "No evidence retrieved."



def suggest_rewrite(claim: str, verdict: Verdict, risk: Risk) -> Optional[str]:
    if verdict == Verdict.SUPPORTED:
        return None

    if risk == Risk.HIGH:
        redacted = re.sub(_NUM_RE, "[number]", claim)
        redacted = re.sub(r"\bconfirmed\b", "reported", redacted, flags=re.IGNORECASE)
        return f"{redacted} (Add a trusted citation or remove precise details.)"

    if verdict == Verdict.CONTRADICTED:
        return "This conflicts with trusted evidence. Remove it or rewrite to match cited sources."

    return "Add a trusted citation, or rewrite more cautiously (e.g., 'reportedly' / 'according to X')."
