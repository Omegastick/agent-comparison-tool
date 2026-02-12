# Data Model: Todo CRUD API

**Feature**: 001-todo-crud | **Date**: 2026-02-12

## Entity: Todo

### SQLite Schema

```sql
CREATE TABLE IF NOT EXISTS todos (
    id          TEXT PRIMARY KEY,          -- UUID v4, generated server-side
    title       TEXT NOT NULL,             -- 1-500 characters
    description TEXT DEFAULT NULL,         -- 0-2000 characters, nullable
    completed   INTEGER NOT NULL DEFAULT 0, -- Boolean: 0=false, 1=true
    created_at  TEXT NOT NULL,             -- ISO 8601 UTC timestamp
    completed_at TEXT DEFAULT NULL         -- ISO 8601 UTC timestamp, nullable
);
```

**Notes**:
- SQLite has no native UUID, BOOLEAN, or DATETIME types. TEXT and INTEGER are used.
- `completed` uses INTEGER (0/1) as SQLite's conventional boolean representation.
- Timestamps stored as ISO 8601 strings (e.g., `2026-02-12T15:30:00Z`) for human readability and standard compliance.
- No indexes beyond the primary key -- at < 1,000 rows, sequential scan is within the 50ms performance target.

### Pydantic Models

```python
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class TodoCreate(BaseModel):
    """Request body for POST /todos."""
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=2000)


class TodoUpdate(BaseModel):
    """Request body for PATCH /todos/{id}."""
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=2000)


class TodoResponse(BaseModel):
    """Response body for all endpoints that return a Todo."""
    id: UUID
    title: str
    description: str | None
    completed: bool
    created_at: datetime
    completed_at: datetime | None
```

### Field Mapping: SQLite <-> Pydantic

| SQLite Column | SQLite Type | Python Type | Pydantic Field | Conversion |
|---------------|-------------|-------------|----------------|------------|
| `id` | TEXT | `UUID` | `TodoResponse.id` | `str(uuid4())` on write, `UUID(row["id"])` on read |
| `title` | TEXT | `str` | `TodoCreate.title` / `TodoResponse.title` | Direct |
| `description` | TEXT (nullable) | `str \| None` | `TodoCreate.description` / `TodoResponse.description` | Direct |
| `completed` | INTEGER (0/1) | `bool` | `TodoResponse.completed` | `bool(row["completed"])` on read, `int(value)` on write |
| `created_at` | TEXT | `datetime` | `TodoResponse.created_at` | `datetime.utcnow().isoformat() + "Z"` on write, `datetime.fromisoformat(row["created_at"])` on read |
| `completed_at` | TEXT (nullable) | `datetime \| None` | `TodoResponse.completed_at` | Same as `created_at`, but nullable |

### Database Operations

| Operation | SQL | Parameters |
|-----------|-----|------------|
| Create | `INSERT INTO todos (id, title, description, completed, created_at, completed_at) VALUES (?, ?, ?, ?, ?, ?)` | `(id, title, description, 0, created_at, None)` |
| List all | `SELECT * FROM todos ORDER BY created_at DESC` | _(none)_ |
| Get by ID | `SELECT * FROM todos WHERE id = ?` | `(id,)` |
| Update | `UPDATE todos SET title = COALESCE(?, title), description = COALESCE(?, description) WHERE id = ?` | `(title, description, id)` |
| Delete | `DELETE FROM todos WHERE id = ?` | `(id,)` |
| Mark complete | `UPDATE todos SET completed = 1, completed_at = ? WHERE id = ?` | `(completed_at, id)` |
| Mark incomplete | `UPDATE todos SET completed = 0, completed_at = NULL WHERE id = ?` | `(id,)` |

### Ordering

Todos are listed ordered by `created_at DESC` (newest first), as specified in User Story 2, Acceptance Scenario 3.
