# Contract: Create Todo

**Endpoint**: `POST /todos`
**Priority**: P1

## Request

**Content-Type**: `application/json`

```json
{
  "title": "string (required, 1-500 chars)",
  "description": "string (optional, max 2000 chars)"
}
```

### Valid Examples

```json
{"title": "Buy groceries"}
```

```json
{"title": "Call mom", "description": "About birthday"}
```

### Invalid Examples

```json
{"title": ""}
```
Reason: Title must be at least 1 character.

```json
{"title": "A".repeat(501)}
```
Reason: Title exceeds 500 character limit.

```json
{}
```
Reason: Title is required.

## Responses

### 201 Created

Returned when the todo is successfully created.

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Buy groceries",
  "description": null,
  "completed": false,
  "created_at": "2026-02-12T15:30:00Z",
  "completed_at": null
}
```

**Invariants**:
- `id` is a valid UUID v4
- `completed` is always `false`
- `completed_at` is always `null`
- `created_at` is set to current UTC time
- `title` matches the request body
- `description` matches the request body (or `null` if not provided)

### 400 Bad Request

Returned when validation fails.

```json
{
  "detail": "Validation error message"
}
```

**Triggers**:
- Empty title (`""`)
- Title longer than 500 characters
- Description longer than 2000 characters
- Missing title field
