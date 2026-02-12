# API Contract: Mark Todo Complete

**Endpoint**: `PATCH /todos/{id}/complete`
**User Story**: US6 - Mark Todo Complete/Incomplete (P2)
**Requirements**: FR-010, FR-005

## Request

**Method**: PATCH
**Path**: `/todos/{id}/complete`
**Content-Type**: N/A (no request body)

### Path Parameters

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `id` | string | Yes | Must be a valid UUID v4 format |

## Response

### 200 OK

Returned when the todo is successfully marked as complete. The `completed` field is set to `true` and `completed_at` is set to the current UTC timestamp.

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Buy groceries",
  "description": "",
  "completed": true,
  "created_at": "2025-02-12T15:30:00Z",
  "completed_at": "2025-02-12T16:00:00Z"
}
```

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

## Behavior Notes

- Marking an already-completed todo as complete is idempotent. The `completed_at` timestamp is updated to the current time.
- The `completed_at` timestamp is always set to the current UTC time when this endpoint is called.

## Examples

### Mark incomplete todo as complete

```
PATCH /todos/550e8400-e29b-41d4-a716-446655440000/complete
```

**Response** (200):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Buy groceries",
  "description": "",
  "completed": true,
  "created_at": "2025-02-12T15:30:00Z",
  "completed_at": "2025-02-12T16:00:00Z"
}
```

### Todo not found

```
PATCH /todos/00000000-0000-0000-0000-000000000000/complete
```

**Response** (404):
```json
{
  "detail": "Todo not found"
}
```
