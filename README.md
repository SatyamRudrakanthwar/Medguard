# MedGuard — Agentic Medication Safety Intelligence Platform

> **Informational use only.** MedGuard is a research and demonstration platform. It does not provide medical advice, diagnosis, or treatment recommendations. Always consult a qualified healthcare professional.

MedGuard is a production-grade AI platform that performs multi-step medication safety analysis using a LangGraph agent pipeline, real-time SSE streaming, a vector knowledge base (Qdrant), and a React + TypeScript frontend — all runnable with one `docker compose up` command.

---

## Architecture

```
Browser (React + TypeScript)
        │
        │  HTTP + SSE
        ▼
   Nginx (port 80)
   ├── /api/*  ──► FastAPI  (port 8000, internal)
   └── /*      ──► React SPA (static files)
                       │
           ┌───────────┼───────────────┐
           │           │               │
      PostgreSQL    Qdrant         Redis
      (reviews)  (embeddings)    (cache)
           │
    LangGraph Pipeline
    ┌──────────────────────────────────────────┐
    │  validate_input → normalize_medications  │
    │  → analyze_case → create_plan            │
    │  → execute_research (parallel MCP calls) │
    │  → aggregate_evidence                    │
    │  → validate_evidence ──► research_again ─┤
    │                     └──► analyze_risk    │
    │                          → generate_report│
    └──────────────────────────────────────────┘
           │                    │
    Anthropic Claude      FastMCP Server
    (4 structured agents) (6 tools: FDA, RxNorm,
                           PubMed, Qdrant RAG)
```

---

## Features

- **Agentic pipeline** — LangGraph 1.x StateGraph with 10 nodes, conditional routing, and automatic retry when evidence is insufficient
- **Real-time streaming** — SSE pushes each agent step to the browser as it completes; late connections replay buffered events
- **Free knowledge base** — OpenFDA drug labels, RxNorm drug normalization, PubMed literature (no paid data required)
- **RAG retrieval** — `all-MiniLM-L6-v2` embeddings in Qdrant with drug-name filtering; falls back to live PubMed when Qdrant is unavailable
- **Deterministic safety layer** — regex-based input blocking (14 patterns), prompt injection detection (8 patterns), and LLM output validation before results are stored
- **Stub mode** — works without an Anthropic API key; uses curated clinical guidelines + live API data to produce realistic demo results
- **Observability** — Langfuse tracing for every LLM call (input/output tokens, latency), graph node, and MCP tool call
- **Rate limiting** — sliding-window in-memory limiter (10 reviews/hour per IP)
- **API key privacy** — keys live only in the browser's `localStorage` and are sent as `X-API-Key`; never stored server-side

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, React Router v6 |
| API | FastAPI, Uvicorn, Pydantic v2, SSE |
| Agent orchestration | LangGraph 1.x (StateGraph, TypedDict state) |
| LLM | Anthropic Claude (claude-sonnet-4-6), tool_use structured output |
| Tool layer | FastMCP 3.x (6 tools), in-process client |
| Vector store | Qdrant, sentence-transformers (all-MiniLM-L6-v2, 384-dim) |
| Database | PostgreSQL 16, SQLAlchemy async, Alembic |
| Cache | Redis 7 |
| Observability | Langfuse (traces, generations, tool spans) |
| Infra | Docker Compose, Nginx |

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for the one-command path)
- **OR** Python 3.11+, Node 20+, and local installs of PostgreSQL, Qdrant, Redis

For real AI analysis (not required for demo mode):
- An [Anthropic API key](https://console.anthropic.com/)

Optional:
- A [Langfuse](https://cloud.langfuse.com/) account for observability (free tier available)

---

## Quick Start (Docker — recommended)

```bash
# 1. Clone
git clone <repo-url>
cd medguard

# 2. Create backend config (only the API key line matters for demo)
cp .env.example backend/.env
# Optional: edit backend/.env and add ANTHROPIC_API_KEY=sk-ant-...

# 3. Start everything
docker compose up -d

# 4. Wait ~60 seconds for services to become healthy, then open:
#    http://localhost          ← React frontend
#    http://localhost/api/v1/docs  ← Swagger UI
```

To watch startup logs:
```bash
docker compose logs -f backend
```

To stop:
```bash
docker compose down        # keep volumes
docker compose down -v     # also delete database / vector store data
```

---

## Manual Setup (development)

### 1. Start infrastructure

```bash
docker compose -f docker-compose.dev.yml up -d
# Starts only postgres:5432, qdrant:6333, redis:6379
```

### 2. Backend

```bash
cd backend
cp ../.env.example .env   # edit .env with your values

pip install -e ".[dev]"   # or: pip install -e .

alembic upgrade head      # create database tables

uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/api/v1/docs
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

---

## Configuration

Copy `.env.example` to `backend/.env`. Key variables:

| Variable | Description | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude agents | No (stub mode if absent) |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key for observability | No |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key | No |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `QDRANT_HOST` | Qdrant hostname | Yes |
| `REDIS_URL` | Redis connection string | Yes |

All other settings have sensible defaults. In Docker, the service hostnames (`postgres`, `qdrant`, `redis`) are automatically overridden.

---

## Building the Knowledge Base

On first run, the vector store is empty. Run the ingestion script to populate it with free public drug data:

```bash
# Inside the backend directory (or docker exec medguard_backend)
python scripts/ingest_knowledge_base.py --guidelines  # ~10 seconds
python scripts/ingest_knowledge_base.py --openfda     # ~60 seconds, fetches FDA labels
python scripts/ingest_knowledge_base.py --pubmed      # ~120 seconds, fetches PubMed articles

# Or run everything at once:
python scripts/ingest_knowledge_base.py --guidelines --openfda --pubmed
```

Without ingestion, evidence retrieval automatically falls back to live PubMed searches.

---

## Running the Demo

With the API running, submit all 30 synthetic medication cases:

```bash
cd backend
python scripts/run_demo.py                                       # stub mode
python scripts/run_demo.py --api-key sk-ant-...                 # with Claude
python scripts/run_demo.py --cases 5                            # first 5 only
python scripts/run_demo.py --label "Warfarin"                   # filter by name
```

---

## API Reference

All endpoints are documented at `http://localhost:8000/api/v1/docs` (Swagger UI).

### POST `/api/v1/review`
Submit a medication safety review. Returns `202 Accepted` immediately.

```json
{
  "age": 72,
  "conditions": ["atrial fibrillation"],
  "medications": ["warfarin", "aspirin"],
  "question": "What bleeding risks are associated with this combination?"
}
```

Headers: `X-API-Key: sk-ant-...` (optional — enables Claude agents)

### GET `/api/v1/review/{id}`
Poll for the review result. `status` is one of: `processing`, `completed`, `failed`, `blocked`.

### GET `/api/v1/review/{id}/stream`
Server-Sent Events stream. Connect immediately after POST to receive live step updates. Late connections replay all past events.

```
data: {"event":"step_completed","step":"analyze_case","message":"Analyzing patient case..."}
data: {"event":"done","message":"<review_id>"}
```

### GET `/api/v1/review`
List the 20 most recent reviews.

### GET `/api/v1/health`
Health check.

---

## Running Tests

```bash
cd backend
pytest tests/unit/ -v           # 43 unit tests (models, safety, MCP tools)
pytest tests/ -v                # all tests including integration
```

---

## Safety Design

MedGuard deliberately limits what it will respond to:

- **Blocked questions** — clinical decision requests ("Should I stop taking X?", "What dose should I take?", diagnoses) are rejected before any LLM call using 14 regex patterns
- **Prompt injection detection** — 8 patterns catch common injection attempts ("ignore previous instructions", "you are now", etc.) in both the question and medication names
- **Output validation** — LLM-generated findings are scanned for treatment recommendation language before being stored or returned
- **Disclaimer** — every response includes a prominent disclaimer that the output is not medical advice

---

## Observability

When `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set, every review generates a Langfuse trace containing:

- **Node spans** — one span per LangGraph node with duration
- **LLM generations** — model name, input/output token counts, latency
- **Tool spans** — one span per MCP tool call (OpenFDA, RxNorm, PubMed, Qdrant) with duration

When keys are absent, all tracing is a no-op — the application runs identically.

---

## Project Structure

```
medguard/
├── backend/
│   ├── app/
│   │   ├── agents/          # Claude agents + stub fallbacks
│   │   ├── api/             # FastAPI routes (review, health)
│   │   ├── config/          # Pydantic settings
│   │   ├── graph/           # LangGraph graph + nodes + runner
│   │   ├── mcp/             # FastMCP server + 6 tools + client
│   │   ├── models/          # Pydantic models (patient, findings, report, review)
│   │   ├── observability/   # Langfuse tracer
│   │   ├── retrieval/       # Qdrant store, embedder, retriever, document processor
│   │   ├── safety/          # Policy engine + rate limiter
│   │   └── services/        # Database, event stream, medication service
│   ├── alembic/             # Database migrations
│   ├── scripts/             # Ingestion, demo, seeding scripts
│   └── tests/               # Unit + integration tests
├── frontend/
│   ├── src/
│   │   ├── api/             # TypeScript API client + types
│   │   ├── components/      # Layout, FindingCard, ProgressStep, SeverityBadge
│   │   ├── hooks/           # useReviewStream, useLocalStorage
│   │   └── pages/           # Home, Review, History, Settings
│   └── nginx.conf           # Production Nginx config
├── docker-compose.yml       # Full stack (one-command)
├── docker-compose.dev.yml   # Infrastructure only (dev)
└── .env.example             # Configuration template
```

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

*Built with Claude Code. This platform is for research and demonstration purposes only.*
