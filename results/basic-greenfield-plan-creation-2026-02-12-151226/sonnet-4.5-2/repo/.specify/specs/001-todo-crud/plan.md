# Implementation Plan: Todo CRUD API

**Branch**: `001-todo-crud` | **Date**: 2026-02-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `.specify/specs/001-todo-crud/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a RESTful Todo CRUD API with FastAPI and SQLite that allows users to create, read, update, delete, and track completion status of todo items. The API will provide 7 endpoints following REST conventions with full input validation, proper error handling, and comprehensive test coverage.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: FastAPI, Pydantic v2, SQLite3 (stdlib)  
**Storage**: SQLite (file-based, local database at `todos.db`)  
**Testing**: pytest with httpx for API tests, pytest-cov for coverage  
**Target Platform**: Linux server (FastAPI with uvicorn)  
**Project Type**: Single project (backend API only)  
**Performance Goals**: <50ms response time for operations with <1000 todos  
**Constraints**: No external database dependencies, TDD mandatory, 100% type coverage  
**Scale/Scope**: 7 API endpoints, ~500-1000 LOC, single resource (Todo)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

✓ **Simplicity First**: Single resource CRUD with no premature abstractions  
✓ **Type Safety**: Python 3.11+ with full type hints, Pydantic models  
✓ **TDD (NON-NEGOTIABLE)**: All acceptance scenarios become pytest tests  
✓ **RESTful Design**: 7 endpoints follow REST conventions with proper HTTP verbs  
✓ **Explicit Error Handling**: All validation errors return 400, not-found returns 404  
✓ **Technology Stack**: FastAPI + SQLite + Pydantic v2 + pytest + uv  
✓ **Code Standards**: PEP 8 via ruff, max 30 lines/function, max 300 lines/file  
✓ **Security**: Input validation at boundaries, parameterized SQL queries

**Constitution Status**: ✅ PASS - All principles satisfied

## Project Structure

### Documentation (this feature)

```text
.specify/specs/001-todo-crud/
├── spec.md              # User scenarios & requirements (EXISTS)
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# Single project structure (Python FastAPI)
src/
├── models/
│   ├── __init__.py
│   └── todo.py          # Pydantic models for Todo (request/response schemas)
├── services/
│   ├── __init__.py
│   └── todo_service.py  # Business logic for CRUD operations
├── database/
│   ├── __init__.py
│   ├── connection.py    # SQLite connection management
│   └── schema.sql       # Database schema initialization
├── api/
│   ├── __init__.py
│   └── routes.py        # FastAPI route handlers
└── main.py              # Application entry point

tests/
├── conftest.py          # pytest fixtures (test DB, client, etc.)
├── contract/
│   └── test_api_contract.py  # Contract tests for all 7 endpoints
├── integration/
│   └── test_todo_crud.py      # Integration tests for complete workflows
└── unit/
    ├── test_models.py         # Unit tests for Pydantic models
    └── test_service.py        # Unit tests for service layer

pyproject.toml           # uv project configuration
README.md                # Setup and usage instructions
todos.db                 # SQLite database file (gitignored)
```

**Structure Decision**: Single project structure chosen because this is a simple backend API with one resource (Todo). No frontend, no multiple services, no platform-specific code. All source code lives in `src/` following standard Python package layout with clear separation of concerns (models, services, database, API routes).

## Complexity Tracking

> **No violations detected** - This feature fully complies with the constitution.

## Phase 0: Research

**Objective**: Validate technical approach and identify FastAPI + SQLite patterns for CRUD operations.

### Research Questions

1. **FastAPI + SQLite Integration**: How to properly manage SQLite connections in FastAPI (lifecycle, connection pooling, dependency injection)?
2. **Pydantic Model Design**: Best practices for request/response models vs database models in FastAPI?
3. **Testing Strategy**: How to set up test fixtures for isolated database testing with pytest and httpx?
4. **UUID Primary Keys**: Best approach for UUID generation and storage in SQLite?
5. **Timestamp Handling**: How to handle UTC timestamps in SQLite (no native datetime type)?
6. **Error Handling**: FastAPI exception handlers for validation errors and 404s?
7. **PATCH vs PUT**: Implementation patterns for partial updates in FastAPI?

### Research Deliverable

Create `research.md` with:
- Code examples for SQLite connection management in FastAPI
- Pydantic model patterns (BaseModel, response_model, validation)
- pytest fixture setup for test database
- Decision on ORM vs raw SQL (recommendation: raw SQL for simplicity per constitution)
- Timestamp storage format (recommendation: ISO 8601 strings or Unix timestamps)

## Phase 1: Design

**Objective**: Create data models, API contracts, and quickstart guide.

### Design Deliverables

1. **data-model.md**: 
   - SQL schema for `todos` table
   - Pydantic models: `TodoCreate`, `TodoUpdate`, `TodoResponse`, `TodoComplete`
   - Type mappings between SQLite and Python

2. **contracts/** directory:
   - `POST_todos.md`: Create todo contract
   - `GET_todos.md`: List todos contract
   - `GET_todos_id.md`: Get single todo contract
   - `PATCH_todos_id.md`: Update todo contract
   - `DELETE_todos_id.md`: Delete todo contract
   - `PATCH_todos_id_complete.md`: Mark complete contract
   - `PATCH_todos_id_incomplete.md`: Mark incomplete contract

3. **quickstart.md**:
   - Installation steps (uv sync)
   - Database initialization
   - Running the server
   - Example curl commands for all endpoints
   - Running tests

### Key Design Decisions

- **Database Schema**: Single `todos` table with columns: id (TEXT/UUID), title (TEXT), description (TEXT), completed (INTEGER/BOOLEAN), created_at (TEXT/ISO8601), completed_at (TEXT/ISO8601 nullable)
- **API Response Format**: Consistent JSON structure for all endpoints with camelCase or snake_case (to be decided)
- **Validation**: Pydantic handles all input validation with Field constraints
- **Error Responses**: Consistent error JSON structure: `{"detail": "error message"}`

## Phase 2: Implementation Tasks

**Objective**: Break down implementation into atomic, testable tasks.

**Note**: This phase is executed by `/speckit.tasks` command (NOT part of `/speckit.plan`).

The tasks.md file will contain:
- Setup tasks (project initialization, dependencies)
- Database tasks (schema, connection management)
- Model tasks (Pydantic schemas)
- Service layer tasks (CRUD operations)
- API route tasks (7 endpoints)
- Test tasks (contract, integration, unit tests)
- Each task marked as TDD cycle with clear acceptance criteria

## Implementation Approach

### Development Workflow

1. **Phase 0**: Complete research.md with SQLite + FastAPI patterns
2. **Phase 1**: Complete data-model.md, all contract files, and quickstart.md
3. **Phase 2**: Run `/speckit.tasks` to generate atomic implementation tasks
4. **Phase 3**: Execute tasks in TDD cycles (Red-Green-Refactor)
5. **Phase 4**: Verify all acceptance scenarios pass

### Test-First Strategy (TDD)

For each endpoint:
1. Write contract test based on acceptance scenarios from spec.md
2. Run test → see it fail (RED)
3. Implement minimum code to pass (GREEN)
4. Refactor for clarity while keeping tests green (REFACTOR)
5. Move to next acceptance scenario

### Verification Gates

- [ ] All 21 acceptance scenarios from spec.md implemented as tests
- [ ] All tests pass with 100% success rate
- [ ] All 7 endpoints return correct status codes
- [ ] Response times <50ms for all operations (verified with pytest-benchmark)
- [ ] Type checking passes (mypy --strict)
- [ ] Linting passes (ruff check)
- [ ] Code coverage >90% (pytest-cov)

## Dependencies & Setup

### Required Packages

```toml
[project]
name = "todo-api"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "httpx>=0.27.0",
    "ruff>=0.6.0",
    "mypy>=1.11.0",
]
```

### Environment Setup

```bash
# Install uv package manager (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create project and install dependencies
uv init todo-api
cd todo-api
uv add fastapi uvicorn[standard] pydantic
uv add --dev pytest pytest-cov httpx ruff mypy

# Initialize database (will be part of main.py startup)
# Run tests
uv run pytest

# Start server
uv run uvicorn src.main:app --reload
```

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| SQLite locking under concurrent writes | Medium | Document that SQLite handles locking, last-write-wins acceptable for MVP |
| Timestamp timezone handling | Low | Store all timestamps as UTC ISO 8601 strings, document in API contracts |
| UUID generation performance | Low | Use Python's uuid.uuid4(), negligible overhead for CRUD operations |
| Test database cleanup | Low | Use pytest fixtures with tmp_path for isolated test databases |
| Missing validation edge cases | Medium | Comprehensive test coverage for all acceptance scenarios including edge cases |

## Success Metrics

- ✅ All 7 endpoints functional with correct status codes
- ✅ All 21 acceptance scenarios pass as automated tests
- ✅ 100% of functional requirements (FR-001 through FR-012) implemented
- ✅ Response times <50ms verified with test suite
- ✅ Zero validation bypasses (all invalid inputs return 400)
- ✅ Type checking passes with --strict mode
- ✅ Code follows constitution (max 30 lines/function, max 300 lines/file)

## Next Steps

1. Execute Phase 0: Complete research.md
2. Execute Phase 1: Complete data-model.md, contracts/, quickstart.md
3. Run `/speckit.tasks` to generate implementation tasks
4. Begin TDD implementation cycle
