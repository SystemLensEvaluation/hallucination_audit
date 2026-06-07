from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


def _norm_domain(d: str) -> str:
    d = d.strip().lower()
    if d.startswith("www."):
        d = d[4:]
    return d


@dataclass(frozen=True)
class TrustProfile:
    trusted_domains: set[str]
    excluded_domains: set[str]
    domain_weights: dict[str, float]  # exact domains + "*" default

    @staticmethod
    def from_json(path: Path) -> "TrustProfile":
        obj = json.loads(path.read_text(encoding="utf-8"))
        trusted = {_norm_domain(x) for x in obj.get("trusted_domains", [])}
        excluded = {_norm_domain(x) for x in obj.get("excluded_domains", [])}
        weights = { _norm_domain(k) if k != "*" else "*": float(v) for k, v in obj.get("domain_weights", {}).items() }
        if "*" not in weights:
            weights["*"] = 0.35
        return TrustProfile(trusted_domains=trusted, excluded_domains=excluded, domain_weights=weights)

    def is_trusted(self, domain: Optional[str]) -> bool:
        if not domain:
            return False
        return _norm_domain(domain) in self.trusted_domains

    def is_excluded(self, domain: Optional[str]) -> bool:
        if not domain:
            return False
        return _norm_domain(domain) in self.excluded_domains

    def weight_for(self, domain: Optional[str]) -> float:
        if not domain:
            return self.domain_weights.get("*", 0.35)
        d = _norm_domain(domain)
        return self.domain_weights.get(d, self.domain_weights.get("*", 0.35))


def domain_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        host = urlparse(url).hostname
        if not host:
            return None
        host = host.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return None
