"""Passwords (bcrypt), access tokens (JWT, HS256) and the current user dependency."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import SettingsDep
from app.db import SessionDep
from app.models import User, UserRole

_ALGORITHM = "HS256"

# auto_error=False: we answer 401 ourselves; the scheme also adds "Authorize" to Swagger.
bearer_scheme = HTTPBearer(auto_error=False, description="Token from POST /api/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID
    role: str


class InvalidTokenError(Exception):
    pass


def create_access_token(user_id: uuid.UUID, role: str, secret: str, ttl_minutes: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=ttl_minutes),
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode_access_token(token: str, secret: str) -> TokenClaims:
    try:
        payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])
        return TokenClaims(user_id=uuid.UUID(payload["sub"]), role=str(payload["role"]))
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise InvalidTokenError(str(exc)) from exc


@dataclass(frozen=True)
class CurrentUser:
    """The authenticated user of the current request."""

    id: uuid.UUID
    login: str
    full_name: str
    role: UserRole
    company_inn: str | None

    @property
    def is_employee(self) -> bool:
        return self.role is UserRole.EMPLOYEE


def get_current_user(
    session: SessionDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = decode_access_token(credentials.credentials, settings.jwt_secret)
    except InvalidTokenError:
        raise unauthorized from None
    user = session.get(User, claims.user_id)
    if user is None:
        raise unauthorized
    return CurrentUser(
        id=user.id,
        login=user.login,
        full_name=user.full_name,
        role=user.role,
        company_inn=user.company_inn,
    )


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
