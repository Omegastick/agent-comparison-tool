# Implementation Plan: Todo CRUD API

**Branch**: `001-todo-crud` | **Date**: 2026-02-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `.specify/specs/001-todo-crud/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a RESTful Todo CRUD API using FastAPI and SQLite that allows users to create, read, update, delete, and mark todos as complete/incomplete. The implementation follows TDD principles with full type safety using Pydantic models, supporting 7 API endpoints with proper validation, error handling, and consistent JSON responses. All CRUD operations must complete in under 50ms for databases with <1000 todos.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: FastAPI, Pydantic v2, SQLite (built-in), httpx (testing)  
**Storage**: SQLite (file-based, local database file)  
**Testing**: pytest with httpx for API tests, TDD mandatory (Red-Green-Refactor)  
**Target Platform**: Linux server (ASGI application via uvicorn)  
**Project Type**: single (API-only backend service)  
**Performance Goals**: <50ms per CRUD operation for databases with <1000 todos  
**Constraints**: No external database dependencies, full type safety (no `Any` types), max 30 lines per function, max 300 lines per file  
**Scale/Scope**: 7 API endpoints, single resource (Todo), basic CRUD operations with completion tracking

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

✅ **Simplicity First**: Single resource (Todo), straightforward CRUD operations, no premature abstractions, SQLite for simplicity (no external DB)

✅ **Type Safety**: Using Pydantic models for all data structures, Python type hints required throughout

✅ **Test-Driven Development**: TDD explicitly mandated in constitution, tests written first for all functionality

✅ **RESTful Design**: All endpoints follow REST conventions (resources as nouns, HTTP verbs for actions)

✅ **Explicit Error Handling**: Proper HTTP status codes (200, 201, 204, 400, 404, 500), input validation on all endpoints

✅ **Technology Stack Compliance**: Python 3.11+, FastAPI, SQLite, Pydantic v2, pytest

✅ **Code Standards**: PEP 8, max 30 lines per function, max 300 lines per file, docstrings required

✅ **Security Requirements**: Input validation (length constraints), parameterized queries (SQLite), no sensitive data in logs

**Result**: All constitutional requirements satisfied. No violations to track.

## Project Structure

### Documentation (this feature)

```text
.specify/specs/001-todo-crud/
├── spec.md              # Feature specification (existing)
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (technology research, design patterns)
├── data-model.md        # Phase 1 output (database schema, Pydantic models)
├── quickstart.md        # Phase 1 output (setup instructions, running locally)
├── contracts/           # Phase 1 output (API contract tests)
│   ├── create_todo.md
│   ├── list_todos.md
│   ├── get_todo.md
│   ├── update_todo.md
│   ├── delete_todo.md
│   ├── complete_todo.md
│   └── incomplete_todo.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# Single project structure (Python backend API)

src/
├── todo_api/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── models.py            # Pydantic models (Todo request/response schemas)
│   ├── database.py          # SQLite database connection and table setup
│   ├── repository.py        # Data access layer (CRUD operations on database)
│   ├── service.py           # Business logic layer (validation, orchestration)
│   └── routes.py            # API route handlers (endpoints)

tests/
├── conftest.py              # pytest fixtures (test database, test client)
├── contract/                # Contract tests (API acceptance scenarios from spec)
│   ├── test_create_todo.py
│   ├── test_list_todos.py
│   ├── test_get_todo.py
│   ├── test_update_todo.py
│   ├── test_delete_todo.py
│   └── test_complete_todo.py
├── integration/             # Integration tests (database + service layer)
│   ├── test_repository.py
│   └── test_service.py
└── unit/                    # Unit tests (individual functions)
    ├── test_models.py
    └── test_validation.py

pyproject.toml               # Project dependencies and configuration (uv)
.gitignore                   # Ignore .venv, __pycache__, *.db, .pytest_cache
README.md                    # Project overview and quickstart guide
```

**Structure Decision**: Selected single project structure (Option 1) because this is a pure backend API with no frontend. The architecture uses a layered approach:
- **Routes layer**: HTTP request/response handling
- **Service layer**: Business logic and validation
- **Repository layer**: Database access (following repository pattern for testability)
- **Models layer**: Pydantic schemas for type safety and validation

This structure supports the constitutional requirements for simplicity (single project), type safety (Pydantic models), and testability (clear separation of concerns).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No violations to track. All design decisions align with constitutional principles.*

## Phase 0: Research

### Technology Research Required

1. **FastAPI Setup**: 
   - Application initialization with lifespan events
   - CORS configuration (if needed for future frontend)
   - Exception handlers for 400/404/500 responses
   - Response models for consistent JSON formatting

2. **SQLite Integration**:
   - Connection management (singleton pattern or context manager)
   - Schema creation on startup (CREATE TABLE IF NOT EXISTS)
   - UUID storage (TEXT or BLOB)
   - Datetime storage (ISO 8601 format in TEXT)
   - Transaction handling for data consistency

3. **Pydantic Models**:
   - Field validators (string length, non-empty title)
   - Response model excludes/includes
   - UUID serialization/deserialization
   - Datetime handling with timezone awareness

4. **Testing Strategy**:
   - pytest fixtures for test database (in-memory SQLite)
   - httpx TestClient for API testing
   - Database cleanup between tests
   - Factory functions for test data creation

### Design Patterns to Research

1. **Repository Pattern**: 
   - Separating data access from business logic
   - Benefits for testing (can mock repository)
   - Implementation in Python with SQLite

2. **Service Layer Pattern**:
   - Business logic separation from HTTP handlers
   - Validation coordination between Pydantic and custom rules
   - Error handling and exception translation

3. **Dependency Injection**:
   - FastAPI's Depends() for database connection
   - Using DI for repository/service in routes
   - Testing with overridden dependencies

### Open Questions for Phase 0

1. Should we use raw SQLite cursor or a lightweight ORM (like SQLModel)?
   - **Preference**: Raw SQLite (constitutional simplicity principle)
   - **Research**: Evaluate complexity trade-offs

2. How to handle database migrations for future schema changes?
   - **Initial approach**: Manual SQL in database.py
   - **Future consideration**: Simple migration script if needed

3. Should we implement pagination for GET /todos?
   - **Spec says**: No mention of pagination
   - **Decision**: Defer to Phase 1, validate performance with 1000 todos

4. What timestamp precision for created_at/completed_at?
   - **Preference**: ISO 8601 with milliseconds (e.g., "2026-02-12T15:30:45.123Z")
   - **Research**: Python datetime.utcnow() vs datetime.now(UTC)

## Phase 1: Design

### Data Model Design (data-model.md)

**Todo Entity**:
- Database schema (SQLite CREATE TABLE)
- Pydantic models:
  - `TodoCreate` (request body for POST /todos)
  - `TodoUpdate` (request body for PATCH /todos/{id})
  - `TodoResponse` (response body for all endpoints)
  - Internal `Todo` model (if needed for repository layer)

**Validation Rules**:
- Title: required, 1-500 characters, non-empty
- Description: optional, max 2000 characters
- ID: UUID v4 format validation
- Timestamps: UTC, ISO 8601 format

### API Contracts (contracts/ directory)

One contract file per user story (7 files total):
1. `create_todo.md` - POST /todos (scenarios 1-3 from spec)
2. `list_todos.md` - GET /todos (scenarios 1-3)
3. `get_todo.md` - GET /todos/{id} (scenarios 1-2)
4. `update_todo.md` - PATCH /todos/{id} (scenarios 1-3)
5. `delete_todo.md` - DELETE /todos/{id} (scenarios 1-3)
6. `complete_todo.md` - PATCH /todos/{id}/complete (scenarios 1-3)
7. `incomplete_todo.md` - PATCH /todos/{id}/incomplete (scenarios 1-2, derived)

Each contract includes:
- HTTP method and endpoint
- Request format (headers, body)
- Response format (status code, body structure)
- Error scenarios
- Example requests/responses

### Architecture Decisions

**Layered Architecture**:
```
HTTP Request → Routes → Service → Repository → Database
                  ↓         ↓          ↓
            Validation   Logic    Data Access
                  ↓         ↓          ↓
HTTP Response ← Serialization ← Results ← Queries
```

**Error Handling Strategy**:
- Custom exceptions: `TodoNotFoundError`, `ValidationError`
- FastAPI exception handlers translate to proper HTTP responses
- All errors logged with context (no stack traces in responses)

**Database Connection**:
- Singleton database connection initialized on app startup
- Lifespan context manager for setup/teardown
- Thread-safe SQLite configuration (check_same_thread=False for testing)

### Quickstart Guide (quickstart.md)

Documentation for:
1. Prerequisites (Python 3.11+, uv)
2. Installation steps
3. Database initialization
4. Running the development server
5. Running tests
6. Manual API testing (curl examples)

## Phase 2: Task Breakdown

**Note**: Detailed task breakdown will be generated in Phase 2 using `/speckit.tasks` command.

**High-Level Task Categories**:
1. Project setup (dependencies, structure, configuration)
2. Database layer (schema, connection, repository)
3. Models and validation (Pydantic schemas)
4. Service layer (business logic)
5. Routes and API handlers
6. Error handling and logging
7. Testing (contract, integration, unit)
8. Documentation (README, quickstart)

**Estimated Task Count**: 25-35 granular tasks

## Success Metrics

The implementation will be considered complete when:

1. ✅ All 7 API endpoints functional and tested
2. ✅ All 17 acceptance scenarios pass (from spec user stories)
3. ✅ All CRUD operations <50ms for databases with <1000 todos
4. ✅ 100% type coverage (no `Any` types)
5. ✅ All tests pass (contract + integration + unit)
6. ✅ Code adheres to constitution (PEP 8, max line/file lengths, docstrings)
7. ✅ Manual API testing verified (curl/httpx examples work)

## Next Steps

1. **Run `/speckit.plan` Phase 0**: Generate `research.md` with technology investigation results
2. **Run `/speckit.plan` Phase 1**: Generate `data-model.md`, `contracts/`, and `quickstart.md`
3. **Review and approve design**: Validate architecture decisions against constitution
4. **Run `/speckit.tasks`**: Generate detailed task breakdown in `tasks.md`
5. **Begin TDD implementation**: Start with first P1 feature (Create Todo)

## Notes

- This plan assumes no existing codebase (greenfield project)
- SQLite database file will be `todos.db` in repository root (gitignored)
- Test database will be in-memory (`:memory:`) for speed
- All timestamps stored in UTC, no timezone conversion needed
- Future enhancements (pagination, filtering) deferred to separate features
