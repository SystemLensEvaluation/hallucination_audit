from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import track

from .audit import AuditConfig, audit_article
from .report import render_terminal_report, write_json_report
from .sources import load_sources_index
from .trust import TrustProfile
from .types import ArticleInput, AuditRunReport

app = typer.Typer(add_completion=False, help="Hallucination Audit CLI (AI-independent, trust-weighted)")
console = Console()


@app.command()
def audit(
    input_path: Path = typer.Argument(..., help="Path to JSONL of AI-generated articles."),
    sources: Path = typer.Option(..., "--sources", help="Directory of local source files."),
    trust_profile: Path = typer.Option(..., "--trust-profile", help="Path to trust profile JSON."),
    top_k: int = typer.Option(5, "--top-k", min=1, max=20, help="Evidence snippets per bucket per claim."),
    format: str = typer.Option("terminal", "--format", help="terminal|json"),
    out: Optional[Path] = typer.Option(None, "--out", help="Output file for json format."),
) -> None:
    if not input_path.exists():
        raise typer.BadParameter(f"Input not found: {input_path}")
    if not sources.exists() or not sources.is_dir():
        raise typer.BadParameter(f"Sources directory not found: {sources}")
    if not trust_profile.exists():
        raise typer.BadParameter(f"Trust profile not found: {trust_profile}")

    trust = TrustProfile.from_json(trust_profile)
    index = load_sources_index(sources)
    cfg = AuditConfig(top_k=top_k)

    reports: list[AuditRunReport] = []
    with input_path.open("r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    for ln in track(lines, description="Auditing"):
        obj = json.loads(ln)
        article = ArticleInput(id=str(obj["id"]), text=str(obj["text"]))
        rep = audit_article(article, index, trust, cfg)
        reports.append(rep)

    if format == "terminal":
        for rep in reports:
            render_terminal_report(rep, console=console)
        return

    if format == "json":
        payload = [r.model_dump() for r in reports]
        if out is None:
            console.print_json(json.dumps(payload, ensure_ascii=False))
        else:
            write_json_report(payload, out)
            console.print(f"[green]Wrote[/green] {out}")
        return

    raise typer.BadParameter("format must be 'terminal' or 'json'")


if __name__ == "__main__":
    app()
