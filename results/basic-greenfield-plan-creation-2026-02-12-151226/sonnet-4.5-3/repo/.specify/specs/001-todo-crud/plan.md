# Implementation Plan: Todo CRUD API

**Branch**: `001-todo-crud` | **Date**: 2026-02-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `.specify/specs/001-todo-crud/spec.md`

**Note**: This plan is created by the `/speckit.plan` command and outlines the implementation approach for the Todo CRUD API feature.

## Summary

This feature implements a RESTful API for managing todo items with full CRUD operations (Create, Read, Update, Delete) plus completion status management. The system will use SQLite for data persistence and provide 7 endpoints to handle all todo lifecycle operations. The implementation focuses on simplicity, validation, and proper HTTP semantics with automated testing for all acceptance scenarios.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: FastAPI, SQLite3, Pydantic, pytest  
**Storage**: SQLite database (todos.db file)  
**Testing**: pytest with httpx for API testing  
**Target Platform**: Linux server / cross-platform  
**Project Type**: Single API service  
**Performance Goals**: <50ms response time for operations on databases with <1000 todos  
**Constraints**: 
- Title validation: 1-500 characters required
- Description validation: 0-2000 characters optional
- All timestamps in UTC
- UUID v4 for todo IDs

**Scale/Scope**: 
- MVP single-user todo API
- 7 API endpoints
- 6 user stories with 17 acceptance scenarios
- ~500-800 lines of production code estimated

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Status**: PASS

- ✓ Single project structure (no unnecessary complexity)
- ✓ Direct database access (no repository pattern needed for MVP)
- ✓ Standard REST API patterns
- ✓ Appropriate dependencies for task
- ✓ Clear validation and error handling requirements
- ✓ Independent, testable user stories

No constitution violations detected. Implementation can proceed.

## Project Structure

### Documentation (this feature)

```text
.specify/specs/001-todo-crud/
├── spec.md              # Feature specification (existing)
├── plan.md              # This file (implementation plan)
├── research.md          # Phase 0: Research findings
├── data-model.md        # Phase 1: Database schema and models
├── quickstart.md        # Phase 1: Development and testing guide
├── contracts/           # Phase 1: API contract definitions
│   ├── create-todo.md
│   ├── list-todos.md
│   ├── get-todo.md
│   ├── update-todo.md
│   ├── delete-todo.md
│   ├── complete-todo.md
│   └── incomplete-todo.md
└── tasks.md             # Phase 2: Implementation tasks (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── models/
│   ├── __init__.py
│   └── todo.py          # Todo Pydantic models (request/response/db)
├── database/
│   ├── __init__.py
│   ├── connection.py    # SQLite connection setup
│   └── migrations.py    # Database schema initialization
├── services/
│   ├── __init__.py
│   └── todo_service.py  # Business logic for todo operations
├── api/
│   ├── __init__.py
│   ├── routes.py        # FastAPI route definitions
│   └── dependencies.py  # Dependency injection (DB session)
├── validation/
│   ├── __init__.py
│   └── todo_validator.py # Input validation logic
└── main.py              # FastAPI application entry point

tests/
├── conftest.py          # Pytest fixtures (test DB, test client)
├── unit/
│   ├── __init__.py
│   ├── test_todo_service.py
│   └── test_validation.py
├── integration/
│   ├── __init__.py
│   └── test_database.py
└── contract/
    ├── __init__.py
    ├── test_create_todo.py
    ├── test_list_todos.py
    ├── test_get_todo.py
    ├── test_update_todo.py
    ├── test_delete_todo.py
    ├── test_complete_todo.py
    └── test_edge_cases.py

pyproject.toml           # Project dependencies and configuration
todos.db                 # SQLite database file (created at runtime)
README.md                # Project setup and usage instructions
```

**Structure Decision**: Single project structure selected. This is a straightforward API service without frontend/backend separation needs. All code resides in a `src/` directory with clear separation of concerns (models, database, services, API routes). Tests are organized by type (unit, integration, contract) to match the three testing levels needed for comprehensive coverage.

## Complexity Tracking

> **No violations to track.** This implementation follows best practices for a simple CRUD API without introducing unnecessary patterns or abstractions.

## Implementation Phases

### Phase 0: Research & Validation

**Objective**: Validate technical approach and identify existing patterns in the repository

**Deliverable**: `research.md`

**Key Questions**:
1. Does the repository have existing Python/FastAPI code to follow for consistency?
2. What testing patterns are already established?
3. Are there existing database connection patterns or migration strategies?
4. What error handling and response format conventions exist?
5. What dependencies are already in use (FastAPI version, pydantic, etc.)?

**Research Tasks**:
- [ ] Search repository for existing Python files and patterns
- [ ] Identify existing test structure and fixtures
- [ ] Review any existing database access patterns
- [ ] Check for API response format standards
- [ ] Verify Python version and dependency management approach
- [ ] Document findings in research.md

**Gate**: Research complete before moving to Phase 1

### Phase 1: Design & Contracts

**Objective**: Design data models, API contracts, and system architecture

**Deliverables**: 
- `data-model.md` - Database schema and Pydantic models
- `quickstart.md` - Development setup and testing guide
- `contracts/` - Detailed API contract for each endpoint

**Design Tasks**:
- [ ] Design SQLite schema for todos table
- [ ] Define Pydantic models (CreateTodoRequest, UpdateTodoRequest, TodoResponse)
- [ ] Design database connection management and initialization
- [ ] Define API contracts for all 7 endpoints with examples
- [ ] Plan validation strategy for title and description
- [ ] Design error response format (consistent JSON structure)
- [ ] Plan timestamp handling (UTC, ISO 8601 format)
- [ ] Design test fixtures and test database strategy

**Contract Specifications** (to be detailed in contracts/ directory):
1. `POST /todos` - Create a new todo
2. `GET /todos` - List all todos (ordered by created_at desc)
3. `GET /todos/{id}` - Get a single todo by ID
4. `PATCH /todos/{id}` - Update todo title/description
5. `DELETE /todos/{id}` - Delete a todo
6. `PATCH /todos/{id}/complete` - Mark todo as complete
7. `PATCH /todos/{id}/incomplete` - Mark todo as incomplete

**Gate**: All design documents reviewed and approved before Phase 2

### Phase 2: Implementation

**Objective**: Build the feature according to design and contracts

**Deliverable**: `tasks.md` (created by `/speckit.tasks` command)

**Implementation will be broken down into these components**:

1. **Database Layer**
   - SQLite schema creation
   - Connection management
   - Database initialization on startup

2. **Data Models**
   - Pydantic models for requests and responses
   - Database row mapping

3. **Validation Layer**
   - Title validation (1-500 chars, non-empty)
   - Description validation (max 2000 chars)
   - UUID format validation

4. **Service Layer**
   - Create todo logic
   - List todos logic (with ordering)
   - Get single todo logic
   - Update todo logic (partial updates)
   - Delete todo logic
   - Complete/incomplete toggle logic

5. **API Layer**
   - FastAPI route handlers
   - Error handling middleware
   - HTTP status code mapping
   - Request/response serialization

6. **Testing**
   - Unit tests for validation
   - Unit tests for service logic
   - Integration tests for database operations
   - Contract tests for all 17 acceptance scenarios
   - Edge case tests

**Task Creation**: Run `/speckit.tasks` to generate detailed implementation tasks

### Phase 3: Testing & Validation

**Objective**: Ensure all acceptance criteria are met

**Validation Checklist**:
- [ ] All 7 endpoints implemented and functional (SC-001)
- [ ] All 17 acceptance scenarios pass (SC-002)
- [ ] Response times <50ms for <1000 todos (SC-003)
- [ ] All validation rules enforced (SC-004)
- [ ] Consistent JSON response format (SC-005)
- [ ] 404 handling for non-existent resources
- [ ] 400 handling for validation errors
- [ ] Edge cases handled (empty title, too long inputs, invalid UUIDs)
- [ ] Database auto-creation on first run
- [ ] Timestamps in UTC and ISO 8601 format

**Testing Strategy**:
1. Run unit tests: `pytest tests/unit/`
2. Run integration tests: `pytest tests/integration/`
3. Run contract tests: `pytest tests/contract/`
4. Run full test suite: `pytest`
5. Manual API testing with sample requests
6. Performance testing with 1000 todos

## Dependencies

### Production Dependencies
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.5.0
python-multipart>=0.0.6
```

### Development Dependencies
```
pytest>=7.4.0
pytest-asyncio>=0.21.0
httpx>=0.25.0
pytest-cov>=4.1.0
```

## Database Schema

**Table**: `todos`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | UUID v4 as string |
| title | TEXT | NOT NULL | Todo title (1-500 chars) |
| description | TEXT | NULL | Optional description (max 2000 chars) |
| completed | INTEGER | NOT NULL DEFAULT 0 | Boolean as 0/1 |
| created_at | TEXT | NOT NULL | ISO 8601 UTC timestamp |
| completed_at | TEXT | NULL | ISO 8601 UTC timestamp when completed |

**Indexes**: 
- Primary key on `id` (automatic)
- Index on `created_at` for efficient ordering (optional, for future optimization)

## API Response Formats

### Success Response (Todo object)
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Buy groceries",
  "description": "Milk, eggs, bread",
  "completed": false,
  "created_at": "2026-02-12T10:30:00Z",
  "completed_at": null
}
```

### List Response
```json
[
  { "id": "...", "title": "...", ... },
  { "id": "...", "title": "...", ... }
]
```

### Error Response (4xx, 5xx)
```json
{
  "detail": "Error message describing what went wrong"
}
```

### Validation Error Response (400)
```json
{
  "detail": [
    {
      "loc": ["body", "title"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## Error Handling Strategy

| Status Code | When to Return | Example |
|-------------|----------------|---------|
| 200 OK | Successful GET, PATCH | Todo retrieved/updated |
| 201 Created | Successful POST | New todo created |
| 204 No Content | Successful DELETE | Todo deleted |
| 400 Bad Request | Validation failure | Empty title, invalid UUID |
| 404 Not Found | Resource not found | Todo ID doesn't exist |
| 500 Internal Server Error | Unexpected server error | Database connection failure |

## Performance Considerations

1. **Database Operations**: 
   - SQLite is sufficient for MVP (<1000 todos target)
   - Single connection for simplicity
   - Consider connection pooling for future scale

2. **Query Optimization**:
   - `ORDER BY created_at DESC` is indexed
   - Single-row lookups by primary key (id) are fast

3. **Response Times**:
   - Target: <50ms for all operations
   - SQLite operations typically <5ms for small datasets
   - Overhead from FastAPI/Pydantic minimal

## Security Considerations

1. **Input Validation**: 
   - Pydantic handles type validation
   - Custom validators for length constraints
   - SQL injection protected by parameterized queries

2. **Authentication**: 
   - Not implemented in MVP (future enhancement)
   - Single-user system assumed

3. **Data Sanitization**:
   - Title and description are text fields
   - No HTML rendering, so XSS not a concern
   - Length limits prevent memory issues

## Future Enhancements (Out of Scope for MVP)

- User authentication and multi-user support
- Pagination for todo lists
- Filtering (by completed status, date range)
- Sorting options (by title, completion status)
- Due dates and reminders
- Categories or tags
- Search functionality
- Bulk operations (mark all complete, delete completed)
- API rate limiting
- Soft deletes with trash/restore
- Audit logging

## Success Metrics Tracking

| Metric | Target | How to Measure | Status |
|--------|--------|----------------|--------|
| All endpoints functional | 7/7 | Manual testing + contract tests | Pending |
| Acceptance scenarios pass | 17/17 | Automated test suite | Pending |
| Response time | <50ms | Performance test with 1000 todos | Pending |
| Validation coverage | 100% | All invalid inputs return 400 | Pending |
| Consistent responses | 100% | Code review + contract tests | Pending |

## Next Steps

1. **Immediate**: Run `/speckit.plan` research phase to populate `research.md`
2. **Then**: Complete Phase 1 design documents (`data-model.md`, `quickstart.md`, `contracts/`)
3. **Then**: Run `/speckit.tasks` to generate detailed implementation tasks
4. **Finally**: Execute implementation phase with test-driven development

## Notes

- This is an MVP implementation focusing on core functionality
- Architecture allows for future scaling and enhancement
- Test coverage is critical for maintaining quality as features are added
- Follow FastAPI best practices for consistency with Python ecosystem
