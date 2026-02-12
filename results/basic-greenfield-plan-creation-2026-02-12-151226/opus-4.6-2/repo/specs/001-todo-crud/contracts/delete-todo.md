# Contract: Delete Todo

**Endpoint**: `DELETE /todos/{id}`
**Priority**: P2

## Request

**Path Parameters**:
- `id` (string, required): UUID v4 of the todo

No request body.

## Responses

### 204 No Content

Returned when the todo is successfully deleted. No response body.

**Invariants**:
- The todo no longer appears in `GET /todos` responses after deletion
- The todo's ID returns 404 on subsequent `GET /todos/{id}` calls

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
