# Data Model: Todo

Table: `todos`

- id: TEXT (UUID v4, PK)
- title: TEXT (1-500 chars)
- description: TEXT (<=2000 chars, nullable)
- completed: INTEGER (0/1, default 0)
- created_at: TEXT (ISO8601 UTC)
- completed_at: TEXT (ISO8601 UTC, nullable)

Indexes:
- created_at DESC (for listing)
