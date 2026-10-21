FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /uvx /bin/
ENV UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY pyproject.toml uv.lock ./

FROM base AS dev
RUN uv sync --locked --group dev --no-install-project
COPY . .
RUN uv sync --locked --group dev
CMD ["sh", "start.sh", "--reload", "--reload-dir", "app"]

FROM base AS prod
RUN uv sync --locked --no-dev --no-install-project
COPY . .
RUN uv sync --locked --no-dev --no-editable
RUN useradd --system --no-create-home app
USER app
CMD ["sh", "start.sh"]
