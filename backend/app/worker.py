"""Pipeline worker: `python -m app.worker`. Several copies can run side by side."""

import logging
import signal
import time
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType

from sqlalchemy.exc import OperationalError, ProgrammingError

from app.config import Settings
from app.db import make_engine, make_session_factory
from app.integrations import HttpIntegrations
from app.pipeline import PipelineContext, run_once
from app.products import load_products

log = logging.getLogger("app.worker")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings()
    engine = make_engine(settings.database_url)
    factory = make_session_factory(engine)
    integrations = HttpIntegrations(
        settings.mocks_url, settings.scoring_url, settings.http_timeout_seconds
    )
    ctx = PipelineContext(integrations, load_products(Path(settings.products_path)))

    stopping = False

    def stop(signum: int, frame: FrameType | None) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    log.info("worker started: mocks=%s scoring=%s", settings.mocks_url, settings.scoring_url)
    try:
        while not stopping:
            try:
                busy = run_once(factory, ctx, datetime.now(UTC))
            except (OperationalError, ProgrammingError) as exc:
                # Database not ready yet or migrations still running.
                log.warning("database not ready: %s", type(exc).__name__)
                busy = False
            if not busy:
                time.sleep(settings.worker_poll_seconds)
    finally:
        integrations.close()
        engine.dispose()
        log.info("worker stopped")


if __name__ == "__main__":
    main()
