# Quickstart: Todo CRUD API

**Branch**: `001-todo-crud` | **Date**: 2025-02-12
**Phase**: 1 - Design

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

## Setup

```bash
# Clone and enter the repository
git clone <repo-url>
cd <repo-dir>
git checkout 001-todo-crud

# Create virtual environment and install dependencies
uv sync
```

## Project Configuration (pyproject.toml)

```toml
[project]
name = "todo-api"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "httpx>=0.27",
    "ruff>=0.5",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
```

## Running the Application

```bash
# Start the development server
uv run uvicorn src.main:app --reload --port 8000

# The API is available at http://localhost:8000
# Swagger UI is available at http://localhost:8000/docs
# ReDoc is available at http://localhost:8000/redoc
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run tests for a specific user story
uv run pytest tests/test_create_todo.py

# Run with coverage (if pytest-cov is installed)
uv run pytest --cov=src
```

## Linting and Formatting

```bash
# Check linting
uv run ruff check src/ tests/

# Auto-fix linting issues
uv run ruff check --fix src/ tests/

# Format code
uv run ruff format src/ tests/
```

## Quick Verification

After starting the server, verify it works:

```bash
# Create a todo
curl -X POST http://localhost:8000/todos \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy groceries"}'

# List all todos
curl http://localhost:8000/todos

# Get a specific todo (replace {id} with actual UUID from create response)
curl http://localhost:8000/todos/{id}

# Update a todo
curl -X PATCH http://localhost:8000/todos/{id} \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy organic groceries"}'

# Mark complete
curl -X PATCH http://localhost:8000/todos/{id}/complete

# Mark incomplete
curl -X PATCH http://localhost:8000/todos/{id}/incomplete

# Delete a todo
curl -X DELETE http://localhost:8000/todos/{id}
```

## Database

- SQLite database file is created automatically at `todos.db` in the project root on first startup
- No migration tooling needed — single CREATE TABLE statement runs at app startup
- To reset the database, delete `todos.db` and restart the server

## TDD Workflow

Per the project constitution, all development follows strict TDD:

1. **Red**: Write a failing test for the next acceptance scenario
2. **Green**: Write the minimum code to make the test pass
3. **Refactor**: Clean up while keeping tests green

```bash
# Example TDD cycle for US1 (Create Todo):
# 1. Write test in tests/test_create_todo.py
# 2. Run tests (should fail): uv run pytest tests/test_create_todo.py
# 3. Implement in src/routes.py, src/database.py, src/models.py
# 4. Run tests (should pass): uv run pytest tests/test_create_todo.py
# 5. Refactor, run full suite: uv run pytest
```
