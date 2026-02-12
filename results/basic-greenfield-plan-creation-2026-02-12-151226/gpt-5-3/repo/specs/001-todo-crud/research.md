# Phase 0 Research: Todo CRUD API

- Goal: Identify simplest viable approach using FastAPI + SQLite that satisfies spec and constitution.
- Notes:
  - Use `sqlite3` with parameterized queries.
  - Pydantic v2 models for inputs/outputs; strict validation on lengths and UUID.
  - Service layer mediates validation and DB access; endpoints remain thin.
