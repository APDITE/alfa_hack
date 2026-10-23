import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from app.synthetic import is_valid_inn, synthesize

logger = logging.getLogger("mocks")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "companies.json"

ServiceName = Literal["egrul", "transparent_business", "bki"]
SERVICES: tuple[str, ...] = ("egrul", "transparent_business", "bki")

EGRUL_FIELDS = ("inn", "name", "legal_form", "okved", "registration_date", "region", "status", "director")


class AvailabilityIn(BaseModel):
    service: ServiceName
    available: bool


def load_companies(path: str | os.PathLike | None = None) -> dict[str, dict]:
    data_path = Path(path or os.environ.get("MOCKS_DATA_PATH") or DEFAULT_DATA_PATH)
    with data_path.open(encoding="utf-8") as f:
        return {c["inn"]: c for c in json.load(f)}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.companies = load_companies()
    # Доступность живёт в памяти процесса: это мок для демо сценария 7,
    # а не боевое состояние. Перезапуск контейнера включает все источники.
    app.state.availability = {name: True for name in SERVICES}
    # Неизвестный ИНН нужного формата получает детерминированную синтетику (сценарий 12).
    app.state.synthetic = os.environ.get("MOCKS_SYNTHETIC_UNKNOWN_INN", "1") != "0"
    logger.info("loaded %d companies", len(app.state.companies))
    yield


app = FastAPI(
    title="External services mocks",
    description="Моки ЕГРЮЛ/ЕГРИП, «Прозрачного бизнеса» и БКИ на синтетических данных.",
    version="0.1.0",
    lifespan=lifespan,
)


def _lookup(request: Request, service: ServiceName, inn: str) -> dict:
    if not request.app.state.availability[service]:
        logger.warning("%s unavailable, inn=%s", service, inn)
        raise HTTPException(status_code=503, detail=f"{service} is temporarily unavailable")
    company = request.app.state.companies.get(inn)
    if company is None and request.app.state.synthetic and is_valid_inn(inn):
        company = synthesize(inn)
    if company is None:
        raise HTTPException(status_code=404, detail="company not found")
    return company


@app.get("/health", tags=["service"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/mock/egrul/{inn}", tags=["mocks"])
def egrul(inn: str, request: Request) -> dict:
    company = _lookup(request, "egrul", inn)
    return {k: company[k] for k in EGRUL_FIELDS}


@app.get("/mock/transparent-business/{inn}", tags=["mocks"])
def transparent_business(inn: str, request: Request) -> dict:
    company = _lookup(request, "transparent_business", inn)
    if company["financials"] is None:
        raise HTTPException(status_code=404, detail="no data for this company")
    return {"inn": inn, **company["financials"]}


@app.get("/mock/bki/{inn}", tags=["mocks"])
def bki(inn: str, request: Request) -> dict:
    company = _lookup(request, "bki", inn)
    if company["credit_history"] is None:
        raise HTTPException(status_code=404, detail="no credit history for this company")
    return {"inn": inn, **company["credit_history"]}


@app.get("/mock/admin/availability", tags=["admin"])
def get_availability(request: Request) -> dict[str, bool]:
    return dict(request.app.state.availability)


@app.post("/mock/admin/availability", tags=["admin"])
def set_availability(body: AvailabilityIn, request: Request) -> dict[str, bool]:
    request.app.state.availability[body.service] = body.available
    logger.info("availability: %s=%s", body.service, body.available)
    return dict(request.app.state.availability)
