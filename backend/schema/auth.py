"""Authentication request and response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request payload for user registration."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Request payload for user login."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    """Serialized user response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    created_at: datetime
    updated_at: datetime


class AuthTokenResponse(BaseModel):
    """Token response returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
