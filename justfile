rebuild:
    docker rmi -f act-opencode 2>/dev/null || true
    docker build -t act-opencode docker/

lint:
    uv run ruff check src/ tests/
    uv run ruff format --check src/ tests/

fmt:
    uv run ruff check --fix src/ tests/
    uv run ruff format src/ tests/

test:
    uv run pytest tests/
