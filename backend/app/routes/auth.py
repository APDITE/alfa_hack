from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.config import SettingsDep
from app.db import SessionDep
from app.models import User
from app.schemas import LoginRequest, LoginResponse, UserResponse
from app.security import CurrentUserDep, create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, session: SessionDep, settings: SettingsDep) -> LoginResponse:
    """Sign in. Test accounts: `client1`…`client8`, `analyst`; password equals login."""
    user = session.scalar(select(User).where(User.login == body.login))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid login or password")
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


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUserDep) -> UserResponse:
    """The signed-in user."""
    return UserResponse(
        id=user.id,
        login=user.login,
        full_name=user.full_name,
        role=user.role,
        company_inn=user.company_inn,
    )
