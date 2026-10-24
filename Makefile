.DEFAULT_GOAL := help
.PHONY: help env up down reset logs db monitoring docs test

help: ## List available commands
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-8s %s\n", $$1, $$2}'

env: ## Create .env from .env.example if missing
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

up: env ## Start everything on http://localhost:8080
	docker compose up --build

down: ## Stop everything
	docker compose down --remove-orphans

reset: ## Stop everything and delete the database
	docker compose down --remove-orphans --volumes

logs: ## Follow backend and worker logs
	docker compose logs -f backend worker

db: ## Only Postgres, published on localhost:5432 (backend outside Docker)
	docker compose -f docker-compose.yml -f compose.dev.yml up db

monitoring: env ## Same as up, plus Prometheus with alert rules on http://localhost:9090
	docker compose -f docker-compose.yml -f compose.monitoring.yml up --build

docs: ## Regenerate docs/state-diagram.md, docs/data-model.md and docs/openapi.json
	cd backend && uv run python -m app.docgen

test: ## Run backend, scoring, mocks and frontend checks locally
	cd backend && uv run ruff check app tests && uv run mypy app && uv run pytest -q
	cd scoring && uv run ruff check . && uv run mypy app && uv run pytest -q
	cd mocks && uv run ruff check . && uv run mypy app generate.py && uv run pytest -q
	cd frontend && npm run typecheck && npm run build
