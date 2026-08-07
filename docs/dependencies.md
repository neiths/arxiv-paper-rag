# Dependencies — why you need them

This project centralizes FastAPI dependency providers in src/dependencies.py. Dependencies are small, testable factories that provide resources (settings, DB sessions, clients, services) to route handlers and other services. They improve modularity, lifecycle control, and testability.

## Key benefits

- Decoupling: handlers receive ready-to-use objects instead of constructing them, keeping handlers focused on business logic.
- Lifecycle management: a dependency can open/close resources (e.g., DB session) and ensure cleanup via generator/yield semantics.
- Reuse: a single provider (e.g., OpenSearch client) is created once and used by many handlers.
- Testability: dependencies can be overridden in tests to inject mocks.
- Clear typing: using Annotated + Depends makes types explicit for editors and static analysis.

## What the file provides (quick map)

- get_settings (cached): returns configured Settings (lru_cache ensures a single global instance).
- get_request_settings: reads Settings from request.app.state (per-app init).
- get_database / get_db_session: provide BaseDatabase and a scoped Session using `with database.get_session(): yield session`.
- get_*_client / get_*_service: return app-level singletons stored on request.app.state (OpenSearchClient, ArxivClient, PDFParserService, JinaEmbeddingsClient, OllamaClient, LangfuseTracer).
- get_cache_client / get_telegram_service: optional getters using getattr(..., None).
- Predefined Annotated aliases (SettingsDep, SessionDep, OpenSearchDep, etc.) for concise route signatures.

## How to use in routes

Example signature using the annotated deps:
```python
# filepath: /home/thienhb/Workspace/arxiv-paper-rag/src/api/search.py
from fastapi import APIRouter
from src.dependencies import SessionDep, OpenSearchDep, SettingsDep

router = APIRouter()

@router.get("/search")
def search(
    db: SessionDep,
    opensearch: OpenSearchDep,
    settings: SettingsDep,
):
    # use db, opensearch, settings...
    ...
```

Or explicit Depends:
```python
from fastapi import Depends
def search(db = Depends(get_db_session)):
    ...
```

## Best practices

- Keep dependency functions small and side-effect free; do initialization in app startup and store on app.state.
- Use context-managed generators for resources that must be cleaned up (DB sessions, transactions).
- Use lru_cache for expensive global singletons (Settings).
- Override dependencies in tests via FastAPI's app.dependency_overrides.
- Prefer request.app.state for objects created during app startup (clients, services) rather than creating them per-request.
- Keep dependencies synchronous unless the resource requires async cleanup.

## Testing tips

- In tests, replace critical deps with lightweight mocks:
  app.dependency_overrides[get_db_session] = lambda: test_session
- For app-level objects (app.state.*), set them directly on the test app instance before sending requests.

## Adding a new dependency

1. Add a provider in src/dependencies.py that returns the resource (or yields for cleanup).
2. If it is app-scoped, create the instance at startup and attach to app.state.
3. Add an Annotated alias for concise route typing if useful.

This approach keeps resource wiring centralized, predictable, and easy to reason about across the codebase.