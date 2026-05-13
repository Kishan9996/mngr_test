from __future__ import annotations


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AuthError(AppError):
    def __init__(self, message: str = "Authentication required.") -> None:
        super().__init__(message, status_code=401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "You do not have permission to perform this action.") -> None:
        super().__init__(message, status_code=403)


class NotFoundError(AppError):
    def __init__(self, resource: str) -> None:
        super().__init__(f"{resource} not found.", status_code=404)


class ConflictError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409)


class AIServiceError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(f"AI service error: {message}", status_code=503)


class DataServiceError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class SessionNotFoundError(AppError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session '{session_id}' not found.", status_code=404)
