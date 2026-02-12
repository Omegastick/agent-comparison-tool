# Contract: List All Todos

**Endpoint**: `GET /todos`
**User Story**: 2 (Priority: P1)

## Request

No request body. No query parameters.

## Response

### 200 OK

**Content-Type**: `application/json`

```json
[
  {
    "id": "uuid-v4-string",
    "title": "string",
    "description": "string | null",
    "completed": false,
    "created_at": "ISO 8601 UTC datetime",
    "completed_at": "ISO 8601 UTC datetime | null"
  }
]
```

**Response Model**: `list[TodoResponse]`

**Invariants**:
- Always returns a JSON array (even if empty)
- Todos are ordered by `created_at` descending (newest first)
- Every todo in the response contains all 6 fields

### Empty Database

```json
[]
```

## Acceptance Scenarios

1. Empty database -> 200 with `[]`
2. 3 todos exist -> 200 with all 3 todos
3. Todos are always ordered by `created_at` descending
