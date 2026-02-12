# Speckit Plan: 001-todo-crud — Todo CRUD

## Objective
Deliver a minimal, reliable Todo CRUD service and API that supports creating, reading, updating, deleting, and listing tasks with basic filtering and validation. Prioritize simplicity, correctness, and test coverage.

## Scope
- REST JSON API with endpoints for create/read/update/delete/list
- Single-tenant, single-node deployment; no auth for now
- SQLite for persistence; clean separation of layers (API, service, data)
- Validation, error handling, and pagination for list

## Non-Goals
- No user accounts or auth/roles
- No complex search; only simple filters
- No multi-tenant or horizontal scaling
- No background jobs, notifications, or real-time features

## Deliverables
- FastAPI application with Todo CRUD endpoints
- Data model and migration bootstrap (SQLite)
- Service layer with validation and business rules
- Tests (unit + integration) and basic docs

## High-Level Design
- API: FastAPI, Pydantic v2 schemas
- Service: pure functions for business logic, validation
- Data: SQLite via `sqlite3` or `sqlalchemy` with parameterized queries
- Layout: `src/api`, `src/models`, `src/services`, `src/lib/db.py`

## Data Model
Todo
- id: int (PK, auto-increment)
- title: str (1..200)
- description: str (0..2000) optional
- status: enum {"pending","in_progress","done"}, default "pending"
- priority: int (0..5), default 0
- due_date: date optional
- created_at: datetime (UTC)
- updated_at: datetime (UTC)

Indexes
- idx_todos_status
- idx_todos_due_date

## API Endpoints
- POST `/todos`
  - Body: { title, description?, priority?, due_date? }
  - 201 Created: returns full Todo
  - 400 on validation error

- GET `/todos/{id}`
  - 200 OK: returns Todo
  - 404 if missing

- PUT `/todos/{id}`
  - Body: { title?, description?, status?, priority?, due_date? }
  - 200 OK: returns updated Todo
  - 404 if missing; 400 on validation error

- DELETE `/todos/{id}`
  - 204 No Content
  - 404 if missing

- GET `/todos`
  - Query: `status?`, `due_before?`, `due_after?`, `limit` (1..100 default 20), `offset` (>=0)
  - 200 OK: { items: Todo[], total: int }

## Validation & Rules
- `title`: required, trimmed, length 1..200
- `description`: length 0..2000
- `status`: only allowed transitions: any -> pending|in_progress|done (no extra rules yet)
- `priority`: integer 0..5
- `due_date`: ISO date string; cannot be before 1970-01-01; warn if past
- All responses use UTC ISO 8601 timestamps

## Errors
- 400: validation errors (field-specific messages)
- 404: resource not found
- 409: idempotency conflicts (if introduced later)
- 500: unexpected errors (masked message, log details)

## Testing Strategy
- Unit: service-level validation and state changes
- Integration: API endpoints with `httpx.AsyncClient`
- Contract: acceptance scenarios for CRUD + listing + filters
- DB: migration init and basic constraints

## Observability
- Request logging: method, path, status, duration
- Error logging with stack traces (server-side only)
- Simple health endpoint `/health` (200 when DB reachable)

## Performance & Limits
- Pagination limit max 100
- Parameterized queries; avoid N+1 by simple SELECTs
- Index on `status` and `due_date` for list filters
- Timeouts: 5s per request default

## Risks & Mitigations
- SQLite lock contention: keep transactions short, use WAL mode
- Validation gaps: comprehensive tests; strict Pydantic models
- Schema drift: migrations tracked; single source of truth in code

## Milestones
1) Data model + DB init (SQLite, tables, indexes)
2) Service layer with validation and CRUD
3) API routes and schemas
4) List filters + pagination
5) Tests (unit, integration, acceptance)
6) Basic docs and health endpoint

## Acceptance Criteria
- All endpoints behave as specified with correct HTTP codes
- Validation enforced; informative error messages
- List endpoint supports `status`, `due_before/after`, `limit/offset`
- Test suite passes locally (`pytest`)
- Plan and minimal docs present in repo
