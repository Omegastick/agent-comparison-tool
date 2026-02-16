"""Metrics collection for benchmark runs."""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RunMetrics:
    """Complete metrics for a benchmark run."""

    run_id: str
    agent_id: str
    exit_code: int
    duration_seconds: float
    token_usage: dict[str, int] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "exit_code": self.exit_code,
            "duration_seconds": self.duration_seconds,
            "token_usage": self.token_usage,
            "error": self.error,
        }


def load_container_metrics(workspace_path: Path) -> dict:
    """Load metrics written by the container entrypoint."""
    metrics_file = workspace_path / "metrics.json"
    if metrics_file.exists():
        try:
            return json.loads(metrics_file.read_text())
        except Exception:
            pass
    return {}


def extract_token_usage_from_session(workspace_path: Path) -> dict[str, int]:
    """Extract token usage from an OpenCode session export.

    Reads opencode_session.json and sums token counts across all messages.
    """
    session_file = workspace_path / "opencode_session.json"
    try:
        session = json.loads(session_file.read_text())
        messages = session.get("messages", []) if isinstance(session, dict) else session
    except Exception:
        return {}

    totals: dict[str, int] = {
        "total": 0,
        "input": 0,
        "output": 0,
        "reasoning": 0,
        "cache_read": 0,
        "cache_write": 0,
    }

    for msg in messages:
        tokens = (msg.get("info") or {}).get("tokens")
        if not tokens:
            continue
        totals["total"] += tokens.get("total", 0)
        totals["input"] += tokens.get("input", 0)
        totals["output"] += tokens.get("output", 0)
        totals["reasoning"] += tokens.get("reasoning", 0)
        cache = tokens.get("cache") or {}
        totals["cache_read"] += cache.get("read", 0)
        totals["cache_write"] += cache.get("write", 0)

    return totals


def collect_run_metrics(
    run_id: str,
    agent_id: str,
    workspace_path: Path,
    exit_code: int,
    error: str | None = None,
) -> RunMetrics:
    """Collect all metrics for a benchmark run."""
    container_metrics = load_container_metrics(workspace_path)
    duration = container_metrics.get("duration_seconds", 0)

    token_usage = extract_token_usage_from_session(workspace_path)

    return RunMetrics(
        run_id=run_id,
        agent_id=agent_id,
        exit_code=exit_code,
        duration_seconds=duration,
        token_usage=token_usage,
        error=error,
    )


def save_metrics(metrics: RunMetrics, output_path: Path) -> None:
    """Save metrics to a JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(metrics.to_dict(), f, indent=2)
