# Data Model: Todo CRUD API

**Branch**: `001-todo-crud` | **Date**: 2025-02-12
**Phase**: 1 - Design

## Entity: Todo

### SQLite Schema

```sql
CREATE TABLE IF NOT EXISTS todos (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL CHECK(length(title) >= 1 AND length(title) <= 500),
    description TEXT DEFAULT '' CHECK(length(description) <= 2000),
    completed   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_todos_created_at ON todos(created_at DESC);
```

### Column Details

| Column | SQLite Type | Constraints | Python Type | Notes |
|--------|-------------|-------------|-------------|-------|
| `id` | TEXT | PRIMARY KEY | `str` (UUID v4) | Generated server-side via `uuid.uuid4()`. Stored as hyphenated string (e.g., `"550e8400-e29b-41d4-a716-446655440000"`). |
| `title` | TEXT | NOT NULL, CHECK(1-500 chars) | `str` | Required. Validated at both Pydantic and database level. |
| `description` | TEXT | DEFAULT '', CHECK(max 2000 chars) | `str` | Optional. Empty string when not provided. |
| `completed` | INTEGER | NOT NULL, DEFAULT 0 | `bool` | SQLite has no boolean type; 0=false, 1=true. Pydantic handles conversion. |
| `created_at` | TEXT | NOT NULL | `datetime` | ISO 8601 UTC format (e.g., `"2025-02-12T15:30:00Z"`). Set once at creation, never modified. |
| `completed_at` | TEXT | nullable | `datetime | None` | ISO 8601 UTC format. Set when `completed` becomes true; cleared (NULL) when set back to false. |

### Index Strategy

- **Primary key on `id`**: Automatic B-tree index for O(log n) lookups by ID.
- **Index on `created_at DESC`**: Supports the "list todos ordered by created_at descending" requirement (FR-006) without a filesort.

## Pydantic Models

### TodoCreate (Request - POST /todos)

```python
class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="", max_length=2000)
```

### TodoUpdate (Request - PATCH /todos/{id})

```python
class TodoUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=2000)
```

All fields optional — partial updates only modify provided fields.

### TodoResponse (Response - all endpoints returning a Todo)

```python
class TodoResponse(BaseModel):
    id: str
    title: str
    description: str
    completed: bool
    created_at: datetime
    completed_at: datetime | None
```

### TodoListResponse (Response - GET /todos)

```python
class TodoListResponse(BaseModel):
    todos: list[TodoResponse]
```

Wrapping the list in an object allows future extensibility (pagination, count, etc.) without breaking the API contract.

## Data Flow by Operation

### Create (POST /todos)

```
TodoCreate → validate → generate UUID + timestamp → INSERT → SELECT by id → TodoResponse
```

### List (GET /todos)

```
SELECT * ORDER BY created_at DESC → [TodoResponse, ...]
```

### Get (GET /todos/{id})

```
Validate UUID format → SELECT by id → TodoResponse (or 404)
```

### Update (PATCH /todos/{id})

```
Validate UUID → TodoUpdate (partial) → UPDATE SET only non-None fields → SELECT by id → TodoResponse (or 404)
```

### Delete (DELETE /todos/{id})

```
Validate UUID → SELECT to check existence → DELETE by id → 204 (or 404)
```

### Complete (PATCH /todos/{id}/complete)

```
Validate UUID → UPDATE SET completed=1, completed_at=now → SELECT by id → TodoResponse (or 404)
```

### Incomplete (PATCH /todos/{id}/incomplete)

```
Validate UUID → UPDATE SET completed=0, completed_at=NULL → SELECT by id → TodoResponse (or 404)
```

## Type Mapping Summary

| Python Type | SQLite Type | Serialization |
|-------------|-------------|---------------|
| `str` (UUID) | TEXT | Stored and returned as hyphenated string |
| `str` | TEXT | Direct mapping |
| `bool` | INTEGER | Python `True`/`False` ↔ SQLite `1`/`0` |
| `datetime` | TEXT | ISO 8601 format (`YYYY-MM-DDTHH:MM:SSZ`) |
| `None` | NULL | SQLite NULL ↔ Python None |
