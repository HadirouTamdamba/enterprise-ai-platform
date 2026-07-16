# Enterprise AI Platform — developer entrypoints

.PHONY: help install up up-deps down logs dev-backend dev-frontend test test-backend \
        test-frontend lint format migrate seed evaluate clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install backend and frontend dependencies
	cd backend && python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
	cd frontend && npm install

up: ## Start the full stack (build if needed)
	docker compose up -d --build

up-deps: ## Start only infrastructure dependencies (postgres, redis, qdrant, monitoring)
	docker compose up -d postgres redis qdrant prometheus grafana loki

down: ## Stop the stack
	docker compose down

logs: ## Tail all container logs
	docker compose logs -f --tail=100

dev-backend: ## Run backend with hot reload
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

dev-frontend: ## Run frontend with hot reload
	cd frontend && npm run dev

migrate: ## Apply database migrations
	cd backend && .venv/bin/alembic upgrade head

seed: ## Seed initial data (admin user, roles, demo prompts)
	cd backend && .venv/bin/python -m app.infrastructure.database.seed

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend test suite with coverage
	cd backend && .venv/bin/pytest ../tests/backend -v --cov=app --cov-report=term-missing

test-frontend: ## Run frontend tests
	cd frontend && npm test

evaluate: ## Run AI evaluation suites (RAG, prompts, agents)
	cd backend && .venv/bin/python -m evaluation.run_all

lint: ## Lint & type-check everything
	cd backend && .venv/bin/ruff check app && .venv/bin/mypy app
	cd frontend && npm run lint

format: ## Auto-format code
	cd backend && .venv/bin/ruff format app && .venv/bin/ruff check --fix app
	cd frontend && npm run format

clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/.mypy_cache backend/.ruff_cache backend/.pytest_cache frontend/.next
