# API Contract: Get a Single Todo

**Endpoint**: `GET /todos/{id}`
**User Story**: US3 - Get a Single Todo (P1)
**Requirements**: FR-007

## Request

**Method**: GET
**Path**: `/todos/{id}`
**Content-Type**: N/A (no request body)

### Path Parameters

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `id` | string | Yes | Must be a valid UUID v4 format |

## Response

### 200 OK

Returned when the todo is found.

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Buy groceries",
  "description": "",
  "completed": false,
  "created_at": "2025-02-12T15:30:00Z",
  "completed_at": null
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

## Examples

### Successful retrieval

```
GET /todos/550e8400-e29b-41d4-a716-446655440000
```

**Response** (200):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Buy groceries",
  "description": "",
  "completed": false,
  "created_at": "2025-02-12T15:30:00Z",
  "completed_at": null
}
```

### Todo not found

```
GET /todos/00000000-0000-0000-0000-000000000000
```

**Response** (404):
```json
{
  "detail": "Todo not found"
}
```

### Invalid UUID format

```
GET /todos/not-a-uuid
```

**Response** (400):
```json
{
  "detail": "Invalid todo ID format"
}
```
