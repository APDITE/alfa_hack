from fastapi import APIRouter, HTTPException, status

from app.presentation import stubs
from app.presentation.schemas import LoginRequest, LoginResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    """Sign in with a test account. Stub: `client1/client1` or `analyst/analyst`."""
    users = {
        stubs.CLIENT_USER.login: stubs.CLIENT_USER,
        stubs.EMPLOYEE_USER.login: stubs.EMPLOYEE_USER,
    }
    user = users.get(body.login)
    if user is None or body.password != body.login:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid login or password")
    return LoginResponse(access_token=f"stub-token-{user.role}", user=user)


@router.get("/me", response_model=UserResponse)
def me() -> UserResponse:
    """Current user. Stub: always the test client."""
    return stubs.CLIENT_USER
