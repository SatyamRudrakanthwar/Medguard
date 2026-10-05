"""
MedGuard CLI entry point.
Usage: python -m app
"""
import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from app.config.settings import get_settings

cli = typer.Typer(name="medguard", help="MedGuard Medication Safety Platform")
console = Console()
settings = get_settings()


@cli.command()
def serve(
    host: str = typer.Option(settings.api_host, help="Host to bind"),
    port: int = typer.Option(settings.api_port, help="Port to bind"),
    reload: bool = typer.Option(settings.api_reload, help="Enable auto-reload"),
):
    """Start the MedGuard API server."""
    console.print(
        Panel(
            Text("MedGuard API", style="bold green"),
            subtitle=f"http://{host}:{port}/docs",
        )
    )
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


@cli.command()
def review():
    """Run an interactive medication safety review from the CLI."""
    console.print(Panel("[bold cyan]MedGuard Medication Safety Review[/bold cyan]"))

    medications_input = typer.prompt("Enter medications (comma-separated)")
    medications = [m.strip() for m in medications_input.split(",") if m.strip()]

    age = typer.prompt("Enter patient age", type=int)
    conditions_input = typer.prompt("Enter conditions (comma-separated, or leave blank)", default="")
    conditions = [c.strip() for c in conditions_input.split(",") if c.strip()]
    question = typer.prompt("Enter your question")

    console.print("\n[bold yellow]Running safety review...[/bold yellow]\n")
    console.print("  [dim]→ This will use the full LangGraph pipeline in Stage 4[/dim]")
    console.print(f"\n  Medications : {', '.join(medications)}")
    console.print(f"  Age         : {age}")
    console.print(f"  Conditions  : {', '.join(conditions) or 'None'}")
    console.print(f"  Question    : {question}\n")
    console.print("[dim]CLI review execution will be wired in Stage 4 (LangGraph).[/dim]")


def main():
    cli()


if __name__ == "__main__":
    main()
