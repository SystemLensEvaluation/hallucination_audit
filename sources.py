from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rank_bm25 import BM25Okapi

from .trust import domain_from_url

URL_LINE_RE = re.compile(r"^\s*URL:\s*(\S+)\s*$", re.IGNORECASE)


def _read_text(path: Path) -> str:
    txt = path.read_text(encoding="utf-8", errors="ignore")
    # MVP: crude HTML strip
    if path.suffix.lower() in {".html", ".htm"}:
        txt = re.sub(r"<[^>]+>", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def _extract_url(raw_text: str) -> tuple[Optional[str], str]:
    # If the first line contains "URL: ...", treat it as metadata and remove it from content
    lines = raw_text.splitlines()
    if not lines:
        return None, raw_text
    m = URL_LINE_RE.match(lines[0])
    if m:
        url = m.group(1)
        remaining = "\n".join(lines[1:])
        return url, remaining
    return None, raw_text


def _chunk_text(text: str, max_len: int = 700) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    cur = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(cur) + len(p) + 1 <= max_len:
            cur = (cur + " " + p).strip()
        else:
            if cur:
                chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)
    return chunks


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+", text.lower())


@dataclass(frozen=True)
class SourceChunk:
    source_file: str
    url: Optional[str]
    domain: Optional[str]
    text: str


class SourcesIndex:
    def __init__(self, chunks: list[SourceChunk]):
        self.chunks = chunks
        corpus = [_tokenize(c.text) for c in chunks]
        self.bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_k: int = 8) -> list[tuple[SourceChunk, float]]:
        q = _tokenize(query)
        scores = self.bm25.get_scores(q)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        return [(self.chunks[i], float(s)) for i, s in ranked]


def load_sources_index(sources_dir: Path) -> SourcesIndex:
    exts = {".txt", ".md", ".html", ".htm"}
    chunks: list[SourceChunk] = []

    for p in sorted(sources_dir.rglob("*")):
        if not (p.is_file() and p.suffix.lower() in exts):
            continue

        raw = p.read_text(encoding="utf-8", errors="ignore")
        url, body = _extract_url(raw)

        txt = body
        if p.suffix.lower() in {".html", ".htm"}:
            txt = re.sub(r"<[^>]+>", " ", txt)
        txt = re.sub(r"\s+", " ", txt).strip()

        dom = domain_from_url(url)

        for ch in _chunk_text(txt):
            chunks.append(
                SourceChunk(
                    source_file=str(p.relative_to(sources_dir)),
                    url=url,
                    domain=dom,
                    text=ch,
                )
            )

    return SourcesIndex(chunks=chunks)
