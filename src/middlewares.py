import logging
import time
from collections.abc import Callable, Iterable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Default public paths that do not require authentication
DEFAULT_EXCLUDED_PATHS: set[str] = {
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/ping",
    "/favicon.ico",
}


def log_request(method: str, path: str) -> None:
    """Log incoming request."""
    logger.info(f"{method} {path}")


def log_error(error: str, method: str, path: str) -> None:
    """Log error during request processing."""
    logger.error(f"Error in {method} {path}: {error}")


class BearerTokenAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that intercepts incoming HTTP requests, validates the 'Authorization: Bearer <token>'
    header, attaches the validated payload/user to `request.state.user`, and rejects unauthorized requests.
    """

    def __init__(
        self,
        app,
        enabled: bool = True,
        secret_token: str | None = None,
        verify_token_func: Callable[[str], dict | bool | None] | None = None,
        excluded_paths: Iterable[str] | None = None,
    ):
        super().__init__(app)
        self.enabled = enabled
        self.secret_token = secret_token
        self.verify_token_func = verify_token_func
        self.excluded_paths = set(
            excluded_paths if excluded_paths is not None else DEFAULT_EXCLUDED_PATHS
        )

    def _is_path_excluded(self, path: str) -> bool:
        """Check if path is in the whitelist or starts with an excluded prefix."""
        if path in self.excluded_paths:
            return True
        return any(
            path.startswith(prefix.rstrip("/") + "/")
            for prefix in self.excluded_paths
            if prefix != "/"
        )

    def _verify_token(self, token: str) -> dict | None:
        """
        Validate the bearer token.
        Supports custom validation function (e.g. JWT) or static secret token matching.
        """
        if self.verify_token_func:
            result = self.verify_token_func(token)
            if result is True:
                return {"authenticated": True, "token": token}
            return result if isinstance(result, dict) else None

        if self.secret_token and token == self.secret_token:
            return {"authenticated": True, "token": token}

        return None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # If auth is globally disabled or if request is for a public path, skip auth
        if not self.enabled or self._is_path_excluded(request.url.path):
            return await call_next(request)

        # Extract Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "detail": "Missing Authorization header",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate Bearer scheme format
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "detail": "Invalid authentication scheme, expected 'Bearer <token>'",
                },
                headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
            )

        token = parts[1]

        # Verify token validity
        user_data = self._verify_token(token)
        if not user_data:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Unauthorized", "detail": "Invalid or expired token"},
                headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
            )

        # Attach auth context to request state for downstream handlers
        request.state.user = user_data
        request.state.token = token

        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging incoming requests, response status codes, and execution duration.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        log_request(request.method, request.url.path)

        try:
            response = await call_next(request)
            process_time = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"{request.method} {request.url.path} completed with status {response.status_code} in {process_time:.2f}ms"
            )
            return response
        except Exception as exc:
            log_error(str(exc), request.method, request.url.path)
            raise
