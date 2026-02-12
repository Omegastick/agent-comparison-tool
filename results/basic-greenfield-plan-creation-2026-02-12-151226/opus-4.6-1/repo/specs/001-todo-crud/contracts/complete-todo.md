# Contract: Mark Todo Complete

**Endpoint**: `PATCH /todos/{id}/complete`
**User Story**: 6 (Priority: P2)

## Request

**Path Parameter**:
- `id` (string, required): UUID v4 of the todo

No request body.

## Response

### 200 OK

**Content-Type**: `application/json`

Returns the full todo with updated completion status:

```json
{
  "id": "uuid-v4-string",
  "title": "string",
  "description": "string | null",
  "completed": true,
  "created_at": "ISO 8601 UTC datetime",
  "completed_at": "ISO 8601 UTC datetime"
}
```

**Pydantic Model**: `TodoResponse`

**Invariants**:
- `completed` is set to `true`
- `completed_at` is set to current UTC timestamp
- If already complete, this is idempotent (updates `completed_at` to current time)
- `title`, `description`, `created_at` are never modified

### 404 Not Found

```json
{
  "detail": "Todo not found"
}
```

### 400 Bad Request

```json
{
  "detail": "Invalid todo ID format"
}
```

## Acceptance Scenarios

1. Incomplete todo -> PATCH complete -> 200 with completed=true, completed_at set
2. Nonexistent ID -> 404 Not Found
