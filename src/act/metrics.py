"""Metrics collection for benchmark runs."""

import json
import re
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


def extract_token_usage(log_content: str) -> dict[str, int]:
    """Extract token usage from OpenCode logs."""
    usage = {}

    patterns = [
        (r"input[_\s]tokens?[:\s]+(\d+)", "input_tokens"),
        (r"output[_\s]tokens?[:\s]+(\d+)", "output_tokens"),
        (r"total[_\s]tokens?[:\s]+(\d+)", "total_tokens"),
    ]

    for pattern, key in patterns:
        match = re.search(pattern, log_content, re.IGNORECASE)
        if match:
            usage[key] = int(match.group(1))

    return usage


def load_container_metrics(workspace_path: Path) -> dict:
    """Load metrics written by the container entrypoint."""
    metrics_file = workspace_path / ".benchmark" / "metrics.json"
    if metrics_file.exists():
        try:
            return json.loads(metrics_file.read_text())
        except Exception:
            pass
    return {}


def collect_run_metrics(
    run_id: str,
    agent_id: str,
    workspace_path: Path,
    logs: str,
    exit_code: int,
    error: str | None = None,
) -> RunMetrics:
    """Collect all metrics for a benchmark run."""
    container_metrics = load_container_metrics(workspace_path)
    duration = container_metrics.get("duration_seconds", 0)

    token_usage = extract_token_usage(logs)

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
