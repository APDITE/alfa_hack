from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app import ops
from app.applications import require_employee
from app.db import SessionDep
from app.schemas import OpsSummary
from app.security import CurrentUserDep

router = APIRouter(prefix="/ops", tags=["ops"])
metrics_router = APIRouter(tags=["ops"])


@router.get("/summary", response_model=OpsSummary)
def summary(session: SessionDep, user: CurrentUserDep) -> OpsSummary:
    """Pipeline health for employees: queue, stuck applications, external services, errors."""
    require_employee(user)
    return ops.summary(ops.collect(session, datetime.now(UTC)))


@metrics_router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def metrics(session: SessionDep) -> PlainTextResponse:
    """Prometheus metrics (text format 0.0.4), for scraping inside the compose network."""
    body = ops.prometheus(ops.collect(session, datetime.now(UTC)))
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4")
