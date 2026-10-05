"""
Seed script — pre-loads a small set of common medications into the DB cache
by fetching from OpenFDA + RxNorm. This avoids cold-start latency on first demo.

Usage:
    cd backend
    python scripts/seed_medications.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.progress import track

from app.services.database import AsyncSessionFactory, engine, Base
from app.services.medication_service import MedicationService
from app.models import Medication

console = Console()

# Common medications that appear frequently in demos
SEED_MEDICATIONS = [
    "aspirin",
    "metformin",
    "lisinopril",
    "atorvastatin",
    "amlodipine",
    "omeprazole",
    "metoprolol",
    "levothyroxine",
    "warfarin",
    "ibuprofen",
    "acetaminophen",
    "sertraline",
    "fluoxetine",
    "losartan",
    "simvastatin",
    "clopidogrel",
    "gabapentin",
    "amoxicillin",
    "prednisone",
    "furosemide",
]


async def seed():
    console.print("[bold cyan]MedGuard — Medication Seed Script[/bold cyan]\n")

    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    console.print("[green]✓[/green] Database tables ready\n")

    async with AsyncSessionFactory() as db:
        service = MedicationService(db)

        success = 0
        failed = 0

        for name in track(SEED_MEDICATIONS, description="Fetching drug data..."):
            try:
                med = Medication(name=name)
                norm_result = await service._rxnorm.normalize(name)
                med.normalized_name = norm_result["normalized_name"]
                med.rxcui = norm_result.get("rxcui")

                info = await service.get_drug_information(med)
                if info.source != "not_found":
                    success += 1
                else:
                    failed += 1
                    console.print(f"  [yellow]⚠[/yellow] Not found: {name}")

                await db.commit()
            except Exception as e:
                failed += 1
                console.print(f"  [red]✗[/red] Error for {name}: {e}")
                await db.rollback()

    console.print(f"\n[green]✓ Seeded: {success}[/green]  [yellow]⚠ Not found: {failed}[/yellow]")
    console.print("\nSeed complete. Run the API server to start using MedGuard.")


if __name__ == "__main__":
    asyncio.run(seed())
