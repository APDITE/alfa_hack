"""Self-registration of a client by INN (scenario 12).

The company card is taken from the registry (ЕГРЮЛ/ЕГРИП, the mock in the demo), so the
client types only a name, a login and a password. One client account per company in
this prototype. Financials are not asked here: the pipeline requests them through a
clarification when «Прозрачный бизнес» has no data on the company.
"""

import re
from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.integrations import ExternalUnavailableError, Integrations
from app.models import Company, User, UserRole
from app.schemas import CompanyResponse, LegalForm, RegistrationRequest
from app.security import hash_password

_INN = re.compile(r"^\d{10}(\d{2})?$")


def ensure_not_registered(session: Session, inn: str) -> None:
    if session.scalar(select(User.id).where(User.company_inn == inn)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Company is already registered")


def fetch_company(integrations: Integrations, inn: str) -> dict[str, Any]:
    """The registry record of the company, or an HTTP error the client can act on."""
    if not _INN.match(inn):
        raise HTTPException(422, "INN must be 10 or 12 digits")
    try:
        record = integrations.egrul(inn)
    except ExternalUnavailableError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Registry is temporarily unavailable"
        ) from exc
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found in the registry")
    return record


def _legal_form(record: dict[str, Any], inn: str) -> LegalForm:
    raw = str(record.get("legal_form", ""))
    return (
        LegalForm(raw)
        if raw in LegalForm.__members__
        else (LegalForm.IP if len(inn) == 12 else LegalForm.OOO)
    )


def to_response(record: dict[str, Any], inn: str) -> CompanyResponse:
    return CompanyResponse(
        inn=inn,
        name=str(record.get("name", "")),
        legal_form=_legal_form(record, inn),
        okved=str(record.get("okved", "")),
        registration_date=date.fromisoformat(str(record["registration_date"])),
        region=str(record.get("region", inn[:2])),
        director=str(record.get("director", "")),
    )


def lookup(session: Session, integrations: Integrations, inn: str) -> CompanyResponse:
    """Step 1 of the form: the card to confirm, or why registration cannot go on."""
    if not _INN.match(inn):
        raise HTTPException(422, "INN must be 10 or 12 digits")
    ensure_not_registered(session, inn)
    return to_response(fetch_company(integrations, inn), inn)


def register(
    session: Session, integrations: Integrations, body: RegistrationRequest, bcrypt_rounds: int
) -> User:
    ensure_not_registered(session, body.inn)
    if session.scalar(select(User.id).where(User.login == body.login)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Login is already taken")

    record = fetch_company(integrations, body.inn)
    card = to_response(record, body.inn)
    company = session.get(Company, body.inn) or Company(inn=body.inn)
    company.name = card.name
    company.legal_form = card.legal_form.value
    company.okved = card.okved
    company.registration_date = card.registration_date
    company.region = card.region
    company.director = card.director
    company.registry_status = str(record.get("status", "active"))
    session.add(company)

    user = User(
        login=body.login,
        password_hash=hash_password(body.password, bcrypt_rounds),
        full_name=body.full_name.strip(),
        role=UserRole.CLIENT,
        company_inn=body.inn,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:  # a concurrent registration took the company or the login
        session.rollback()
        ensure_not_registered(session, body.inn)
        raise HTTPException(status.HTTP_409_CONFLICT, "Login is already taken") from exc
    return user
