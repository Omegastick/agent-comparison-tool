# Implementation Plan: Todo CRUD API

**Branch**: `001-todo-crud` | **Date**: 2026-02-12 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-todo-crud/spec.md`

## Summary

Build a RESTful Todo CRUD API using FastAPI with SQLite persistence. The API exposes 7 endpoints for creating, listing, reading, updating, deleting, and toggling completion status of todo items. Each todo has a UUID v4 identifier, title (1-500 chars), optional description (max 2000 chars), completion status, and timestamps. All inputs are validated via Pydantic v2 models, and the project follows strict TDD with pytest + httpx.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, uvicorn, Pydantic v2
**Storage**: SQLite (file-based, auto-created on startup)
**Testing**: pytest with httpx (async test client for FastAPI)
**Target Platform**: Linux server
**Project Type**: Single project (API-only, no frontend)
**Performance Goals**: All CRUD operations complete in <50ms for databases with <1000 todos
**Constraints**: No external database dependencies; SQLite file-based storage only
**Scale/Scope**: Single-user local API; <1000 todos target dataset

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Single project, no abstractions beyond basic service layer. Direct SQLite access via stdlib `sqlite3`. No ORM. |
| II. Type Safety | PASS | All models defined as Pydantic v2 `BaseModel`. Full type hints on all functions. No `Any` types. |
| III. TDD (Non-Negotiable) | PASS | Tests written first using pytest + httpx `AsyncClient`. Red-Green-Refactor enforced per user story. |
| IV. RESTful Design | PASS | Resources are nouns (`/todos`, `/todos/{id}`). Actions via HTTP verbs (POST, GET, PATCH, DELETE). Consistent JSON responses. |
| V. Explicit Error Handling | PASS | Pydantic validates all inputs at API boundary. Custom exception handlers for 400/404/500. No silent failures. |
| Code Standards | PASS | PEP 8 via ruff. Max 30-line functions. Max 300-line files. Docstrings on all public functions. No `*` imports. No global mutable state. |
| Security | PASS | Parameterized SQL queries (no string interpolation). Input validation on all endpoints. No sensitive data in logs. No stack traces in production. |

**No violations detected. Proceeding to implementation.**

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
src/
├── __init__.py
├── main.py              # FastAPI app creation, lifespan, middleware
├── models.py            # Pydantic request/response models
├── database.py          # SQLite connection management, table creation
├── routes.py            # API route handlers (/todos endpoints)
└── errors.py            # Custom exception classes and handlers

tests/
├── __init__.py
├── conftest.py          # Shared fixtures (test client, test database)
├── test_create_todo.py  # User Story 1 tests
├── test_list_todos.py   # User Story 2 tests
├── test_get_todo.py     # User Story 3 tests
├── test_update_todo.py  # User Story 4 tests
├── test_delete_todo.py  # User Story 5 tests
└── test_complete_todo.py # User Story 6 tests

pyproject.toml           # Project config, dependencies, ruff config
```

**Structure Decision**: Single project layout selected. This is an API-only project with no frontend. The `src/` directory contains all application code organized by concern (models, database, routes, errors). Tests are organized by user story to align with the spec and enable incremental TDD implementation. No subdirectories within `src/` beyond flat modules, keeping maximum simplicity per Constitution Principle I.

## Complexity Tracking

> No Constitution violations detected. This section is intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *(none)* | | |
