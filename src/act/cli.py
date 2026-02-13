"""CLI entry point for act."""

from pathlib import Path

import typer
from rich.console import Console

from .config import load_config
from .display import ProgressDisplay
from .runner import ExperimentRunner

app = typer.Typer(
    name="act",
    help="Agent Comparison Tool",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
console = Console()


def _run_experiment(config_path: Path, output_dir: Path, no_parallel: bool) -> Path:
    """Load config, run the experiment, and return the results path.

    Handles config loading, printing experiment info, and error handling.
    Raises typer.Exit(1) on failure.
    """
    try:
        config = load_config(config_path)
    except Exception as e:
        console.print(f"[red]Error loading config:[/] {e}")
        raise typer.Exit(1)

    if no_parallel:
        config.settings.parallel = False

    console.print(f"[bold]Running experiment:[/] {config.experiment.name}")
    console.print(f"Target: {config.target.repo}")
    console.print(f"Agents: {', '.join(a.id for a in config.agents)}")
    console.print(f"Runs per agent: {config.settings.runs_per_agent}")
    console.print()

    display = ProgressDisplay(console)
    runner = ExperimentRunner(config, output_dir, display)

    try:
        results_path = runner.run()
        console.print()
        console.print(f"[green]Results saved to:[/] {results_path}")
        return results_path
    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Experiment cancelled[/]")
        runner.cleanup()
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Experiment failed:[/] {e}")
        runner.cleanup()
        raise typer.Exit(1)


@app.command()
def run(
    config_path: Path = typer.Argument(
        ...,
        help="Path to experiment configuration file (TOML)",
        exists=True,
    ),
    output_dir: Path = typer.Option(
        Path("results"),
        "--output",
        "-o",
        help="Directory to store results",
    ),
    no_parallel: bool = typer.Option(
        False,
        "--no-parallel",
        help="Run experiments sequentially instead of in parallel",
    ),
) -> None:
    """Run a benchmark experiment."""
    _run_experiment(config_path, output_dir, no_parallel)


@app.command()
def analyze(
    results_dir: Path = typer.Argument(
        ...,
        help="Path to experiment results directory",
        exists=True,
    ),
) -> None:
    """Analyze experiment results using AI.

    Runs an AI agent to analyze the benchmark results and generate:
    - analysis.md: Detailed analysis report
    - stats.json: Key statistics

    Requires [analysis] section in the experiment config.
    """
    from .analysis import run_ai_analysis

    console.print(f"[bold]Analyzing results:[/] {results_dir}")

    config_file = results_dir / "config.toml"
    if not config_file.exists():
        console.print("[red]No config.toml found in results directory[/]")
        raise typer.Exit(1)

    try:
        config = load_config(config_file)
    except Exception as e:
        console.print(f"[red]Error loading config:[/] {e}")
        raise typer.Exit(1)

    if not config.analysis or not config.analysis.prompt:
        console.print("[red]No [analysis] section with prompt configured[/]")
        console.print("Add an [analysis] section to your experiment config:")
        console.print("  [analysis]")
        console.print('  model = "anthropic/claude-sonnet-4-5"')
        console.print('  prompt = "Your analysis criteria here"')
        raise typer.Exit(1)

    console.print(f"[bold]Running AI analysis with {config.analysis.model}...[/]")
    console.print()

    success = run_ai_analysis(
        results_path=results_dir,
        model=config.analysis.model,
        prompt=config.analysis.prompt,
    )

    if success:
        console.print()
        console.print(f"[green]Analysis complete:[/] {results_dir / 'analysis.md'}")
    else:
        raise typer.Exit(1)


@app.command("run-and-analyze")
def run_and_analyze(
    config_path: Path = typer.Argument(
        ...,
        help="Path to experiment configuration file (TOML)",
        exists=True,
    ),
    output_dir: Path = typer.Option(
        Path("results"),
        "--output",
        "-o",
        help="Directory to store results",
    ),
    no_parallel: bool = typer.Option(
        False,
        "--no-parallel",
        help="Run experiments sequentially instead of in parallel",
    ),
) -> None:
    """Run a benchmark experiment and then analyze the results.

    Combines 'run' and 'analyze' commands into a single workflow.
    Requires [analysis] section in the experiment config.
    """
    from .analysis import run_ai_analysis

    try:
        config = load_config(config_path)
    except Exception as e:
        console.print(f"[red]Error loading config:[/] {e}")
        raise typer.Exit(1)

    if not config.analysis or not config.analysis.prompt:
        console.print("[red]No [analysis] section with prompt configured[/]")
        console.print("Add an [analysis] section to your experiment config for run-and-analyze")
        raise typer.Exit(1)

    results_path = _run_experiment(config_path, output_dir, no_parallel)

    console.print()
    console.print(f"[bold]Running AI analysis with {config.analysis.model}...[/]")
    console.print()

    success = run_ai_analysis(
        results_path=results_path,
        model=config.analysis.model,
        prompt=config.analysis.prompt,
    )

    if success:
        console.print()
        console.print(f"[green]Analysis complete:[/] {results_path / 'analysis.md'}")
    else:
        raise typer.Exit(1)


@app.command("list")
def list_experiments(
    results_dir: Path = typer.Option(
        Path("results"),
        "--dir",
        "-d",
        help="Results directory to scan",
    ),
) -> None:
    """List past experiments."""
    if not results_dir.exists():
        console.print("[yellow]No results directory found[/]")
        return

    experiments = sorted(results_dir.iterdir())
    experiments = [e for e in experiments if e.is_dir()]

    if not experiments:
        console.print("[yellow]No experiments found[/]")
        return

    console.print("[bold]Past experiments:[/]")
    for exp in experiments:
        config_file = exp / "config.toml"
        name = exp.name
        if config_file.exists():
            try:
                config = load_config(config_file)
                name = f"{config.experiment.name} ({exp.name})"
            except Exception:
                pass
        console.print(f"  - {name}")


if __name__ == "__main__":
    app()
