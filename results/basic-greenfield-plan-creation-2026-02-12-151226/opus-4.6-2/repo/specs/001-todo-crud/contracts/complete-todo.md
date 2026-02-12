# Contract: Mark Todo Complete

**Endpoint**: `PATCH /todos/{id}/complete`
**Priority**: P2

## Request

**Path Parameters**:
- `id` (string, required): UUID v4 of the todo

No request body.

## Responses

### 200 OK

Returned when the todo is successfully marked as complete.

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Buy groceries",
  "description": null,
  "completed": true,
  "created_at": "2026-02-12T15:30:00Z",
  "completed_at": "2026-02-12T16:00:00Z"
}
```

**Invariants**:
- `completed` is set to `true`
- `completed_at` is set to current UTC time
- All other fields remain unchanged
- Marking an already-complete todo as complete is idempotent (updates `completed_at` to current time)

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
