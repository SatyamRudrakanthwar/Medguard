from fastapi import APIRouter
from datetime import datetime

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    return {
        "status": "ok",
        "service": "medguard-api",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/")
async def root() -> dict:
    return {
        "service": "MedGuard API",
        "version": "1.0.0",
        "docs": "/docs",
    }
