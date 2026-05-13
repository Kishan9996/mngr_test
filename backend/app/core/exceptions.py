class AppError(Exception):
    """Base application error — all custom exceptions inherit from this."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class CalendarAuthError(AppError):
    """Raised when a calendar OAuth token is missing, expired, or invalid."""

    def __init__(self, provider: str, message: str = "") -> None:
        detail = message or f"Calendar '{provider}' is not connected or the token has expired."
        super().__init__(detail, status_code=401)
        self.provider = provider


class CalendarAPIError(AppError):
    """Raised when a calendar provider API call fails."""

    def __init__(self, provider: str, message: str) -> None:
        super().__init__(f"[{provider}] {message}", status_code=502)
        self.provider = provider


class SlotNotAvailableError(AppError):
    """Raised when the requested slot is no longer free at booking time."""

    def __init__(self) -> None:
        super().__init__("The selected time slot is no longer available.", status_code=409)


class SessionNotFoundError(AppError):
    """Raised when a session ID does not exist in the session store."""

    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session '{session_id}' not found.", status_code=404)


class AIServiceError(AppError):
    """Raised when the Claude API call fails."""

    def __init__(self, message: str) -> None:
        super().__init__(f"AI service error: {message}", status_code=503)


class UnsupportedProviderError(AppError):
    """Raised when an unknown calendar provider is requested."""

    def __init__(self, provider: str) -> None:
        super().__init__(f"Unsupported calendar provider: '{provider}'.", status_code=400)
