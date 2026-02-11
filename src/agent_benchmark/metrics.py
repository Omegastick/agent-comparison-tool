"""Metrics collection for benchmark runs."""

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GitDiffStats:
    """Git diff statistics."""

    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0


@dataclass
class PlanMetrics:
    """Metrics about a generated plan."""

    total_lines: int = 0
    sections: int = 0
    tasks: int = 0
    files_referenced: list[str] = field(default_factory=list)


@dataclass
class RunMetrics:
    """Complete metrics for a benchmark run."""

    run_id: str
    agent_id: str
    exit_code: int
    duration_seconds: float
    has_commits: bool
    git_diff: GitDiffStats
    plan: PlanMetrics
    token_usage: dict[str, int] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "exit_code": self.exit_code,
            "duration_seconds": self.duration_seconds,
            "has_commits": self.has_commits,
            "git_diff": {
                "files_changed": self.git_diff.files_changed,
                "insertions": self.git_diff.insertions,
                "deletions": self.git_diff.deletions,
            },
            "plan": {
                "total_lines": self.plan.total_lines,
                "sections": self.plan.sections,
                "tasks": self.plan.tasks,
                "files_referenced": self.plan.files_referenced,
            },
            "token_usage": self.token_usage,
            "error": self.error,
        }


def collect_git_metrics(repo_path: Path) -> tuple[bool, GitDiffStats]:
    """Collect git metrics from a repository."""
    has_commits = False
    diff_stats = GitDiffStats()

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        has_commits = result.returncode == 0

        if has_commits:
            result = subprocess.run(
                ["git", "diff", "--stat", "HEAD~1"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                diff_stats = parse_diff_stat(result.stdout)
    except Exception:
        pass

    return has_commits, diff_stats


def parse_diff_stat(diff_output: str) -> GitDiffStats:
    """Parse git diff --stat output."""
    stats = GitDiffStats()

    lines = diff_output.strip().split("\n")
    if not lines:
        return stats

    summary_line = lines[-1]
    match = re.search(
        r"(\d+) files? changed(?:, (\d+) insertions?\(\+\))?(?:, (\d+) deletions?\(-\))?",
        summary_line,
    )
    if match:
        stats.files_changed = int(match.group(1))
        stats.insertions = int(match.group(2)) if match.group(2) else 0
        stats.deletions = int(match.group(3)) if match.group(3) else 0

    return stats


def collect_plan_metrics(workspace_path: Path) -> PlanMetrics:
    """Analyze plan files in the workspace."""
    metrics = PlanMetrics()

    plan_patterns = ["*.md", "plan.txt", "PLAN.md", "PLAN.txt"]
    plan_files = []
    repo_path = workspace_path / "repo"

    for pattern in plan_patterns:
        plan_files.extend(repo_path.glob(pattern))

    if not plan_files:
        return metrics

    for plan_file in plan_files:
        try:
            content = plan_file.read_text()
            metrics.total_lines += len(content.split("\n"))
            metrics.sections += len(re.findall(r"^#+\s", content, re.MULTILINE))
            metrics.tasks += len(re.findall(r"^[-*]\s\[[ x]\]", content, re.MULTILINE))
            metrics.files_referenced.extend(
                re.findall(r"`([^`]+\.[a-z]+)`", content)
            )
        except Exception:
            pass

    metrics.files_referenced = list(set(metrics.files_referenced))
    return metrics


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

    repo_path = workspace_path / "repo"
    has_commits, git_diff = collect_git_metrics(repo_path)
    plan_metrics = collect_plan_metrics(workspace_path)
    token_usage = extract_token_usage(logs)

    return RunMetrics(
        run_id=run_id,
        agent_id=agent_id,
        exit_code=exit_code,
        duration_seconds=duration,
        has_commits=has_commits,
        git_diff=git_diff,
        plan=plan_metrics,
        token_usage=token_usage,
        error=error,
    )


def save_metrics(metrics: RunMetrics, output_path: Path) -> None:
    """Save metrics to a JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(metrics.to_dict(), f, indent=2)
