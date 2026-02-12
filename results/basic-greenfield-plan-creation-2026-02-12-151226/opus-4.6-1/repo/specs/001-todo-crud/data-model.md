# Data Model: Todo CRUD API

**Feature**: `001-todo-crud` | **Date**: 2026-02-12 | **Phase**: 1

## Entity: Todo

### Database Schema (SQLite)

```sql
CREATE TABLE IF NOT EXISTS todos (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL CHECK(length(title) >= 1 AND length(title) <= 500),
    description TEXT DEFAULT '' CHECK(length(description) <= 2000),
    completed   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    completed_at TEXT
);
```

**Column Details**:

| Column | SQLite Type | Python Type | Constraints | Notes |
|--------|-------------|-------------|-------------|-------|
| `id` | TEXT | `uuid.UUID` | PRIMARY KEY | UUID v4, generated server-side via `uuid.uuid4()` |
| `title` | TEXT | `str` | NOT NULL, 1-500 chars | Required field, validated by Pydantic and DB CHECK |
| `description` | TEXT | `str \| None` | Max 2000 chars | Optional, defaults to empty string in DB |
| `completed` | INTEGER | `bool` | NOT NULL, DEFAULT 0 | SQLite has no BOOLEAN; 0=false, 1=true |
| `created_at` | TEXT | `datetime` | NOT NULL | ISO 8601 UTC, set on creation, immutable |
| `completed_at` | TEXT | `datetime \| None` | Nullable | ISO 8601 UTC, set when completed, null when incomplete |

### Pydantic Models

#### `TodoCreate` (Request - POST /todos)

```python
class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=2000)
```

#### `TodoUpdate` (Request - PATCH /todos/{id})

```python
class TodoUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=2000)
```

#### `TodoResponse` (Response - all endpoints returning a Todo)

```python
class TodoResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    completed: bool
    created_at: datetime
    completed_at: datetime | None
```

#### `TodoListResponse` (Response - GET /todos)

```python
class TodoListResponse(BaseModel):
    todos: list[TodoResponse]
```

### Data Flow

```text
Client Request
    │
    ▼
Pydantic Model (validates input)
    │
    ▼
Route Handler (business logic)
    │
    ▼
Database Layer (parameterized SQL)
    │
    ▼
SQLite Row (tuple)
    │
    ▼
TodoResponse Model (serializes output)
    │
    ▼
JSON Response
```

### SQL Queries

| Operation | Query |
|-----------|-------|
| Create | `INSERT INTO todos (id, title, description, completed, created_at, completed_at) VALUES (?, ?, ?, ?, ?, ?)` |
| List All | `SELECT id, title, description, completed, created_at, completed_at FROM todos ORDER BY created_at DESC` |
| Get by ID | `SELECT id, title, description, completed, created_at, completed_at FROM todos WHERE id = ?` |
| Update | `UPDATE todos SET {dynamic_fields} WHERE id = ?` (fields built from provided PATCH body) |
| Delete | `DELETE FROM todos WHERE id = ?` |
| Mark Complete | `UPDATE todos SET completed = 1, completed_at = ? WHERE id = ?` |
| Mark Incomplete | `UPDATE todos SET completed = 0, completed_at = NULL WHERE id = ?` |

### Indexes

No additional indexes beyond the PRIMARY KEY on `id`. The `ORDER BY created_at DESC` for listing is acceptable without an index given the <1000 todos target (per SC-003, all operations must complete in <50ms).

### Data Integrity Rules

1. **UUID uniqueness**: Enforced by PRIMARY KEY constraint. Collision probability with UUIDv4 is negligible.
2. **Title constraints**: Enforced at both Pydantic layer (API boundary) and SQLite CHECK constraint (defense in depth).
3. **Completed/completed_at consistency**: When `completed=true`, `completed_at` must be set. When `completed=false`, `completed_at` must be NULL. Enforced in application logic (route handlers).
4. **created_at immutability**: Never included in UPDATE queries. Set once on INSERT.
