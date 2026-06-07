from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .scoring import classify_verdict, risk_level, suggest_rewrite
from .sources import SourcesIndex
from .trust import TrustProfile
from .types import (
    ArticleInput,
    AuditRunReport,
    ClaimResult,
    EvidenceSnippet,
)


@dataclass(frozen=True)
class AuditConfig:
    top_k: int = 8


def extract_claims(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    sents = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sents if len(s.strip()) >= 25]


def _mk_snippet(
    source_file: str,
    url: Optional[str],
    domain: Optional[str],
    snippet: str,
    raw_score: float,
    weight: float,
) -> EvidenceSnippet:
    return EvidenceSnippet(
        source_file=source_file,
        url=url,
        domain=domain,
        snippet=snippet,
        raw_score=float(raw_score),
        weighted_score=float(raw_score * weight),
        weight=float(weight),
    )


def audit_article(
    article: ArticleInput,
    index: SourcesIndex,
    trust: TrustProfile,
    cfg: AuditConfig,
) -> AuditRunReport:
    claims = extract_claims(article.text)
    results: list[ClaimResult] = []

    for i, claim in enumerate(claims, start=1):
        risk = risk_level(claim)

        hits = index.search(claim, top_k=max(cfg.top_k * 2, cfg.top_k))
        trusted_evidence: list[EvidenceSnippet] = []
        untrusted_evidence: list[EvidenceSnippet] = []

        for ch, raw_score in hits:
            if trust.is_excluded(ch.domain):
                continue
            w = trust.weight_for(ch.domain)
            snip = _mk_snippet(
                source_file=ch.source_file,
                url=ch.url,
                domain=ch.domain,
                snippet=ch.text,
                raw_score=raw_score,
                weight=w,
            )
            if trust.is_trusted(ch.domain):
                trusted_evidence.append(snip)
            else:
                untrusted_evidence.append(snip)

        # Sort evidence by weighted score within each bucket, then cut to top_k
        trusted_evidence.sort(key=lambda e: e.weighted_score, reverse=True)
        untrusted_evidence.sort(key=lambda e: e.weighted_score, reverse=True)
        trusted_evidence = trusted_evidence[: cfg.top_k]
        untrusted_evidence = untrusted_evidence[: cfg.top_k]

        verdict, notes = classify_verdict(claim, trusted_evidence, untrusted_evidence)
        rewrite = suggest_rewrite(claim, verdict, risk)

        results.append(
            ClaimResult(
                claim_id=f"C{i:03d}",
                text=claim,
                risk=risk,
                verdict=verdict,
                trusted_evidence=trusted_evidence,
                untrusted_evidence=untrusted_evidence,
                notes=notes,
                suggested_rewrite=rewrite,
            )
        )

    summary = {
        "claims_total": len(results),
        "supported": sum(1 for r in results if r.verdict.value == "SUPPORTED"),
        "contradicted": sum(1 for r in results if r.verdict.value == "CONTRADICTED"),
        "unclear": sum(1 for r in results if r.verdict.value == "UNCLEAR"),
        "high_risk": sum(1 for r in results if r.risk.value == "HIGH"),
    }

    trust_dump = {
        "trusted_domains": sorted(trust.trusted_domains),
        "excluded_domains": sorted(trust.excluded_domains),
        "domain_weights": dict(trust.domain_weights),
    }

    return AuditRunReport(article_id=article.id, summary=summary, trust_profile=trust_dump, claims=results)
