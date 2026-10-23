import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.schemas import ScoreRequest, ScoreResponse
from app.scorecard import get_config, score_request

logger = logging.getLogger("scoring")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # падаем на старте, если конфиг карты битый, а не на первом запросе
    cfg = get_config()
    logger.info("scorecard loaded: version=%s factors=%d", cfg.model_version, len(cfg.factors))
    yield


app = FastAPI(
    title="Scoring service",
    description="Оценка риска (вероятность дефолта) по балльной карте с объяснением факторов.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["service"])
def health() -> dict[str, str]:
    return {"status": "ok", "model_version": get_config().model_version}


@app.post("/score", response_model=ScoreResponse, tags=["scoring"])
def score(req: ScoreRequest) -> ScoreResponse:
    result = score_request(req)
    logger.info(
        "scored inn=%s product=%s score=%.4f class=%s points=%d",
        req.company.inn,
        req.application.product_id,
        result.score,
        result.risk_class,
        result.points_total,
    )
    return result
