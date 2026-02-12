# Quickstart

## Run

1. Create venv with uv and install deps:
   - `uv venv && source .venv/bin/activate && uv pip install fastapi uvicorn pydantic pytest httpx ruff`
2. Start API: `uvicorn src.api.todos:app --reload`

## Test (TDD)

- Run all tests: `pytest -q`
- Red-Green-Refactor per acceptance scenarios.
