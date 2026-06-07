from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNCLEAR = "UNCLEAR"


class Risk(str, Enum):
    HIGH = "HIGH"
    MED = "MED"
    LOW = "LOW"


class ArticleInput(BaseModel):
    id: str
    text: str


class EvidenceSnippet(BaseModel):
    source_file: str
    url: Optional[str] = None
    domain: Optional[str] = None
    snippet: str
    raw_score: float
    weighted_score: float
    weight: float


class ClaimResult(BaseModel):
    claim_id: str
    text: str
    risk: Risk
    verdict: Verdict

    trusted_evidence: list[EvidenceSnippet] = Field(default_factory=list)
    untrusted_evidence: list[EvidenceSnippet] = Field(default_factory=list)

    notes: Optional[str] = None
    suggested_rewrite: Optional[str] = None


class AuditRunReport(BaseModel):
    article_id: str
    summary: dict[str, Any]
    trust_profile: dict[str, Any]
    claims: list[ClaimResult]
