# Implementation Plan: Todo CRUD API

**Branch**: `001-todo-crud` | **Date**: 2026-02-12 | **Spec**: `.specify/specs/001-todo-crud/spec.md`
**Input**: Feature specification from `.specify/specs/001-todo-crud/spec.md`

## Summary

Implement a RESTful CRUD API for managing todo items using Python 3.11+, FastAPI, and SQLite. The API exposes 7 endpoints (create, list, get, update, delete, mark complete, mark incomplete) with full input validation via Pydantic v2, UUID v4 identifiers, and persistent SQLite storage. Development follows strict TDD per the project constitution.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, uvicorn, Pydantic v2
**Storage**: SQLite (file-based, single `todos.db` file, no external dependencies)
**Testing**: pytest with httpx (async test client for FastAPI)
**Target Platform**: Linux server
**Project Type**: Single project (API-only, no frontend)
**Performance Goals**: All CRUD operations < 50ms for databases with < 1,000 todos (SC-003)
**Constraints**: No external database dependencies; SQLite file auto-created on startup
**Scale/Scope**: Single-user local API; < 1,000 todos target workload

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Simplicity First | PASS | Single project, single database file, no ORM (direct SQLite), no abstractions beyond what's needed |
| II. Type Safety | PASS | All models use Pydantic v2; all function signatures fully typed; no `Any` types |
| III. TDD (NON-NEGOTIABLE) | PASS | Tests written first using pytest + httpx; red-green-refactor enforced per task ordering |
| IV. RESTful Design | PASS | Resources are nouns (`/todos`), actions are HTTP verbs (GET, POST, PATCH, DELETE); proper status codes (200, 201, 204, 400, 404) |
| V. Explicit Error Handling | PASS | All validation errors return 400 with messages; 404 for missing resources; no silent failures |
| Code Standards (PEP 8/ruff) | PASS | Ruff configured for linting; max 30-line functions, max 300-line files |
| Security | PASS | Parameterized SQL queries (no injection); input validation at API boundary; no stack traces in responses |

No violations detected. Proceeding with implementation.

## Project Structure

### Documentation (this feature)

```text
specs/001-todo-crud/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── create-todo.md
│   ├── list-todos.md
│   ├── get-todo.md
│   ├── update-todo.md
│   ├── delete-todo.md
│   ├── complete-todo.md
│   └── incomplete-todo.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
pyproject.toml               # Project config (uv/pip, ruff, pytest)
src/
├── __init__.py
├── main.py                  # FastAPI app factory + uvicorn entrypoint
├── database.py              # SQLite connection management + table creation
├── models.py                # Pydantic request/response models
└── routes/
    ├── __init__.py
    └── todos.py             # All /todos endpoint handlers

tests/
├── __init__.py
├── conftest.py              # Shared fixtures (test client, temp database)
├── contract/
│   ├── __init__.py
│   └── test_todo_contracts.py   # Contract tests (request/response shape validation)
├── integration/
│   ├── __init__.py
│   └── test_todo_api.py         # Full API integration tests (all 7 endpoints)
└── unit/
    ├── __init__.py
    ├── test_models.py           # Pydantic model validation tests
    └── test_database.py         # Database layer unit tests
```

**Structure Decision**: Single project layout (Option 1 adapted for Python/FastAPI). This is an API-only project with no frontend. The `src/` directory contains application code organized by concern (models, database, routes). Tests are split into contract, integration, and unit layers per testing best practices. A flat `routes/` module is sufficient given the single-resource scope.

## Complexity Tracking

> No constitution violations detected. This section is intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_  | _(n/a)_    | _(n/a)_                             |
