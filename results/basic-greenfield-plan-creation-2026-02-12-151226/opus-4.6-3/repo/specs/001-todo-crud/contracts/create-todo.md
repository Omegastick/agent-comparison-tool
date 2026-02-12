# API Contract: Create a Todo

**Endpoint**: `POST /todos`
**User Story**: US1 - Create a Todo (P1)
**Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005

## Request

**Method**: POST
**Path**: `/todos`
**Content-Type**: `application/json`

### Request Body

```json
{
  "title": "string (required, 1-500 characters)",
  "description": "string (optional, max 2000 characters, defaults to empty string)"
}
```

### Request Schema

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `title` | string | Yes | min 1 char, max 500 chars |
| `description` | string | No | max 2000 chars, default: `""` |

## Response

### 201 Created

Returned when the todo is successfully created.

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

Returned when validation fails (empty title, title too long, description too long).

```json
{
  "detail": "Validation error message"
}
```

## Examples

### Create with title only

```
POST /todos
Content-Type: application/json

{"title": "Buy groceries"}
```

**Response** (201):
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

### Create with title and description

```
POST /todos
Content-Type: application/json

{"title": "Call mom", "description": "About birthday"}
```

**Response** (201):
```json
{
  "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "title": "Call mom",
  "description": "About birthday",
  "completed": false,
  "created_at": "2025-02-12T15:31:00Z",
  "completed_at": null
}
```

### Empty title (validation error)

```
POST /todos
Content-Type: application/json

{"title": ""}
```

**Response** (400):
```json
{
  "detail": "Title must be between 1 and 500 characters"
}
```
