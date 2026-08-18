# Bearer Token Authentication & Middleware Guide

This document describes the Bearer Token authentication and middleware system implemented in the **arXiv Paper Curator API**.

---

## Overview

The authentication layer protects API endpoints using the standard HTTP **Bearer Token** authentication scheme (RFC 6750). It intercepts incoming requests globally via FastAPI/Starlette middleware, validates credentials, enforces security rules, and attaches the authenticated context to `request.state.user`.

### Key Features

- **Global Request Interception**: Validates all incoming requests before reaching route handlers.
- **Configurable Whitelisting**: Allows public routes (e.g., OpenAPI docs, health checks) to bypass authentication.
- **RFC 6750 Compliant**: Returns standard `401 Unauthorized` responses with `WWW-Authenticate: Bearer` headers.
- **Environment Toggle**: Can be enabled or disabled via environment variables (`AUTH__ENABLED=true/false`).
- **Flexible Verification**: Supports static API tokens out-of-the-box, with support for custom verification functions (e.g., JWT decoding, database lookups).
- **FastAPI Dependency Integration**: Provides `AuthenticatedUserDep` for accessing the current user in route handlers.

---

## Architecture & Request Flow

```mermaid
flowchart TD
    A["Incoming HTTP Request"] --> B["RequestLoggingMiddleware"]
    B --> C["BearerTokenAuthMiddleware"]
    C --> D{"Is Auth Enabled?"}
    D -- No --> H["Route Handler"]
    D -- Yes --> E{"Is Path Excluded?<br/>(/docs, /api/v1/ping, etc.)"}
    E -- Yes --> H
    E -- No --> F{"Has 'Authorization: Bearer <token>'?"}
    F -- No / Invalid Scheme --> G1["401 Unauthorized<br/>Missing/Invalid Scheme"]
    F -- Yes --> J{"Verify Token<br/>(Static / JWT / Custom)"}
    J -- Invalid --> G2["401 Unauthorized<br/>Invalid Token"]
    J -- Valid --> K["Attach User to request.state.user<br/>& request.state.token"]
    K --> H
    H --> L["HTTP Response"]
    L --> B
```

---

## Configuration

Authentication is configured via `src/config.py` using Pydantic Settings under the `AUTH__` prefix.

### Environment Variables (`.env`)

```bash
# Enable or disable authentication globally (default: false)
AUTH__ENABLED=true

# Static Bearer token for API requests
AUTH__SECRET_TOKEN=my-super-secret-api-token-123

# Optional JWT settings (for future JWT extensions)
AUTH__JWT_SECRET_KEY=your-jwt-secret-key-32-chars-minimum
AUTH__JWT_ALGORITHM=HS256
```

### Config Class (`src/config.py`)

```python
class AuthSettings(BaseConfigSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        env_prefix="AUTH__",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    enabled: bool = False
    secret_token: str = ""
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
```

---

## Components

### 1. `BearerTokenAuthMiddleware` (`src/middlewares.py`)

Handles request interception, header parsing, path exclusion matching, and token validation.

```python
class BearerTokenAuthMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        enabled: bool = True,
        secret_token: Optional[str] = None,
        verify_token_func: Optional[Callable[[str], Optional[dict | bool]]] = None,
        excluded_paths: Optional[Iterable[str]] = None,
    ):
        ...
```

#### Default Excluded Paths

The following paths are excluded from authentication by default:

- `/docs` (Swagger UI)
- `/redoc` (ReDoc)
- `/openapi.json` (OpenAPI Schema)
- `/api/v1/ping` (Health check)
- `/favicon.ico`

### 2. Application Registration (`src/main.py`)

Middlewares are registered in `src/main.py`:

```python
from src.config import get_settings
from src.middlewares import BearerTokenAuthMiddleware, RequestLoggingMiddleware

app_settings = get_settings()

app = FastAPI(title="arXiv Paper Curator API", lifespan=lifespan)

# Register Bearer Token Authentication Middleware
app.add_middleware(
    BearerTokenAuthMiddleware,
    enabled=app_settings.auth.enabled,
    secret_token=app_settings.auth.secret_token,
    excluded_paths={"/docs", "/redoc", "/openapi.json", "/api/v1/ping"},
)

# Register Request Logging Middleware (wraps outer execution)
app.add_middleware(RequestLoggingMiddleware)
```

> **Note on Middleware Execution Order:**
> In Starlette/FastAPI, middlewares execute in reverse order of addition. `RequestLoggingMiddleware` runs first, timing the request and logging the final response status (including 401s), before passing execution to `BearerTokenAuthMiddleware`.

### 3. Route Handler Dependency (`src/dependencies.py`)

Route handlers can access authenticated user data using the `AuthenticatedUserDep` dependency:

```python
# src/dependencies.py
def get_current_user(request: Request) -> Optional[dict]:
    """Get authenticated user data from request state populated by BearerTokenAuthMiddleware."""
    return getattr(request.state, "user", None)

AuthenticatedUserDep = Annotated[Optional[dict], Depends(get_current_user)]
```

#### Usage in Route Handlers:

```python
from fastapi import APIRouter
from src.dependencies import AuthenticatedUserDep

router = APIRouter()

@router.get("/profile")
async def get_user_profile(user: AuthenticatedUserDep):
    return {"message": "Authenticated successfully", "user": user}
```

---

## API Usage & Examples

### 1. Successful Request

Send an HTTP request with the `Authorization` header containing `Bearer <token>`:

```bash
curl -X GET "http://localhost:8000/api/v1/ask" \
     -H "Authorization: Bearer my-super-secret-api-token-123" \
     -H "Content-Type: application/json" \
     -d '{"query": "attention mechanism", "model": "llama3.2:latest"}'
```

### 2. Error Responses

#### A. Missing Authorization Header (`401 Unauthorized`)

**Request:**

```bash
curl -X GET "http://localhost:8000/api/v1/ask"
```

**Response:**

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer
Content-Type: application/json

{
  "error": "Unauthorized",
  "detail": "Missing Authorization header"
}
```

#### B. Invalid Authorization Scheme (`401 Unauthorized`)

**Request:**

```bash
curl -X GET "http://localhost:8000/api/v1/ask" \
     -H "Authorization: Basic dXNlcjpwYXNz"
```

**Response:**

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer error="invalid_token"
Content-Type: application/json

{
  "error": "Unauthorized",
  "detail": "Invalid authentication scheme, expected 'Bearer <token>'"
}
```

#### C. Invalid or Expired Token (`401 Unauthorized`)

**Request:**

```bash
curl -X GET "http://localhost:8000/api/v1/ask" \
     -H "Authorization: Bearer wrong-token"
```

**Response:**

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer error="invalid_token"
Content-Type: application/json

{
  "error": "Unauthorized",
  "detail": "Invalid or expired token"
}
```

---

## Customizing Token Verification (e.g. JWT)

To support JWT verification or database session checks, provide a custom `verify_token_func` callback to `BearerTokenAuthMiddleware`:

```python
import jwt
from fastapi import FastAPI
from src.middlewares import BearerTokenAuthMiddleware

def verify_jwt_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, "your-secret-key", algorithms=["HS256"])
        return payload  # Attached to request.state.user
    except jwt.PyJWTError:
        return None

app = FastAPI()
app.add_middleware(
    BearerTokenAuthMiddleware,
    enabled=True,
    verify_token_func=verify_jwt_token,
    excluded_paths={"/docs", "/openapi.json", "/api/v1/ping"},
)
```

---

## Testing

Unit tests for the middleware are located at [`tests/unit/test_middlewares.py`](../tests/unit/test_middlewares.py).

To run the middleware tests:

```bash
pytest tests/unit/test_middlewares.py -vv
```
