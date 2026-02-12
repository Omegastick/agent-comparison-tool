# Contract: List All Todos

**Endpoint**: `GET /todos`
**Priority**: P1

## Request

No request body. No query parameters.

## Responses

### 200 OK

Always returned (even for empty databases).

**Empty database**:
```json
[]
```

**With todos**:
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Buy groceries",
    "description": null,
    "completed": false,
    "created_at": "2026-02-12T15:30:00Z",
    "completed_at": null
  },
  {
    "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "title": "Call mom",
    "description": "About birthday",
    "completed": true,
    "created_at": "2026-02-12T14:00:00Z",
    "completed_at": "2026-02-12T15:00:00Z"
  }
]
```

**Invariants**:
- Response is always a JSON array (never `null`)
- Todos are ordered by `created_at` descending (newest first)
- Each element has the full Todo shape (id, title, description, completed, created_at, completed_at)
