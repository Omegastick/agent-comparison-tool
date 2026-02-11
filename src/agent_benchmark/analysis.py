"""Analysis and report generation for benchmark results."""

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .metrics import RunMetrics


@dataclass
class AgentSummary:
    """Summary statistics for a single agent."""

    agent_id: str
    total_runs: int
    successful_runs: int
    failed_runs: int
    avg_duration: float
    avg_plan_lines: float
    avg_plan_sections: float
    total_tokens: int


@dataclass
class ExperimentAnalysis:
    """Complete analysis of an experiment."""

    experiment_name: str
    results_path: Path
    agent_summaries: dict[str, AgentSummary] = field(default_factory=dict)
    all_metrics: list[RunMetrics] = field(default_factory=list)
    comparison_notes: str = ""


def load_run_metrics(run_path: Path) -> RunMetrics | None:
    """Load metrics from a run directory."""
    metrics_file = run_path / "metrics.json"
    if not metrics_file.exists():
        return None

    try:
        data = json.loads(metrics_file.read_text())
        from .metrics import GitDiffStats, PlanMetrics

        return RunMetrics(
            run_id=data["run_id"],
            agent_id=data["agent_id"],
            exit_code=data["exit_code"],
            duration_seconds=data["duration_seconds"],
            has_commits=data["has_commits"],
            git_diff=GitDiffStats(
                files_changed=data["git_diff"]["files_changed"],
                insertions=data["git_diff"]["insertions"],
                deletions=data["git_diff"]["deletions"],
            ),
            plan=PlanMetrics(
                total_lines=data["plan"]["total_lines"],
                sections=data["plan"]["sections"],
                tasks=data["plan"]["tasks"],
                files_referenced=data["plan"]["files_referenced"],
            ),
            token_usage=data.get("token_usage", {}),
            error=data.get("error"),
        )
    except Exception:
        return None


def analyze_results(results_path: Path) -> ExperimentAnalysis:
    """Analyze all results in an experiment directory."""
    config_file = results_path / "config.toml"
    experiment_name = results_path.name

    if config_file.exists():
        try:
            from .config import load_config

            config = load_config(config_file)
            experiment_name = config.experiment.name
        except Exception:
            pass

    analysis = ExperimentAnalysis(
        experiment_name=experiment_name,
        results_path=results_path,
    )

    run_dirs = [d for d in results_path.iterdir() if d.is_dir() and d.name != ".benchmark"]

    for run_dir in run_dirs:
        metrics = load_run_metrics(run_dir)
        if metrics:
            analysis.all_metrics.append(metrics)

    agent_runs: dict[str, list[RunMetrics]] = {}
    for metrics in analysis.all_metrics:
        if metrics.agent_id not in agent_runs:
            agent_runs[metrics.agent_id] = []
        agent_runs[metrics.agent_id].append(metrics)

    for agent_id, runs in agent_runs.items():
        successful = [r for r in runs if r.exit_code == 0]
        failed = [r for r in runs if r.exit_code != 0]

        avg_duration = sum(r.duration_seconds for r in successful) / len(successful) if successful else 0
        avg_plan_lines = sum(r.plan.total_lines for r in successful) / len(successful) if successful else 0
        avg_plan_sections = sum(r.plan.sections for r in successful) / len(successful) if successful else 0
        total_tokens = sum(
            r.token_usage.get("total_tokens", 0)
            for r in runs
        )

        analysis.agent_summaries[agent_id] = AgentSummary(
            agent_id=agent_id,
            total_runs=len(runs),
            successful_runs=len(successful),
            failed_runs=len(failed),
            avg_duration=avg_duration,
            avg_plan_lines=avg_plan_lines,
            avg_plan_sections=avg_plan_sections,
            total_tokens=total_tokens,
        )

    return analysis


def generate_report(analysis: ExperimentAnalysis, output_path: Path) -> Path:
    """Generate a Markdown report from the analysis."""
    lines = [
        f"# Experiment Analysis: {analysis.experiment_name}",
        "",
        f"Results path: `{analysis.results_path}`",
        "",
        "## Summary",
        "",
        f"- Total runs: {len(analysis.all_metrics)}",
        f"- Agents tested: {len(analysis.agent_summaries)}",
        "",
        "## Agent Performance",
        "",
        "| Agent | Runs | Success | Avg Duration | Avg Plan Lines | Avg Sections |",
        "|-------|------|---------|--------------|----------------|--------------|",
    ]

    for summary in analysis.agent_summaries.values():
        lines.append(
            f"| {summary.agent_id} | {summary.total_runs} | "
            f"{summary.successful_runs}/{summary.total_runs} | "
            f"{summary.avg_duration:.1f}s | "
            f"{summary.avg_plan_lines:.0f} | "
            f"{summary.avg_plan_sections:.0f} |"
        )

    lines.extend([
        "",
        "## Individual Runs",
        "",
    ])

    for metrics in sorted(analysis.all_metrics, key=lambda m: m.run_id):
        status = "Success" if metrics.exit_code == 0 else f"Failed (exit {metrics.exit_code})"
        lines.extend([
            f"### {metrics.run_id}",
            "",
            f"- Status: {status}",
            f"- Duration: {metrics.duration_seconds:.1f}s",
            f"- Has commits: {metrics.has_commits}",
            f"- Plan lines: {metrics.plan.total_lines}",
            f"- Plan sections: {metrics.plan.sections}",
            f"- Plan tasks: {metrics.plan.tasks}",
        ])

        if metrics.git_diff.files_changed > 0:
            lines.append(
                f"- Git changes: {metrics.git_diff.files_changed} files, "
                f"+{metrics.git_diff.insertions}/-{metrics.git_diff.deletions}"
            )

        if metrics.error:
            lines.append(f"- Error: {metrics.error}")

        lines.append("")

    if analysis.comparison_notes:
        lines.extend([
            "## AI Analysis Notes",
            "",
            analysis.comparison_notes,
            "",
        ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))

    json_path = output_path.with_suffix(".json")
    json_data = {
        "experiment_name": analysis.experiment_name,
        "results_path": str(analysis.results_path),
        "agent_summaries": {
            agent_id: {
                "agent_id": s.agent_id,
                "total_runs": s.total_runs,
                "successful_runs": s.successful_runs,
                "failed_runs": s.failed_runs,
                "avg_duration": s.avg_duration,
                "avg_plan_lines": s.avg_plan_lines,
                "avg_plan_sections": s.avg_plan_sections,
                "total_tokens": s.total_tokens,
            }
            for agent_id, s in analysis.agent_summaries.items()
        },
        "runs": [m.to_dict() for m in analysis.all_metrics],
    }
    json_path.write_text(json.dumps(json_data, indent=2))

    return output_path


def run_ai_analysis(results_path: Path, opencode_path: str = "opencode") -> str:
    """Run OpenCode to analyze the results and generate comparison notes."""
    prompt = f"""Analyze the benchmark results in {results_path}.

Compare the plans generated by each agent across all runs. Consider:
1. Completeness: Did each agent address all requirements?
2. Accuracy: Correct interpretation of the spec?
3. Consistency: How much variance between runs of the same agent?
4. Quality: Overall plan quality and feasibility

Provide a structured comparison report."""

    try:
        result = subprocess.run(
            [opencode_path, "--prompt", prompt, "--yes"],
            cwd=results_path,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        return "AI analysis timed out."
    except FileNotFoundError:
        return "OpenCode not found. Install it to enable AI analysis."
    except Exception as e:
        return f"AI analysis failed: {e}"
