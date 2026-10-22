from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.models import Company, Product, User
from app.security import verify_password
from app.seed import seed_all


def test_seed_is_idempotent(app: FastAPI, settings: Settings) -> None:
    factory: sessionmaker[Session] = app.state.session_factory
    with factory() as session:
        seed_all(session, settings)  # second run on top of the fixture's first
        assert session.scalar(select(func.count()).select_from(Product)) == 2
        assert session.scalar(select(func.count()).select_from(Company)) == 8
        assert session.scalar(select(func.count()).select_from(User)) == 9


def test_passwords_are_hashed(app: FastAPI) -> None:
    factory: sessionmaker[Session] = app.state.session_factory
    with factory() as session:
        user = session.scalar(select(User).where(User.login == "analyst"))
        assert user is not None
        assert user.password_hash != "analyst"
        assert verify_password("analyst", user.password_hash)
