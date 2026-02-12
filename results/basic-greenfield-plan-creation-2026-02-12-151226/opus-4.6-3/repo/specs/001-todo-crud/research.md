# Research: Todo CRUD API

**Branch**: `001-todo-crud` | **Date**: 2025-02-12
**Phase**: 0 - Research

## Objective

Identify the best approach for building a RESTful Todo CRUD API with FastAPI and SQLite, aligned with the project constitution's principles of simplicity, type safety, and TDD.

## Technology Decisions

### 1. Web Framework: FastAPI

**Decision**: Use FastAPI as the web framework.

**Rationale**:
- Specified in the project constitution's technology stack
- Native async support (though SQLite operations are sync, FastAPI handles this gracefully)
- Built-in OpenAPI/Swagger documentation generation
- First-class Pydantic v2 integration for request/response validation
- Lightweight — minimal overhead for a simple CRUD API

**Version**: FastAPI 0.115+ (latest stable, Pydantic v2 native support)

### 2. Database Access: sqlite3 Standard Library

**Decision**: Use Python's built-in `sqlite3` module directly. No ORM.

**Rationale**:
- Constitution Principle I (Simplicity First): An ORM (SQLAlchemy, Tortoise) adds unnecessary abstraction for a single-table application
- SQLite is specified in the constitution's technology stack
- `sqlite3` is part of the Python standard library — zero additional dependencies
- Parameterized queries (`?` placeholders) satisfy the security requirement for no SQL injection
- For a single entity with 6 columns, raw SQL is more readable than ORM mapping

**Alternatives Rejected**:
- SQLAlchemy: Over-engineered for a single table; violates Simplicity First
- Tortoise ORM: Async ORM adds complexity without benefit (SQLite doesn't support true async)
- aiosqlite: Adds a dependency for minimal benefit in a low-concurrency local API

### 3. ID Generation: UUID v4

**Decision**: Generate UUID v4 identifiers server-side using Python's `uuid` module.

**Rationale**:
- Specified in FR-002 of the feature spec
- `uuid.uuid4()` is stdlib — no additional dependencies
- UUIDs prevent enumeration attacks and are safe for external exposure
- Store as TEXT in SQLite (SQLite has no native UUID type)

### 4. Validation: Pydantic v2

**Decision**: Use Pydantic v2 models for all request/response schemas.

**Rationale**:
- Specified in the constitution's technology stack
- FastAPI's native integration means validation happens automatically at the endpoint boundary
- Field validators handle length constraints (title: 1-500 chars, description: 0-2000 chars)
- Satisfies Constitution Principle V (Explicit Error Handling) — Pydantic returns structured validation errors

### 5. Testing: pytest + httpx

**Decision**: Use pytest as the test runner and httpx as the async test client.

**Rationale**:
- Specified in the constitution's technology stack
- httpx `ASGITransport` allows testing FastAPI without starting a real server
- pytest fixtures manage test database lifecycle (fresh DB per test)
- Constitution Principle III (TDD) requires tests written before implementation

### 6. Package Manager: uv

**Decision**: Use `uv` for dependency management and virtual environment.

**Rationale**:
- Specified in the constitution's technology stack
- Fast dependency resolution and installation
- Compatible with standard `pyproject.toml`

## Architecture Decisions

### Request/Response Flow

```
Client Request
    → FastAPI Router (routes.py)
        → Pydantic Validation (models.py)
            → Database Function (database.py)
                → SQLite
            ← Row Data
        ← Pydantic Response Model
    ← JSON Response
```

### Database Connection Strategy

**Decision**: Use a module-level connection factory with dependency injection.

- A `get_db()` function yields a `sqlite3.Connection` per request
- FastAPI's `Depends()` mechanism injects the connection into route handlers
- Connection is closed after each request via a generator pattern
- `row_factory = sqlite3.Row` enables dict-like access to query results
- Table creation happens at application startup via FastAPI lifespan

This avoids global mutable state (constitution requirement) while keeping the code simple.

### Error Handling Strategy

| Error Type | Handler | HTTP Status |
|------------|---------|-------------|
| Pydantic validation failure | FastAPI built-in | 422 → mapped to 400 |
| Todo not found | Custom `TodoNotFound` exception + handler | 404 |
| Invalid UUID format | Custom validator in Pydantic model | 400 |
| Database error | Generic exception handler with logging | 500 |

**Note**: FastAPI returns 422 for validation errors by default. A custom exception handler will map these to 400 to match the spec's expected status codes.

### File Organization Rationale

| File | Responsibility | Max Expected Size |
|------|---------------|-------------------|
| `main.py` | App factory, lifespan, middleware | ~30 lines |
| `models.py` | Pydantic schemas (3-4 models) | ~60 lines |
| `database.py` | Connection mgmt, CRUD queries (7 functions) | ~120 lines |
| `routes.py` | 7 endpoint handlers | ~100 lines |
| `exceptions.py` | 2-3 exception classes + handlers | ~30 lines |

All files well under the 300-line constitution limit. All functions well under the 30-line limit.

## Dependency List

### Runtime Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | >=0.115 | Web framework |
| uvicorn[standard] | >=0.30 | ASGI server |
| pydantic | >=2.0 | Data validation (transitive via FastAPI) |

### Development Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | >=8.0 | Test runner |
| httpx | >=0.27 | Async test client |
| ruff | >=0.5 | Linter and formatter |

**Total runtime dependencies**: 2 (FastAPI + uvicorn). SQLite and uuid are stdlib.

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SQLite locking under concurrent writes | Low | Low | Single-user local API; SQLite handles basic locking. Document in quickstart. |
| FastAPI 422 vs spec's 400 for validation | Certain | Low | Custom exception handler remaps RequestValidationError to 400. |
| datetime serialization inconsistency | Medium | Medium | Use ISO 8601 format consistently. Store as TEXT in SQLite, parse with `datetime.fromisoformat()`. |
