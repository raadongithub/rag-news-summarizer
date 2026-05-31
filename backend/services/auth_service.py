"""Authentication service layer."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import AppConfig, get_settings
from ..core.exceptions import AuthenticationError, ConflictError, ValidationError
from ..core.security import create_access_token, hash_password, verify_password
from ..queries import UserQueries
from .serializers import serialize_user


class AuthService:
    """Handle user registration, login, and token issuance."""

    def __init__(
        self,
        db_session: Session,
        settings: AppConfig | None = None,
        user_repository: UserQueries | None = None,
    ) -> None:
        """Initialize the auth service."""

        self.db_session = db_session
        self.settings = settings or get_settings()
        self.user_repository = user_repository or UserQueries(db_session)

    def register(self, email: str, password: str) -> dict[str, object]:
        """Create a new user and issue an access token."""

        normalized_email = email.strip().lower()
        if len(password) < self.settings.min_password_length:
            raise ValidationError(
                f"Password must be at least {self.settings.min_password_length} characters long"
            )
        if password.strip() == "":
            raise ValidationError("Password cannot contain only whitespace")
        if not any(c.isalpha() for c in password):
            raise ValidationError("Password must include at least one letter")
        if not any(c.isdigit() for c in password):
            raise ValidationError("Password must include at least one number")
        if self.user_repository.get_by_email(normalized_email):
            raise ConflictError("An account with this email already exists")

        try:
            user = self.user_repository.create(
                email=normalized_email,
                password_hash=hash_password(password),
            )
            self.db_session.commit()
        except IntegrityError as exc:
            self.db_session.rollback()
            raise ConflictError("An account with this email already exists") from exc

        return {
            "access_token": create_access_token(user.id, self.settings),
            "token_type": "bearer",
            "user": serialize_user(user),
        }

    def login(self, email: str, password: str) -> dict[str, object]:
        """Authenticate a user and issue an access token."""

        normalized_email = email.strip().lower()
        user = self.user_repository.get_by_email(normalized_email)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")

        return {
            "access_token": create_access_token(user.id, self.settings),
            "token_type": "bearer",
            "user": serialize_user(user),
        }
