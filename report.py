from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .types import AuditRunReport


def _evidence_block(evs, label: str) -> str:
    if not evs:
        return f"{label}: (none)"
    top = evs[0]
    dom = top.domain or "unknown-domain"
    url = top.url or ""
    return (
        f"{label}: {top.source_file} [{dom}] w={top.weight:.2f} "
        f"(raw={top.raw_score:.2f}, weighted={top.weighted_score:.2f})\n"
        f"{top.snippet}\n{url}"
    )


def render_terminal_report(rep: AuditRunReport, console: Console) -> None:
    console.print(
        Panel.fit(
            f"[bold]Article:[/bold] {rep.article_id}\n"
            f"[bold]Summary:[/bold] {rep.summary}\n"
            f"[bold]Trust:[/bold] {rep.trust_profile}",
            title="Audit",
        )
    )

    for c in rep.claims:
        table = Table(show_header=False, box=None)
        table.add_row("[bold]Claim[/bold]", f"{c.claim_id}: {c.text}")
        table.add_row("Risk", c.risk.value)
        table.add_row("Verdict", c.verdict.value)
        if c.notes:
            table.add_row("Notes", c.notes)

        table.add_row("Trusted evidence", _evidence_block(c.trusted_evidence, "Top trusted"))
        table.add_row("Untrusted evidence", _evidence_block(c.untrusted_evidence, "Top untrusted"))

        if c.suggested_rewrite:
            table.add_row("Rewrite", c.suggested_rewrite)

        console.print(Panel(table, title=f"{c.claim_id}"))

    console.print()


def write_json_report(payload: object, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
