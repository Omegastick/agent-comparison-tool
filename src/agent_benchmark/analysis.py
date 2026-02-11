"""Analysis and report generation for benchmark results."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from .metrics import RunMetrics


ANALYSIS_SYSTEM_PROMPT = """You are analyzing AI coding agent benchmark results.

## Directory Structure
Your working directory is /workspace/results which contains:
- config.toml: Original benchmark configuration
- {agent-id}-{run-number}/: Individual run directories containing:
  - metrics.json: Quantitative metrics (duration, exit_code, plan stats)
  - .benchmark/run.log: Agent execution log
  - repo/: Repository state after agent execution
    - .specify/specs/*/plan.md: Generated plan (if created)

## Metrics Available
Each run's metrics.json contains:
- run_id, agent_id: Identifiers
- exit_code: 0 = success
- duration_seconds: Execution time
- has_commits: Whether agent made git commits
- git_diff: files_changed, insertions, deletions
- plan: total_lines, sections, tasks, files_referenced

## Your Approach
1. First, list all run directories to understand what needs to be analyzed
2. Create a todo list of tasks - one task per run directory to inspect
3. For each run directory:
   - Read metrics.json for quantitative data
   - Read the generated plan if it exists
   - Note key observations
4. After inspecting all runs, synthesize your findings
5. Write the output files, iterating until complete

## Output Files
You must write two files:

1. /workspace/results/analysis.md - A well-structured markdown report with:
   - Executive Summary (2-3 sentences)
   - Agent-by-Agent Analysis (detailed qualitative analysis)
   - Comparative Rankings
   - Notable Observations

2. /workspace/results/stats.json - A JSON file with key statistics:
   - experiment_name: Name from config
   - total_runs: Number of runs
   - agents: Object with per-agent stats (success_rate, avg_duration, etc.)
   - rankings: Ordered list of agents by performance
   - Any other relevant aggregate statistics

## User Criteria
The user will provide specific criteria to evaluate. Focus your analysis on those criteria.
"""


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


def run_ai_analysis(
    results_path: Path,
    model: str = "anthropic/claude-opus-4-5",
    prompt: str | None = None,
) -> bool:
    """Run OpenCode in a container to analyze results and write analysis.md.

    The agent writes directly to results_path/analysis.md.

    Args:
        results_path: Path to the results directory to analyze.
        model: Model to use for analysis.
        prompt: Custom analysis prompt. If None, uses a default prompt.

    Returns:
        True if analysis succeeded, False otherwise.
    """
    from .container import AnalysisContainerConfig, ContainerManager

    if prompt is None:
        prompt = """Compare the plans generated by each agent. Consider:
1. Completeness: Did each agent address all spec requirements?
2. Accuracy: Correct interpretation of the spec?
3. Consistency: How much variance between runs of the same agent?
4. Quality: Overall plan quality and feasibility"""

    config = AnalysisContainerConfig(
        results_path=results_path.resolve(),
        model=model,
        prompt=prompt,
        system_prompt=ANALYSIS_SYSTEM_PROMPT,
        timeout_seconds=600,
    )

    manager = ContainerManager()
    try:
        result = manager.run_analysis(config)

        if result.error:
            print(f"AI analysis failed: {result.error}")
            return False

        if result.exit_code != 0:
            print(f"AI analysis failed with exit code {result.exit_code}")
            return False

        return True
    except Exception as e:
        print(f"AI analysis failed: {e}")
        return False
    finally:
        manager.cleanup()
