"""Idempotent seed: products, demo companies and test accounts.

Run with `python -m app.main.seed` (the dev stack runs it on start after migrations).
"""

import logging
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import make_engine, make_session_factory
from app.models import Company, Product, User, UserRole
from app.products import ProductConfig, load_products
from app.security import hash_password

log = logging.getLogger(__name__)


def seed_products(session: Session, products: dict[str, ProductConfig]) -> None:
    for config in products.values():
        p = config.params
        session.merge(
            Product(
                id=p.id,
                name=config.name,
                description=config.description,
                purposes=list(config.purposes),
                min_amount=p.min_amount,
                max_amount=p.max_amount,
                min_term_months=p.min_term_months,
                max_term_months=p.max_term_months,
                base_rate=p.base_rate,
                min_business_age_months=p.min_business_age_months,
            )
        )


def _ensure_user(
    session: Session, login: str, full_name: str, role: UserRole, company_inn: str | None
) -> None:
    if session.scalar(select(User).where(User.login == login)) is not None:
        return
    # Test accounts only: password equals login.
    session.add(
        User(
            login=login,
            password_hash=hash_password(login),
            full_name=full_name,
            role=role,
            company_inn=company_inn,
        )
    )


def seed_demo_data(session: Session, demo_path: Path) -> None:
    data: dict[str, Any] = yaml.safe_load(demo_path.read_text(encoding="utf-8")) or {}
    for raw in data.get("companies", []):
        reg_date = raw["registration_date"]
        session.merge(
            Company(
                inn=str(raw["inn"]),
                name=str(raw["name"]),
                legal_form=str(raw["legal_form"]),
                okved=str(raw["okved"]),
                registration_date=reg_date
                if isinstance(reg_date, date)
                else date.fromisoformat(str(reg_date)),
                region=str(raw["region"]),
                director=str(raw["director"]),
                registry_status=str(raw.get("registry_status", "active")),
            )
        )
        client = raw.get("client")
        if client:
            session.flush()
            _ensure_user(
                session, client["login"], client["full_name"], UserRole.CLIENT, str(raw["inn"])
            )
    for raw in data.get("employees", []):
        _ensure_user(session, raw["login"], raw["full_name"], UserRole.EMPLOYEE, None)


def seed_all(session: Session, settings: Settings) -> None:
    seed_products(session, load_products(Path(settings.products_path)))
    seed_demo_data(session, Path(settings.demo_data_path))
    session.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    settings = Settings()
    engine = make_engine(settings.database_url)
    try:
        with make_session_factory(engine)() as session:
            seed_all(session, settings)
            users = len(session.scalars(select(User)).all())
            products = len(session.scalars(select(Product)).all())
        log.info("seed done: %d products, %d users", products, users)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
