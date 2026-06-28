rebuild:
    docker rmi -f act-agent 2>/dev/null || true
    docker build -t act-agent docker/

lint:
    uv run ruff check --fix src/ tests/
    uv run ruff format src/ tests/
    uv run ty check --error-on-warning

test:
    uv run pytest tests/
