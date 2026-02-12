# Implementation Plan: Todo CRUD API

**Branch**: `001-todo-crud` | **Date**: 2025-02-12 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-todo-crud/spec.md`

## Summary

Implement a RESTful Todo CRUD API using FastAPI with SQLite persistence. The API exposes 7 endpoints for creating, listing, retrieving, updating, deleting, and toggling completion status of todo items. All data is validated with Pydantic v2 models and persisted to a SQLite database. Development follows strict TDD (Red-Green-Refactor) per the project constitution, with pytest and httpx for testing.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, uvicorn, Pydantic v2
**Storage**: SQLite (file-based, no external dependencies)
**Testing**: pytest with httpx (async test client for FastAPI)
**Target Platform**: Linux server (local development)
**Project Type**: single
**Performance Goals**: All CRUD operations complete in under 50ms for databases with <1000 todos (SC-003)
**Constraints**: No external database dependencies; SQLite file auto-created on startup; parameterized queries only (no raw string interpolation)
**Scale/Scope**: Single-user local API; ~7 endpoints; 1 entity (Todo)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Single entity, single database, no abstractions beyond what FastAPI provides. Direct SQLite access via `sqlite3` stdlib — no ORM overhead. |
| II. Type Safety | PASS | Pydantic v2 models for all request/response schemas. Full type hints on all functions. No `Any` types needed. |
| III. TDD (Non-Negotiable) | PASS | Tests written first for each endpoint using pytest + httpx. Red-Green-Refactor cycle enforced per user story. |
| IV. RESTful Design | PASS | Resources as nouns (`/todos`, `/todos/{id}`). HTTP verbs for actions (POST, GET, PATCH, DELETE). Proper status codes (200, 201, 204, 400, 404). |
| V. Explicit Error Handling | PASS | Pydantic validation returns 400 with clear messages. 404 for missing resources. 500 handled by FastAPI with logging. No silent failures. |
| PEP 8 / ruff | PASS | All code formatted and linted with ruff. |
| Max 30-line functions | PASS | Each endpoint handler is a thin function delegating to a service layer. |
| Max 300-line files | PASS | Separated into models, database, routes, and main modules. |
| No global mutable state | PASS | Database connection managed via dependency injection. |
| No `*` imports | PASS | Explicit imports throughout. |
| Parameterized queries | PASS | All SQL uses `?` placeholders via `sqlite3` — no string interpolation. |

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
├── main.py              # FastAPI app creation, lifespan, router inclusion
├── models.py            # Pydantic request/response schemas (TodoCreate, TodoUpdate, TodoResponse)
├── database.py          # SQLite connection management, table creation, query functions
├── routes.py            # API endpoint handlers (7 endpoints)
└── exceptions.py        # Custom exception classes and handlers (TodoNotFound, ValidationError)

tests/
├── __init__.py
├── conftest.py          # Shared fixtures (test client, test database, sample todos)
├── test_create_todo.py  # US1: POST /todos
├── test_list_todos.py   # US2: GET /todos
├── test_get_todo.py     # US3: GET /todos/{id}
├── test_update_todo.py  # US4: PATCH /todos/{id}
├── test_delete_todo.py  # US5: DELETE /todos/{id}
├── test_complete_todo.py # US6: PATCH /todos/{id}/complete and /incomplete
└── test_edge_cases.py   # Edge cases: validation, invalid UUIDs, missing DB

pyproject.toml           # Project metadata, dependencies, ruff config, pytest config
```

**Structure Decision**: Single project structure selected. This is a standalone API with no frontend component. The `src/` directory contains all application code, organized by responsibility (models, database, routes). Tests mirror the user story structure from the spec for traceability.

## Complexity Tracking

> No constitution violations detected. All implementation decisions align with the five core principles and code standards.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *None* | — | — |
