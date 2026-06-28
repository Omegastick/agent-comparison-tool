"""CLI entry point for act."""

from pathlib import Path

import typer
from rich.console import Console

from .config import load_config
from .cost import Pricing, load_pricing
from .display import ProgressDisplay
from .runner import ExperimentRunner

app = typer.Typer(
    name="act",
    help="Agent Comparison Tool",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
console = Console()


def _run_experiment(
    config_path: Path, output_dir: Path, no_parallel: bool, pricing_path: Path
) -> Path:
    """Load config, run the experiment, and return the results path.

    Handles config loading, printing experiment info, and error handling.
    Raises typer.Exit(1) on failure.
    """
    try:
        config = load_config(config_path)
    except Exception as e:
        console.print(f"[red]Error loading config:[/] {e}")
        raise typer.Exit(1)

    if pricing_path.exists():
        try:
            pricing = load_pricing(pricing_path)
        except Exception as e:
            console.print(f"[red]Error loading pricing:[/] {e}")
            raise typer.Exit(1)
    else:
        console.print(
            f"[yellow]No pricing table at {pricing_path}; "
            f"reporting token counts only.[/]"
        )
        pricing = Pricing()

    if no_parallel:
        config.settings.parallel = False

    console.print(f"[bold]Running experiment:[/] {config.experiment.name}")
    console.print(f"Target: {config.target.repo}")
    console.print(f"Agents: {', '.join(a.id for a in config.agents)}")
    console.print(f"Runs per agent: {config.settings.runs_per_agent}")
    console.print()

    display = ProgressDisplay(console)
    runner = ExperimentRunner(config, output_dir, display, pricing)

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
    pricing_path: Path = typer.Option(
        Path("pricing.toml"),
        "--pricing",
        help="Path to the per-model pricing table (TOML)",
    ),
) -> None:
    """Run a model-comparison experiment."""
    _run_experiment(config_path, output_dir, no_parallel, pricing_path)


if __name__ == "__main__":
    app()
