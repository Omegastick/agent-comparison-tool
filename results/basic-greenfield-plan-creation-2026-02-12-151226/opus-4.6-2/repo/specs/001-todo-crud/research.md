# Research: Todo CRUD API

**Feature**: 001-todo-crud | **Date**: 2026-02-12

## Technology Decisions

### FastAPI + Uvicorn

FastAPI is the framework specified by the constitution. It provides automatic OpenAPI documentation, native async support, and tight Pydantic v2 integration for request/response validation. Uvicorn serves as the ASGI server.

**Key considerations**:
- FastAPI's `APIRouter` will group all `/todos` endpoints in a single router module
- Dependency injection via `Depends()` for database connections
- Built-in request validation via Pydantic model type annotations on route parameters
- Automatic 422 responses for malformed requests (FastAPI default); we override to return 400 per spec requirements

### SQLite (stdlib `sqlite3`)

The constitution mandates SQLite with no external dependencies. Python's built-in `sqlite3` module is sufficient.

**Key considerations**:
- No ORM (aligns with Simplicity First principle) -- direct parameterized SQL queries
- Connection-per-request pattern via FastAPI dependency injection
- WAL mode for better concurrent read performance (though single-user scope makes this low priority)
- Database file auto-created on first connection if missing (FR: "Database file missing on startup: Create it automatically")
- `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON` set on connection

### UUID v4 for Primary Keys

Per FR-002, each todo gets a UUID v4. Generated in Python using `uuid.uuid4()` and stored as TEXT in SQLite.

**Trade-offs considered**:
- UUID as TEXT vs. BLOB: TEXT chosen for simplicity and debuggability; 36 bytes vs 16 bytes storage is negligible at < 1,000 rows
- Server-generated (not client-supplied) to prevent collisions and maintain control

### Pydantic v2 Models

Four models needed:
- `TodoCreate` -- request body for POST (title required, description optional)
- `TodoUpdate` -- request body for PATCH (title optional, description optional, all fields `None` by default)
- `TodoResponse` -- response body for all endpoints returning a Todo
- `TodoListResponse` -- response body wrapping a list of `TodoResponse` (or just `list[TodoResponse]`)

**Validation rules** (from spec edge cases):
- `title`: `str`, `min_length=1`, `max_length=500`
- `description`: `str | None`, `max_length=2000`, default `None`

### Testing Strategy

Per constitution: TDD is NON-NEGOTIABLE. Tests written first.

**Layers**:
1. **Unit tests** (`tests/unit/`): Pydantic model validation, database CRUD functions in isolation
2. **Contract tests** (`tests/contract/`): Verify request/response shapes match the API contract documents
3. **Integration tests** (`tests/integration/`): Full HTTP round-trip via `httpx.AsyncClient` with FastAPI's `TestClient`

**Fixtures**:
- Temporary SQLite database per test (`:memory:` or `tmp_path`)
- `httpx.AsyncClient` configured with the FastAPI app
- Auto-cleanup between tests

### Error Handling Strategy

- Invalid UUID format in path: Return 400 (not 404) -- requires explicit path parameter validation
- Validation errors (empty title, too-long fields): Pydantic raises `ValidationError`, caught by custom exception handler returning 400
- Resource not found: Return 404 with `{"detail": "Todo not found"}`
- FastAPI's default 422 for validation errors will be remapped to 400 to match spec

### Package Management

`uv` as specified by constitution. Project defined via `pyproject.toml` with:
- Runtime dependencies: `fastapi`, `uvicorn[standard]`
- Dev dependencies: `pytest`, `httpx`, `pytest-asyncio`, `ruff`

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SQLite locking under concurrent writes | Low (single-user) | Low | WAL mode; last-write-wins per spec |
| FastAPI 422 vs spec 400 for validation | Certain | Medium | Custom exception handler to remap ValidationError to 400 |
| UUID validation in path params | Medium | Low | Custom path parameter validator or regex constraint |

## Open Questions

None. The spec and constitution provide sufficient detail to proceed with implementation.
