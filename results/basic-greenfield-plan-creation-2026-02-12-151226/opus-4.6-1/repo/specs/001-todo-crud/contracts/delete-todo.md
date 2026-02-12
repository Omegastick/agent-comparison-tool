# Contract: Delete a Todo

**Endpoint**: `DELETE /todos/{id}`
**User Story**: 5 (Priority: P2)

## Request

**Path Parameter**:
- `id` (string, required): UUID v4 of the todo

No request body.

## Response

### 204 No Content

Empty response body. The todo has been permanently deleted.

**Invariants**:
- The deleted todo no longer appears in `GET /todos` results
- Subsequent `GET /todos/{id}` for this ID returns 404
- Subsequent `DELETE /todos/{id}` for this ID returns 404

### 404 Not Found

Returned when no todo exists with the given ID.

```json
{
  "detail": "Todo not found"
}
```

### 400 Bad Request

Returned when the ID is not a valid UUID format.

```json
{
  "detail": "Invalid todo ID format"
}
```

## Acceptance Scenarios

1. DELETE existing todo -> 204 No Content (empty body)
2. Deleted todo no longer in `GET /todos` list
3. DELETE nonexistent ID -> 404 Not Found
