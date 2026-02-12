# Quickstart

Prereqs: Python 3.11+, uv, pytest.

1. Create venv and install deps
   - `uv venv && uv pip install fastapi pydantic pytest httpx ruff`
2. Run tests (TDD): `pytest -q`
3. Start API: `uvicorn src.api.app:app --reload`
4. Try endpoints: `curl -X POST localhost:8000/todos -d '{"title":"Buy milk"}' -H 'Content-Type: application/json'`
