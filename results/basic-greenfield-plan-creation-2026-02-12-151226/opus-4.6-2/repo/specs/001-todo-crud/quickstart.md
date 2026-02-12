# Quickstart: Todo CRUD API

**Feature**: 001-todo-crud | **Date**: 2026-02-12

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

## Setup

```bash
# Clone and switch to feature branch
git checkout 001-todo-crud

# Install dependencies
uv sync

# Run the test suite (TDD - tests first)
uv run pytest

# Start the development server
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## Verify It Works

```bash
# Create a todo
curl -X POST http://localhost:8000/todos \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy groceries", "description": "Milk, eggs, bread"}'

# List all todos
curl http://localhost:8000/todos

# Get a specific todo (replace {id} with actual UUID)
curl http://localhost:8000/todos/{id}

# Update a todo
curl -X PATCH http://localhost:8000/todos/{id} \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy groceries and snacks"}'

# Mark complete
curl -X PATCH http://localhost:8000/todos/{id}/complete

# Mark incomplete
curl -X PATCH http://localhost:8000/todos/{id}/incomplete

# Delete a todo
curl -X DELETE http://localhost:8000/todos/{id}
```

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
pyproject.toml           # Project configuration
src/
├── __init__.py
├── main.py              # FastAPI app factory + entrypoint
├── database.py          # SQLite connection + table init
├── models.py            # Pydantic models
└── routes/
    ├── __init__.py
    └── todos.py         # /todos endpoint handlers

tests/
├── conftest.py          # Shared test fixtures
├── contract/
│   └── test_todo_contracts.py
├── integration/
│   └── test_todo_api.py
└── unit/
    ├── test_models.py
    └── test_database.py
```

## Development Workflow

This project follows strict TDD (constitution requirement):

1. Write a failing test for the next requirement
2. Run `uv run pytest` -- confirm it fails (RED)
3. Write the minimum code to make it pass
4. Run `uv run pytest` -- confirm it passes (GREEN)
5. Refactor if needed, re-run tests (REFACTOR)
6. Repeat

## Linting

```bash
# Check code style
uv run ruff check src/ tests/

# Auto-fix issues
uv run ruff check --fix src/ tests/

# Format code
uv run ruff format src/ tests/
```
