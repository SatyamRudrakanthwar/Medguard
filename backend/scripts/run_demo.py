"""
Demo runner — submits all 30 synthetic cases to a running MedGuard API
and prints a summary table of findings.

Usage:
    # Make sure the API is running (uvicorn or docker-compose)
    python scripts/run_demo.py
    python scripts/run_demo.py --base-url http://localhost:8000 --api-key sk-ant-...
    python scripts/run_demo.py --cases 5     # run first 5 only
    python scripts/run_demo.py --label "Warfarin"   # run cases matching label
"""
import asyncio
import json
import time
import argparse
from pathlib import Path

import httpx
from rich.console import Console
from rich.table import Table
from rich.progress import track

console = Console()

CASES_FILE = Path(__file__).parent / "demo_cases.json"


async def submit_and_wait(
    client: httpx.AsyncClient,
    case: dict,
    api_key: str,
    timeout: float = 120.0,
) -> dict:
    """Submit one review and poll until complete."""
    headers = {"X-API-Key": api_key} if api_key else {}

    resp = await client.post(
        "/api/v1/review",
        json={
            "age": case["age"],
            "conditions": case["conditions"],
            "medications": case["medications"],
            "question": case["question"],
        },
        headers=headers,
        timeout=30.0,
    )
    resp.raise_for_status()
    review_id = resp.json()["review_id"]

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = await client.get(f"/api/v1/review/{review_id}", timeout=10.0)
        r.raise_for_status()
        data = r.json()
        if data["status"] in ("completed", "failed", "blocked"):
            return data
        await asyncio.sleep(2)

    return {"review_id": review_id, "status": "timeout", "findings": [], "high_severity_count": 0}


def severity_icon(high_count: int, total: int) -> str:
    if high_count > 0:
        return f"[red]⚠ {high_count} high[/red]"
    if total > 0:
        return f"[yellow]{total} moderate[/yellow]"
    return "[green]✓ clean[/green]"


async def main(base_url: str, api_key: str, n: int, label_filter: str) -> None:
    cases = json.loads(CASES_FILE.read_text())

    if label_filter:
        cases = [c for c in cases if label_filter.lower() in c["label"].lower()]
        if not cases:
            console.print(f"[red]No cases match filter: {label_filter!r}[/red]")
            return

    cases = cases[:n] if n else cases
    console.print(f"\n[bold blue]MedGuard Demo — running {len(cases)} cases[/bold blue]\n")

    results = []
    async with httpx.AsyncClient(base_url=base_url) as client:
        for case in track(cases, description="Running reviews…"):
            t0 = time.monotonic()
            try:
                result = await submit_and_wait(client, case, api_key)
                elapsed = time.monotonic() - t0
                results.append({
                    "label": case["label"],
                    "status": result["status"],
                    "findings": len(result.get("findings", [])),
                    "high": result.get("high_severity_count", 0),
                    "elapsed": elapsed,
                })
            except Exception as e:
                results.append({
                    "label": case["label"],
                    "status": "error",
                    "findings": 0,
                    "high": 0,
                    "elapsed": 0,
                    "error": str(e),
                })

    # Summary table
    table = Table(title="Demo Results", show_header=True, header_style="bold")
    table.add_column("Case", style="dim", max_width=40)
    table.add_column("Status", justify="center")
    table.add_column("Findings", justify="center")
    table.add_column("Severity", justify="center")
    table.add_column("Time (s)", justify="right")

    for r in results:
        status_color = {"completed": "green", "failed": "red", "blocked": "yellow", "timeout": "orange1"}.get(r["status"], "white")
        table.add_row(
            r["label"],
            f"[{status_color}]{r['status']}[/{status_color}]",
            str(r["findings"]),
            severity_icon(r["high"], r["findings"]),
            f"{r['elapsed']:.1f}",
        )

    console.print(table)

    completed = sum(1 for r in results if r["status"] == "completed")
    total_findings = sum(r["findings"] for r in results)
    console.print(
        f"\n[bold]Summary:[/bold] {completed}/{len(results)} completed, "
        f"{total_findings} total findings, "
        f"avg {sum(r['elapsed'] for r in results) / len(results):.1f}s per review\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MedGuard demo runner")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--api-key", default="", help="Anthropic API key")
    parser.add_argument("--cases", type=int, default=0, help="Max cases to run (0 = all)")
    parser.add_argument("--label", default="", help="Filter cases by label substring")
    args = parser.parse_args()

    asyncio.run(main(args.base_url, args.api_key, args.cases, args.label))
