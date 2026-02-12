# Contract: Get a Single Todo

**Endpoint**: `GET /todos/{id}`
**User Story**: 3 (Priority: P1)

## Request

**Path Parameter**:
- `id` (string, required): UUID v4 of the todo

## Response

### 200 OK

**Content-Type**: `application/json`

```json
{
  "id": "uuid-v4-string",
  "title": "string",
  "description": "string | null",
  "completed": false,
  "created_at": "ISO 8601 UTC datetime",
  "completed_at": "ISO 8601 UTC datetime | null"
}
```

**Pydantic Model**: `TodoResponse`

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

**Note**: Per spec edge cases, invalid UUID format returns 400 (not 404).

## Acceptance Scenarios

1. Todo exists with id "abc-123" -> 200 with full todo details
2. No todo with id "nonexistent" -> 404 Not Found
