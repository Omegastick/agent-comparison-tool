# API Contract: Mark Todo Incomplete

**Endpoint**: `PATCH /todos/{id}/incomplete`
**User Story**: US6 - Mark Todo Complete/Incomplete (P2)
**Requirements**: FR-010, FR-005

## Request

**Method**: PATCH
**Path**: `/todos/{id}/incomplete`
**Content-Type**: N/A (no request body)

### Path Parameters

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `id` | string | Yes | Must be a valid UUID v4 format |

## Response

### 200 OK

Returned when the todo is successfully marked as incomplete. The `completed` field is set to `false` and `completed_at` is set to `null`.

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

## Behavior Notes

- Marking an already-incomplete todo as incomplete is idempotent. No error is returned.
- The `completed_at` field is always set to `null` when this endpoint is called.

## Examples

### Mark completed todo as incomplete

```
PATCH /todos/550e8400-e29b-41d4-a716-446655440000/incomplete
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
PATCH /todos/00000000-0000-0000-0000-000000000000/incomplete
```

**Response** (404):
```json
{
  "detail": "Todo not found"
}
```
