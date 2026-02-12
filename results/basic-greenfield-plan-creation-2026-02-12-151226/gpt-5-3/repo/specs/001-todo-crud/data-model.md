# Data Model: Todo

- Table: `todos`
- Columns:
  - `id` TEXT PRIMARY KEY (UUID v4)
  - `title` TEXT NOT NULL (1-500 chars)
  - `description` TEXT NULL (0-2000 chars)
  - `completed` INTEGER NOT NULL DEFAULT 0 (0=false,1=true)
  - `created_at` TEXT NOT NULL (ISO8601 UTC)
  - `completed_at` TEXT NULL (ISO8601 UTC or NULL)
