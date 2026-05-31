"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db_session
from ..models import User
from ..schema import AuthTokenResponse, LoginRequest, RegisterRequest, UserResponse
from ..services import AuthService
from ..services.serializers import serialize_user
from .dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthTokenResponse, status_code=201)
def register(
    payload: RegisterRequest,
    db_session: Session = Depends(get_db_session),
) -> dict[str, object]:
    """Register a new user account."""

    return AuthService(db_session).register(payload.email, payload.password)


@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: LoginRequest,
    db_session: Session = Depends(get_db_session),
) -> dict[str, object]:
    """Authenticate a user account."""

    return AuthService(db_session).login(payload.email, payload.password)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> dict[str, object]:
    """Return the authenticated user profile."""

    return serialize_user(current_user)
