"""CLI entry point for agent-benchmark."""

from pathlib import Path

import typer
from rich.console import Console

from .analysis import analyze_results, generate_report
from .config import load_config
from .display import ProgressDisplay
from .runner import ExperimentRunner

app = typer.Typer(
    name="agent-benchmark",
    help="Benchmark framework for AI coding agents",
    no_args_is_help=True,
)
console = Console()


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
def analyze(
    results_dir: Path = typer.Argument(
        ...,
        help="Path to experiment results directory",
        exists=True,
    ),
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file for the report (defaults to results_dir/analysis.md)",
    ),
) -> None:
    """Analyze experiment results and generate a report."""
    if output is None:
        output = results_dir / "analysis.md"

    console.print(f"[bold]Analyzing results:[/] {results_dir}")

    try:
        analysis = analyze_results(results_dir)
        report_path = generate_report(analysis, output)
        console.print(f"[green]Report saved to:[/] {report_path}")
    except Exception as e:
        console.print(f"[red]Analysis failed:[/] {e}")
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


@app.command()
def show(
    run_dir: Path = typer.Argument(
        ...,
        help="Path to a specific run directory",
        exists=True,
    ),
) -> None:
    """Show details for a specific run."""
    import json

    metrics_file = run_dir / "metrics.json"
    log_file = run_dir / ".benchmark" / "run.log"

    if metrics_file.exists():
        console.print("[bold]Metrics:[/]")
        try:
            metrics = json.loads(metrics_file.read_text())
            for key, value in metrics.items():
                console.print(f"  {key}: {value}")
        except Exception as e:
            console.print(f"  [red]Error reading metrics:[/] {e}")
    else:
        console.print("[yellow]No metrics file found[/]")

    console.print()

    if log_file.exists():
        console.print("[bold]Run log:[/]")
        console.print(log_file.read_text()[:2000])
        if log_file.stat().st_size > 2000:
            console.print("[dim]... (truncated)[/]")
    elif (run_dir / "run.log").exists():
        log_file = run_dir / "run.log"
        console.print("[bold]Run log:[/]")
        console.print(log_file.read_text()[:2000])
        if log_file.stat().st_size > 2000:
            console.print("[dim]... (truncated)[/]")
    else:
        console.print("[yellow]No log file found[/]")


if __name__ == "__main__":
    app()
