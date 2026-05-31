"""Shared API dependencies."""

from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..database import get_db_session
from ..models import User
from ..queries import UserQueries
from ..core.exceptions import AuthenticationError
from ..core.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db_session: Session = Depends(get_db_session),
) -> User:
    """Resolve the authenticated user for the current request."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Missing bearer access token")

    payload = decode_access_token(credentials.credentials)
    user = UserQueries(db_session).get_by_id(str(payload["sub"]))
    if user is None:
        raise AuthenticationError("Authenticated user no longer exists")
    return user
