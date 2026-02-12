# Contract: Mark Todo Incomplete

**Endpoint**: `PATCH /todos/{id}/incomplete`
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
  "completed": false,
  "created_at": "ISO 8601 UTC datetime",
  "completed_at": null
}
```

**Pydantic Model**: `TodoResponse`

**Invariants**:
- `completed` is set to `false`
- `completed_at` is set to `null`
- If already incomplete, this is idempotent (no change)
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

1. Completed todo -> PATCH incomplete -> 200 with completed=false, completed_at=null
2. Nonexistent ID -> 404 Not Found
