from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config.settings import get_settings
from app.api import api_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"MedGuard API starting — environment: {settings.environment}")

    # Ensure Qdrant collection exists (non-blocking — fails gracefully if Docker not running)
    try:
        from app.retrieval.qdrant_store import ensure_collection
        ready = await ensure_collection()
        if ready:
            from app.retrieval.retriever import is_qdrant_ready, reset_qdrant_ready_cache
            reset_qdrant_ready_cache()
            count_ready = await is_qdrant_ready()
            print(f"Qdrant ready: {count_ready} (run ingest script to load documents)")
        else:
            print("Qdrant not running — evidence retrieval will use live PubMed fallback")
    except Exception as e:
        print(f"Qdrant startup check skipped: {e}")

    yield
    # Shutdown — flush any pending Langfuse events
    try:
        from app.observability import tracer
        tracer.flush()
    except Exception:
        pass
    print("MedGuard API shutting down")


app = FastAPI(
    title="MedGuard API",
    description="Agentic Medication Safety Intelligence Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
