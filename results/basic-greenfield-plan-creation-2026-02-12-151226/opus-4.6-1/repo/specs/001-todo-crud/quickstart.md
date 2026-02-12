# Quickstart: Todo CRUD API

**Feature**: `001-todo-crud` | **Date**: 2026-02-12 | **Phase**: 1

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

## Project Setup

```bash
# Initialize project with uv
uv init --name todo-api --python 3.11

# Add dependencies
uv add fastapi uvicorn[standard]

# Add dev dependencies
uv add --dev pytest httpx pytest-asyncio ruff
```

## pyproject.toml Configuration

```toml
[project]
name = "todo-api"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.20.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "httpx>=0.24.0",
    "pytest-asyncio>=0.21.0",
    "ruff>=0.1.0",
]

[tool.ruff]
line-length = 88
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

## Running the Application

```bash
# Start the development server
uv run uvicorn src.main:app --reload --port 8000

# Server runs at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
# OpenAPI JSON at http://localhost:8000/openapi.json
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run tests for a specific user story
uv run pytest tests/test_create_todo.py -v

# Run with coverage (if pytest-cov is added)
uv run pytest --cov=src
```

## Linting

```bash
# Check code style
uv run ruff check src/ tests/

# Auto-fix style issues
uv run ruff check --fix src/ tests/

# Format code
uv run ruff format src/ tests/
```

## API Usage Examples

### Create a Todo

```bash
curl -X POST http://localhost:8000/todos \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy groceries", "description": "Milk, eggs, bread"}'
```

**Response** (201 Created):
```json
{
  "id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
  "title": "Buy groceries",
  "description": "Milk, eggs, bread",
  "completed": false,
  "created_at": "2026-02-12T10:30:00",
  "completed_at": null
}
```

### List All Todos

```bash
curl http://localhost:8000/todos
```

**Response** (200 OK):
```json
[
  {
    "id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
    "title": "Buy groceries",
    "description": "Milk, eggs, bread",
    "completed": false,
    "created_at": "2026-02-12T10:30:00",
    "completed_at": null
  }
]
```

### Get a Single Todo

```bash
curl http://localhost:8000/todos/a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d
```

### Update a Todo

```bash
curl -X PATCH http://localhost:8000/todos/a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy groceries and snacks"}'
```

### Delete a Todo

```bash
curl -X DELETE http://localhost:8000/todos/a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d
```

**Response**: 204 No Content (empty body)

### Mark Todo Complete

```bash
curl -X PATCH http://localhost:8000/todos/a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d/complete
```

### Mark Todo Incomplete

```bash
curl -X PATCH http://localhost:8000/todos/a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d/incomplete
```

## TDD Workflow (Constitution Requirement)

For each user story, follow this cycle:

1. **Red**: Write a failing test in `tests/test_<story>.py`
2. **Green**: Implement the minimum code in `src/` to make the test pass
3. **Refactor**: Clean up while keeping tests green

```bash
# Example TDD cycle for User Story 1 (Create Todo)

# 1. Write failing test
uv run pytest tests/test_create_todo.py -v  # Should FAIL

# 2. Implement route handler
uv run pytest tests/test_create_todo.py -v  # Should PASS

# 3. Refactor and verify
uv run ruff check src/ tests/
uv run pytest -v  # All tests should still PASS
```

## Database

The SQLite database file is auto-created at `todos.db` in the project root on first startup. No manual setup required.

To reset the database:
```bash
rm todos.db
# Restart the server - database will be recreated
```
