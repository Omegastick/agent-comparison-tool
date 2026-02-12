# API Contract: Delete a Todo

**Endpoint**: `DELETE /todos/{id}`
**User Story**: US5 - Delete a Todo (P2)
**Requirements**: FR-009

## Request

**Method**: DELETE
**Path**: `/todos/{id}`
**Content-Type**: N/A (no request body)

### Path Parameters

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `id` | string | Yes | Must be a valid UUID v4 format |

## Response

### 204 No Content

Returned when the todo is successfully deleted. No response body.

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

## Examples

### Successful deletion

```
DELETE /todos/550e8400-e29b-41d4-a716-446655440000
```

**Response** (204): No body.

### Verify deletion

```
GET /todos
```

**Response** (200):
```json
{
  "todos": []
}
```

The deleted todo no longer appears in the list.

### Todo not found

```
DELETE /todos/00000000-0000-0000-0000-000000000000
```

**Response** (404):
```json
{
  "detail": "Todo not found"
}
```

### Invalid UUID format

```
DELETE /todos/not-a-uuid
```

**Response** (400):
```json
{
  "detail": "Invalid todo ID format"
}
```
