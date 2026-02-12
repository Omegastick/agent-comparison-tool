# Research: Todo CRUD API

**Feature**: `001-todo-crud` | **Date**: 2026-02-12 | **Phase**: 0

## Technology Decisions

### FastAPI + Uvicorn

FastAPI is the framework specified in the constitution. It provides automatic OpenAPI/Swagger documentation, native async support, and Pydantic integration for request/response validation. Uvicorn serves as the ASGI server.

**Version constraints**: FastAPI 0.100+ (for Pydantic v2 native support).

### SQLite via stdlib `sqlite3`

The constitution specifies SQLite with no external dependencies. Python's built-in `sqlite3` module provides everything needed:

- Parameterized queries for SQL injection prevention (constitution security requirement)
- WAL mode for better concurrent read performance
- Auto-creation of database file on first connection

**Decision**: Use `sqlite3` directly rather than an ORM (e.g., SQLAlchemy). Rationale:
- Constitution Principle I (Simplicity First): An ORM adds abstraction without justification for 1 table and 7 queries
- Total SQL queries needed: 7 (INSERT, SELECT all, SELECT by ID, UPDATE, DELETE, UPDATE complete, UPDATE incomplete)
- Each query is a simple single-table operation with no joins

### Pydantic v2 Models

Pydantic v2 is specified in the constitution. It handles:

- Request body validation (title length 1-500, description max 2000)
- Response serialization (consistent JSON format across endpoints)
- UUID validation for path parameters
- Type coercion and error message generation

### pytest + httpx

The constitution mandates pytest for testing. `httpx.AsyncClient` provides a test client that can call FastAPI endpoints without starting a real server, enabling fast integration tests.

**Test database strategy**: Each test function gets a fresh in-memory SQLite database (`:memory:`) injected via FastAPI dependency override. This ensures test isolation without filesystem side effects.

### uv Package Manager

The constitution specifies `uv` for package management. This provides fast dependency resolution and lockfile-based reproducible builds.

## Key Design Decisions

### UUID Generation

UUIDs are generated server-side using Python's `uuid.uuid4()`. The spec requires UUID v4 (FR-002). UUIDs are stored as TEXT in SQLite (SQLite has no native UUID type).

### Timestamp Handling

All timestamps are UTC, stored as ISO 8601 TEXT in SQLite. Python's `datetime.datetime.now(datetime.UTC)` generates them. This avoids timezone ambiguity and provides human-readable database inspection.

### Error Response Format

Consistent error response structure across all endpoints:

```json
{
  "detail": "Human-readable error message"
}
```

This aligns with FastAPI's default `HTTPException` format, requiring no custom error response models.

### Database Connection Management

A single module (`database.py`) manages:
- Connection creation with WAL mode enabled
- Table creation (idempotent `CREATE TABLE IF NOT EXISTS`)
- Connection lifecycle tied to FastAPI lifespan events

No connection pooling needed for SQLite (single-file database with built-in locking).

### Input Validation Strategy

Validation happens at two levels:
1. **Pydantic models** (API boundary): Type checking, string length constraints, required/optional fields
2. **Database layer**: UUID format validation before query execution (returns 400, not 404, per spec edge cases)

### PATCH Semantics

PATCH endpoints accept partial updates. Only fields present in the request body are updated. This is implemented by checking `exclude_unset=True` on the Pydantic model, then building a dynamic UPDATE query for only the provided fields.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| SQLite file locking under concurrent writes | Low (single-user API) | WAL mode enabled; constitution accepts "last write wins" |
| Database file missing on startup | None | Auto-created by `sqlite3.connect()` and `CREATE TABLE IF NOT EXISTS` |
| Large response payloads with many todos | Low (<1000 todos target) | No pagination needed per spec; monitor if scope changes |

## Out of Scope

- Authentication/authorization (not in spec)
- Pagination (spec targets <1000 todos)
- Filtering/sorting parameters (spec only requires created_at DESC ordering)
- Database migrations (single table, no schema evolution needed for v1)
- Docker/containerization (not in spec)
- CI/CD configuration (not in spec)
