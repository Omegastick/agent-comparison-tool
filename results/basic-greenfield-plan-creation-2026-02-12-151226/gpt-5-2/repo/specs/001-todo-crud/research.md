# Phase 0 Research: Todo CRUD API

- Domain: simple REST API over SQLite; avoid ORMs for simplicity.
- Validation: Pydantic v2 models with field constraints (title 1-500, description <=2000).
- IDs: UUID v4 generated server-side; validate path IDs format.
- Error handling: consistent JSON errors; 400 for validation, 404 for not found.
- Concurrency: SQLite default locking is sufficient; last write wins.
