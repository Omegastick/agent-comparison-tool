# API Contract: List All Todos

**Endpoint**: `GET /todos`
**User Story**: US2 - List All Todos (P1)
**Requirements**: FR-006

## Request

**Method**: GET
**Path**: `/todos`
**Content-Type**: N/A (no request body)

### Query Parameters

None.

## Response

### 200 OK

Always returned. Contains a list of all todos ordered by `created_at` descending (newest first).

**Empty database:**

```json
{
  "todos": []
}
```

**With todos:**

```json
{
  "todos": [
    {
      "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "title": "Call mom",
      "description": "About birthday",
      "completed": false,
      "created_at": "2025-02-12T15:31:00Z",
      "completed_at": null
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Buy groceries",
      "description": "",
      "completed": true,
      "created_at": "2025-02-12T15:30:00Z",
      "completed_at": "2025-02-12T16:00:00Z"
    }
  ]
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `todos` | array[Todo] | List of all todos, newest first |

Each todo object:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (UUID v4) | Unique identifier |
| `title` | string | Todo title |
| `description` | string | Todo description (may be empty) |
| `completed` | boolean | Completion status |
| `created_at` | string (ISO 8601) | Creation timestamp (UTC) |
| `completed_at` | string (ISO 8601) \| null | Completion timestamp (UTC) or null |

## Examples

### Empty list

```
GET /todos
```

**Response** (200):
```json
{
  "todos": []
}
```

### Multiple todos

```
GET /todos
```

**Response** (200):
```json
{
  "todos": [
    {
      "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "title": "Call mom",
      "description": "About birthday",
      "completed": false,
      "created_at": "2025-02-12T15:31:00Z",
      "completed_at": null
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Buy groceries",
      "description": "",
      "completed": false,
      "created_at": "2025-02-12T15:30:00Z",
      "completed_at": null
    }
  ]
}
```
