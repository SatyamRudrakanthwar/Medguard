"""
Knowledge base ingestion script.
Fetches documents from OpenFDA + PubMed, embeds them, and stores in Qdrant.

Usage:
    cd backend
    python scripts/ingest_knowledge_base.py              # full ingestion
    python scripts/ingest_knowledge_base.py --guidelines  # guidelines only (fast, no API)
    python scripts/ingest_knowledge_base.py --openfda     # OpenFDA labels only
    python scripts/ingest_knowledge_base.py --pubmed      # PubMed abstracts only
"""
import asyncio
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from app.retrieval.qdrant_store import ensure_collection, collection_count
from app.retrieval.retriever import reset_qdrant_ready_cache
from app.retrieval.ingestion import ingest_guidelines, ingest_openfda_labels, ingest_pubmed_abstracts

console = Console()


async def main(run_guidelines: bool, run_openfda: bool, run_pubmed: bool):
    console.print(Panel("[bold cyan]MedGuard — Knowledge Base Ingestion[/bold cyan]"))

    # Ensure collection exists
    console.print("[dim]Connecting to Qdrant...[/dim]")
    ready = await ensure_collection()
    if not ready:
        console.print("[red]✗ Cannot connect to Qdrant. Is Docker running?[/red]")
        console.print("  Run: [bold]docker compose up -d[/bold]")
        sys.exit(1)

    before = await collection_count()
    console.print(f"[green]✓[/green] Qdrant connected. Current document count: {before}\n")

    total = 0

    if run_guidelines:
        console.print("[bold]Step 1: Ingesting curated safety guidelines...[/bold]")
        with console.status("Embedding guidelines..."):
            n = await ingest_guidelines()
        console.print(f"  [green]✓[/green] {n} guideline chunks stored\n")
        total += n

    if run_openfda:
        console.print("[bold]Step 2: Ingesting OpenFDA drug labels (25 drugs)...[/bold]")
        console.print("  [dim]This takes ~2 minutes (API rate limit applied)[/dim]")
        with console.status("Fetching and embedding drug labels..."):
            n = await ingest_openfda_labels()
        console.print(f"  [green]✓[/green] {n} drug label chunks stored\n")
        total += n

    if run_pubmed:
        console.print("[bold]Step 3: Ingesting PubMed abstracts (13 queries × 5 articles)...[/bold]")
        console.print("  [dim]This takes ~1 minute (API rate limit applied)[/dim]")
        with console.status("Fetching and embedding PubMed abstracts..."):
            n = await ingest_pubmed_abstracts()
        console.print(f"  [green]✓[/green] {n} abstract chunks stored\n")
        total += n

    after = await collection_count()
    reset_qdrant_ready_cache()

    console.print(Panel(
        f"[bold green]Ingestion Complete[/bold green]\n\n"
        f"  New chunks added : {total}\n"
        f"  Total in Qdrant  : {after}",
        title="Done",
    ))
    console.print("\n[dim]Restart the API server to use the new knowledge base.[/dim]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest medical documents into Qdrant")
    parser.add_argument("--guidelines", action="store_true", help="Ingest curated guidelines only")
    parser.add_argument("--openfda", action="store_true", help="Ingest OpenFDA labels only")
    parser.add_argument("--pubmed", action="store_true", help="Ingest PubMed abstracts only")
    args = parser.parse_args()

    # If no flags — run all
    run_all = not (args.guidelines or args.openfda or args.pubmed)
    asyncio.run(main(
        run_guidelines=run_all or args.guidelines,
        run_openfda=run_all or args.openfda,
        run_pubmed=run_all or args.pubmed,
    ))
