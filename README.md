# Alfa Hack

Hackathon starter repository with a FastAPI backend and a React + TypeScript frontend.

## Requirements

- Docker Engine and Docker Compose v2
- `uv` for local backend development
- Node.js 22 and npm for local frontend development
- GNU Make

## Quick start (Docker)

```
cp .env.example .env
make dev
```

Open <http://localhost:8080>. The API health endpoint is at <http://localhost:8080/api/health> and the interactive API docs are at <http://localhost:8080/api/docs>.

## Local development

Backend:

```
cd backend
uv sync --group dev
uv run fastapi dev
```

Frontend:

```
cd frontend
npm ci
npm run dev
```

On the first run use `uv lock` in `backend/` and `npm install` in `frontend/` to generate `uv.lock` and `package-lock.json`, then commit them.

## Environments

Compose files provide separate configurations:

- Development: `make dev` (HTTP, source reload, API docs enabled)
- Tests: `make test` (isolated test configuration; HTTP)
- Production: `make prod` (HTTP-to-HTTPS redirect and TLS; configure a domain first)

Production requires a DNS name pointing to the host and inbound ports 80 and 443. Set `CERTBOT_DOMAIN` and `LETSENCRYPT_EMAIL` in `.env`, then follow the [TLS setup](#production-tls-with-lets-encrypt) instructions. Never commit `.env` or private keys.

## Production TLS with Let's Encrypt

1. Set `CERTBOT_DOMAIN` to the registered DNS name and `LETSENCRYPT_EMAIL` to a monitored email address in `.env`.
2. Ensure the DNS A/AAAA records point to this host and ports 80/443 are reachable from the internet.
3. Run `make prod-cert-init`. This starts the production stack with a temporary HTTP-only Nginx configuration, obtains the certificate using the HTTP-01 webroot challenge, and restarts Nginx with HTTPS enabled.
4. Start or update the production stack with `make prod`.
5. Schedule `make prod-cert-renew` (for example, daily via a host cron job). It renews eligible certificates and reloads Nginx.

Certificate data is stored in the ignored local `letsencrypt/` directory. Back it up securely; do not commit it. The ignored `certbot/` directory is used only for the HTTP-01 challenge webroot. For local testing, use `make test` and do not request real certificates.

## Backend architecture

`backend/src/app/` is arranged by DDD responsibility:

- `domain/`: domain model and rules
- `application/`: use cases and ports
- `infrastructure/`: implementations of external-system adapters
- `presentation/`: HTTP/API adapters
- `main/`: application composition and startup

Use Pydantic models for request/response DTOs and validation in `presentation/`. Keep domain entities and value objects as standard-library dataclasses in `domain/`; do not use Pydantic models as domain models.

Dishka manages dependencies; application settings are provided at `Scope.APP` and resolved from the container during app composition. For future handler dependencies, use `FromDishka[T]` with Dishka's `@inject_sync` FastAPI integration; do not use FastAPI `Depends`.

The starter includes only the health endpoint; business logic and persistence belong in future feature work.

## Git workflow

Use Gitflow branch names and merge direction:

- `main`: production-ready releases
- `develop`: integration branch
- `feature/<short-name>` branches from `develop`, merge back to `develop`
- `release/<version>` branches from `develop`, merge into `main` and back into `develop`
- `hotfix/<short-name>` branches from `main`, merge into `main` and `develop`

Keep feature branches focused and use pull requests for integration. Create the initial commit on `main`, then create `develop` from it before starting feature branches.

## Useful commands

Run `make help` to list project commands. Test commands do not require production secrets or certificates.
