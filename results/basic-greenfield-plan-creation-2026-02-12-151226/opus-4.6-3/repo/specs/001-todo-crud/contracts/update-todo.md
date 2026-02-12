# API Contract: Update a Todo

**Endpoint**: `PATCH /todos/{id}`
**User Story**: US4 - Update a Todo (P2)
**Requirements**: FR-008

## Request

**Method**: PATCH
**Path**: `/todos/{id}`
**Content-Type**: `application/json`

### Path Parameters

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `id` | string | Yes | Must be a valid UUID v4 format |

### Request Body

Partial update — only provided fields are modified.

```json
{
  "title": "string (optional, 1-500 characters)",
  "description": "string (optional, max 2000 characters)"
}
```

### Request Schema

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `title` | string | No | min 1 char, max 500 chars |
| `description` | string | No | max 2000 chars |

At least one field should be provided, though an empty body is not an error (it results in no changes).

## Response

### 200 OK

Returned when the todo is successfully updated. Returns the full updated todo.

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Buy organic groceries",
  "description": "",
  "completed": false,
  "created_at": "2025-02-12T15:30:00Z",
  "completed_at": null
}
```

### 400 Bad Request

Returned when validation fails (empty title, title too long, description too long) or invalid UUID format.

```json
{
  "detail": "Validation error message"
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

### Update title only

```
PATCH /todos/550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json

{"title": "Buy organic groceries"}
```

**Response** (200):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Buy organic groceries",
  "description": "",
  "completed": false,
  "created_at": "2025-02-12T15:30:00Z",
  "completed_at": null
}
```

### Update description only

```
PATCH /todos/550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json

{"description": "From the farmers market"}
```

**Response** (200):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Buy organic groceries",
  "description": "From the farmers market",
  "completed": false,
  "created_at": "2025-02-12T15:30:00Z",
  "completed_at": null
}
```

### Todo not found

```
PATCH /todos/00000000-0000-0000-0000-000000000000
Content-Type: application/json

{"title": "New title"}
```

**Response** (404):
```json
{
  "detail": "Todo not found"
}
```
