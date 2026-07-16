"""Auth endpoints: register, login (OAuth2 password), refresh, me."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DbSession
from app.api.v1.schemas import RefreshRequest, RegisterRequest, TokenResponse, UserResponse
from app.application.services.auth_service import AuthService
from app.infrastructure.database.repositories.ai import AuditRepository
from app.infrastructure.database.repositories.identity import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


def _service(session: DbSession) -> AuthService:
    return AuthService(UserRepository(session), AuditRepository(session))


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: RegisterRequest, session: DbSession) -> UserResponse:
    user = await _service(session).register(
        email=body.email, full_name=body.full_name, password=body.password
    )
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], session: DbSession
) -> TokenResponse:
    access, refresh, _ = await _service(session).login(
        email=form.username, password=form.password
    )
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, session: DbSession) -> TokenResponse:
    access, new_refresh = await _service(session).refresh(body.refresh_token)
    return TokenResponse(access_token=access, refresh_token=new_refresh)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
