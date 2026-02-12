# Contract: Update a Todo

**Endpoint**: `PATCH /todos/{id}`
**User Story**: 4 (Priority: P2)

## Request

**Path Parameter**:
- `id` (string, required): UUID v4 of the todo

**Content-Type**: `application/json`

**Body** (all fields optional, at least one should be provided):
```json
{
  "title": "string (optional, 1-500 characters)",
  "description": "string (optional, max 2000 characters)"
}
```

**Pydantic Model**: `TodoUpdate`

**PATCH Semantics**: Only fields present in the request body are updated. Absent fields remain unchanged. This is determined by using Pydantic's `model_dump(exclude_unset=True)`.

## Response

### 200 OK

**Content-Type**: `application/json`

Returns the full updated todo:

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

**Invariants**:
- `id` never changes
- `created_at` never changes
- `completed` and `completed_at` are not affected by this endpoint
- Only `title` and/or `description` can be updated

### 400 Bad Request

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
- `title` is empty string
- `title` exceeds 500 characters
- `description` exceeds 2000 characters
- Invalid UUID format for path parameter

### 404 Not Found

```json
{
  "detail": "Todo not found"
}
```

## Acceptance Scenarios

1. PATCH with `{"title": "New title"}` -> 200 with updated title, description unchanged
2. PATCH with `{"description": "New desc"}` -> 200 with updated description, title unchanged
3. PATCH on nonexistent ID -> 404 Not Found
