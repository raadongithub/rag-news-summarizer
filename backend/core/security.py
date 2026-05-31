"""Authentication and password security helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError

from .config import AppConfig, get_settings
from .exceptions import AuthenticationError, ValidationError

PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000
MIN_SECRET_LENGTH = 32


def _ensure_secret_strength(settings: AppConfig) -> None:
    """Validate minimum access-token secret strength."""

    if len(settings.access_token_secret) < MIN_SECRET_LENGTH:
        raise ValidationError(
            "ACCESS_TOKEN_SECRET must be at least 32 characters long for secure token signing"
        )


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256."""

    salt = secrets.token_bytes(16)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return "$".join(
        [
            PASSWORD_SCHEME,
            str(PASSWORD_ITERATIONS),
            base64.b64encode(salt).decode("utf-8"),
            base64.b64encode(derived_key).decode("utf-8"),
        ]
    )


def verify_password(password: str, encoded_password: str) -> bool:
    """Verify a plaintext password against a stored hash."""

    try:
        scheme, iterations_text, salt_text, hash_text = encoded_password.split("$", maxsplit=3)
    except ValueError:
        return False

    if scheme != PASSWORD_SCHEME:
        return False

    salt = base64.b64decode(salt_text.encode("utf-8"))
    expected_hash = base64.b64decode(hash_text.encode("utf-8"))
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        int(iterations_text),
    )
    return hmac.compare_digest(derived_key, expected_hash)


def create_access_token(user_id: str, settings: AppConfig | None = None) -> str:
    """Create a signed access token for a user."""

    resolved_settings = settings or get_settings()
    _ensure_secret_strength(resolved_settings)
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(
        minutes=resolved_settings.access_token_expire_minutes
    )
    payload = {
        "sub": user_id,
        "iss": resolved_settings.auth_token_issuer,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, resolved_settings.access_token_secret, algorithm="HS256")


def decode_access_token(token: str, settings: AppConfig | None = None) -> dict[str, str | int]:
    """Decode and validate an access token."""

    resolved_settings = settings or get_settings()
    _ensure_secret_strength(resolved_settings)
    try:
        payload = jwt.decode(
            token,
            resolved_settings.access_token_secret,
            algorithms=["HS256"],
            issuer=resolved_settings.auth_token_issuer,
        )
    except InvalidTokenError as exc:
        raise AuthenticationError("Invalid or expired access token") from exc

    if payload.get("type") != "access" or not payload.get("sub"):
        raise AuthenticationError("Invalid access token payload")
    return payload
