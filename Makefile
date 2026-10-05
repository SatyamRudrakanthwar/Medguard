.PHONY: help install dev-up dev-down api frontend test lint format

help:
	@echo "MedGuard — Available commands"
	@echo ""
	@echo "  make install     Install backend dependencies"
	@echo "  make dev-up      Start PostgreSQL, Qdrant, Redis (Docker)"
	@echo "  make dev-down    Stop all Docker services"
	@echo "  make api         Start FastAPI development server"
	@echo "  make frontend    Start React development server"
	@echo "  make test        Run backend tests"
	@echo "  make lint        Run ruff linter"
	@echo "  make format      Run ruff formatter"

install:
	cd backend && pip install -e ".[dev]"

db-migrate:
	cd backend && alembic upgrade head

db-revision:
	cd backend && alembic revision --autogenerate -m "$(msg)"

db-seed:
	cd backend && python scripts/seed_medications.py

ingest:
	cd backend && python scripts/ingest_knowledge_base.py

ingest-guidelines:
	cd backend && python scripts/ingest_knowledge_base.py --guidelines

dev-up:
	docker compose up -d
	@echo "Services running:"
	@echo "  PostgreSQL : localhost:5432"
	@echo "  Qdrant     : localhost:6333  (UI: http://localhost:6333/dashboard)"
	@echo "  Redis      : localhost:6379"

dev-down:
	docker compose down

api:
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

frontend:
	cd frontend && npm run dev

test:
	cd backend && pytest tests/ -v --tb=short

lint:
	cd backend && ruff check app/

format:
	cd backend && ruff format app/
