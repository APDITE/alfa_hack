.DEFAULT_GOAL := help
.PHONY: help env up down reset logs test

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

test: ## Run backend and frontend checks locally
	cd backend && uv run ruff check app tests && uv run mypy app && uv run pytest -q
	cd frontend && npm run typecheck && npm run build
