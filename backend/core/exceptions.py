"""Application-specific exceptions."""

from __future__ import annotations


class ApiError(Exception):
    """Base API exception with HTTP status and stable error code."""

    def __init__(self, message: str, *, status_code: int, error_code: str) -> None:
        """Initialize an API error."""

        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class AuthenticationError(ApiError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed") -> None:
        """Initialize an authentication error."""

        super().__init__(message, status_code=401, error_code="authentication_failed")


class AuthorizationError(ApiError):
    """Raised when a user attempts to access unauthorized resources."""

    def __init__(self, message: str = "You are not allowed to access this resource") -> None:
        """Initialize an authorization error."""

        super().__init__(message, status_code=403, error_code="access_denied")


class ConflictError(ApiError):
    """Raised when a resource conflicts with existing data."""

    def __init__(self, message: str) -> None:
        """Initialize a conflict error."""

        super().__init__(message, status_code=409, error_code="resource_conflict")


class NotFoundError(ApiError):
    """Raised when a resource cannot be found."""

    def __init__(self, message: str) -> None:
        """Initialize a not found error."""

        super().__init__(message, status_code=404, error_code="resource_not_found")


class ValidationError(ApiError):
    """Raised when user input fails domain validation."""

    def __init__(self, message: str) -> None:
        """Initialize a validation error."""

        super().__init__(message, status_code=400, error_code="validation_error")
