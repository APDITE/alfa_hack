FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/
ENV UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY pyproject.toml uv.lock* ./

FROM base AS dev
RUN uv sync --group dev --no-install-project
COPY src ./src
COPY tests ./tests
RUN uv sync --group dev
CMD ["uvicorn", "app.main.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "src"]

FROM base AS prod
RUN uv sync --no-dev --no-install-project
COPY src ./src
RUN uv sync --no-dev --no-editable
RUN useradd --system --no-create-home app
USER app
CMD ["uvicorn", "app.main.app:app", "--host", "0.0.0.0", "--port", "8000"]
