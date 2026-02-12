# Contract: Update Todo

**Endpoint**: `PATCH /todos/{id}`
**Priority**: P2

## Request

**Path Parameters**:
- `id` (string, required): UUID v4 of the todo

**Content-Type**: `application/json`

```json
{
  "title": "string (optional, 1-500 chars)",
  "description": "string (optional, max 2000 chars)"
}
```

### Valid Examples

Update title only:
```json
{"title": "New title"}
```

Update description only:
```json
{"description": "New description"}
```

Update both:
```json
{"title": "New title", "description": "New description"}
```

### Invalid Examples

```json
{"title": ""}
```
Reason: Title must be at least 1 character if provided.

## Responses

### 200 OK

Returned when the todo is successfully updated. Returns the full updated todo.

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "New title",
  "description": null,
  "completed": false,
  "created_at": "2026-02-12T15:30:00Z",
  "completed_at": null
}
```

**Invariants**:
- Only provided fields are updated; omitted fields remain unchanged
- `id`, `completed`, `created_at`, and `completed_at` are never modified by this endpoint

### 400 Bad Request

Returned when validation fails or ID format is invalid.

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
