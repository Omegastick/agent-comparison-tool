# Implementation Plan: Todo CRUD API

**Branch**: `001-todo-crud` | **Date**: 2026-02-12 | **Spec**: specs/001-todo-crud/spec.md
**Input**: Feature specification from `specs/001-todo-crud/spec.md`

## Summary

Implement a RESTful Todo CRUD API with 7 endpoints using FastAPI and SQLite. Follow the constitution: strict type hints via Pydantic, TDD-first with pytest/httpx, explicit error handling, consistent JSON responses, and no global mutable state. Performance target: all CRUD operations complete in <50ms for <1000 todos.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: FastAPI, Pydantic v2, Uvicorn, pytest, httpx, ruff  
**Storage**: SQLite (file-based), `sqlite3` stdlib with parameterized queries  
**Testing**: pytest with httpx async client; TDD (red-green-refactor)  
**Target Platform**: Linux server (container-friendly)  
**Project Type**: single backend project  
**Performance Goals**: CRUD ops <50ms for <1000 todos; predictable latency  
**Constraints**: Full type safety, RESTful design, explicit error mapping (400/404/500), PEP8 enforced by ruff, functions <=30 lines, files <=300 lines, docstrings on public functions  
**Scale/Scope**: Single service, small dataset (<1000 todos), simple concurrency (SQLite locking acceptable)

## Constitution Check

Gates to satisfy before implementation:
- TDD: write failing tests for all endpoints before implementation; acceptance scenarios drive tests.
- Type Safety: use Python type hints everywhere and Pydantic models for request/response.
- RESTful Design: resource-oriented endpoints, proper HTTP methods/status codes.
- Explicit Error Handling: return meaningful messages; validate inputs (UUID format, title/description length).
- Security: parameterized SQL only; no sensitive data in logs.
- Code Standards: PEP8 via ruff; no wildcard imports; no global mutable state; docstrings required.

## Project Structure

### Documentation (this feature)

```text
specs/001-todo-crud/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
```

### Source Code (repository root)

```text
src/
├── api/
│   └── todos.py          # FastAPI router/endpoints
├── lib/
│   └── db.py             # SQLite connection + migrations
├── models/
│   └── todo.py           # Pydantic models (request/response)
└── services/
    └── todo_service.py   # CRUD + business rules

tests/
├── contract/
│   └── test_todos_contract.py
├── integration/
│   └── test_todos_integration.py
└── unit/
    └── test_todo_service.py
```

**Structure Decision**: Single backend project with clear separation: API layer (FastAPI routers), service layer (CRUD/validation), models (Pydantic), and lib (DB). Tests organized by level: contract (spec-driven), integration (API + DB), unit (services).

## Complexity Tracking

No constitution violations anticipated. Repository pattern kept minimal; direct service functions over heavy abstractions.
