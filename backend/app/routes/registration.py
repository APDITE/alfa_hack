from fastapi import APIRouter, status

from app import registration
from app.config import SettingsDep
from app.db import SessionDep
from app.integrations import IntegrationsDep
from app.schemas import CompanyResponse, LoginResponse, RegistrationRequest, UserResponse
from app.security import create_access_token

router = APIRouter(prefix="/registration", tags=["registration"])


@router.get("/company/{inn}", response_model=CompanyResponse)
def find_company(inn: str, session: SessionDep, integrations: IntegrationsDep) -> CompanyResponse:
    """Find the company in the registry before registering (registry data is public).

    409 if the company already has an account, so the client is sent to sign in at once.
    """
    return registration.lookup(session, integrations, inn)


@router.post("", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegistrationRequest,
    session: SessionDep,
    settings: SettingsDep,
    integrations: IntegrationsDep,
) -> LoginResponse:
    """Register a client by INN and sign them in. One account per company in the prototype."""
    user = registration.register(session, integrations, body, settings.bcrypt_rounds)
    token = create_access_token(user.id, user.role, settings.jwt_secret, settings.jwt_ttl_minutes)
    return LoginResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            login=user.login,
            full_name=user.full_name,
            role=user.role,
            company_inn=user.company_inn,
        ),
    )
