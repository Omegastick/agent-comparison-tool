# Contract: Create a Todo

**Endpoint**: `POST /todos`
**User Story**: 1 (Priority: P1)

## Request

**Content-Type**: `application/json`

**Body**:
```json
{
  "title": "string (required, 1-500 characters)",
  "description": "string (optional, max 2000 characters)"
}
```

**Pydantic Model**: `TodoCreate`

## Response

### 201 Created

**Content-Type**: `application/json`

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
- `id` is always a newly generated UUID v4
- `completed` is always `false` on creation
- `completed_at` is always `null` on creation
- `created_at` is set to current UTC time

### 400 Bad Request

Returned when validation fails.

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "title"],
      "msg": "String should have at least 1 character",
      "input": ""
    }
  ]
}
```

**Triggers**:
- `title` is missing from request body
- `title` is empty string (`""`)
- `title` exceeds 500 characters
- `description` exceeds 2000 characters
- Request body is not valid JSON

## Acceptance Scenarios

1. POST with `{"title": "Buy groceries"}` -> 201 with id, title, created_at, completed=false
2. POST with `{"title": "Call mom", "description": "About birthday"}` -> 201 with both fields
3. POST with `{"title": ""}` -> 400 with validation error
