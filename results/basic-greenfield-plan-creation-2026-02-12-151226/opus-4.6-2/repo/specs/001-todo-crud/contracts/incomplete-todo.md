# Contract: Mark Todo Incomplete

**Endpoint**: `PATCH /todos/{id}/incomplete`
**Priority**: P2

## Request

**Path Parameters**:
- `id` (string, required): UUID v4 of the todo

No request body.

## Responses

### 200 OK

Returned when the todo is successfully marked as incomplete.

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Buy groceries",
  "description": null,
  "completed": false,
  "created_at": "2026-02-12T15:30:00Z",
  "completed_at": null
}
```

**Invariants**:
- `completed` is set to `false`
- `completed_at` is set to `null`
- All other fields remain unchanged
- Marking an already-incomplete todo as incomplete is idempotent (no change)

### 400 Bad Request

Returned when the `id` path parameter is not a valid UUID format.

```json
{
  "detail": "Invalid todo ID format"
}
```

### 404 Not Found

Returned when no todo exists with the given ID.

```json
{
  "detail": "Todo not found"
}
```
