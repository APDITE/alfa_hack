#!/bin/sh
# Apply migrations, load demo data (idempotent), then start the API.
# Extra arguments go to uvicorn, e.g. --reload in the dev stack.
set -e
alembic upgrade head
python -m app.seed
exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 "$@"
