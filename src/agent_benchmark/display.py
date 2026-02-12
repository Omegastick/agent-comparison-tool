"""Rich TUI display for benchmark progress."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from rich.console import Console, ConsoleOptions, RenderableType, RenderResult
from rich.live import Live
from rich.panel import Panel
from rich.table import Table


class _DynamicRenderable:
    """Wraps a callable so Rich re-evaluates it on every render."""

    def __init__(self, fn: Callable[[], RenderableType]) -> None:
        self._fn = fn

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        yield self._fn()


class RunStatus(Enum):
    """Status of a benchmark run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class RunState:
    """State of a single benchmark run."""

    run_id: str
    agent_id: str
    run_number: int
    status: RunStatus = RunStatus.PENDING
    duration: float = 0.0
    started_at: float | None = None
    error: str | None = None
    activity: str = ""


@dataclass
class ExperimentState:
    """State of the entire experiment."""

    name: str
    total_runs: int
    runs: dict[str, RunState] = field(default_factory=dict)

    @property
    def completed_runs(self) -> int:
        return sum(
            1 for r in self.runs.values() if r.status in (RunStatus.COMPLETED, RunStatus.FAILED)
        )

    @property
    def successful_runs(self) -> int:
        return sum(1 for r in self.runs.values() if r.status == RunStatus.COMPLETED)


class ProgressDisplay:
    """Rich TUI display for experiment progress."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self.state: ExperimentState | None = None
        self._live: Live | None = None

    def start(self, experiment_name: str, total_runs: int) -> None:
        """Start the progress display."""
        self.state = ExperimentState(name=experiment_name, total_runs=total_runs)
        self._live = Live(
            _DynamicRenderable(self._make_panel), console=self.console, refresh_per_second=4
        )
        self._live.start()

    def add_run(self, run_id: str, agent_id: str, run_number: int) -> None:
        """Register a new run."""
        if self.state is None:
            raise RuntimeError("Display not started")
        self.state.runs[run_id] = RunState(
            run_id=run_id,
            agent_id=agent_id,
            run_number=run_number,
        )
        self._refresh()

    def update_run(
        self,
        run_id: str,
        status: RunStatus,
        duration: float = 0.0,
        error: str | None = None,
    ) -> None:
        """Update the status of a run."""
        if self.state is None or run_id not in self.state.runs:
            return
        run = self.state.runs[run_id]
        run.status = status
        run.duration = duration
        run.error = error
        if status == RunStatus.RUNNING:
            run.started_at = time.monotonic()
        if status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.TIMEOUT):
            run.started_at = None
            run.activity = ""
        self._refresh()

    def update_activity(self, run_id: str, activity: str) -> None:
        """Update the activity description of a running task."""
        if self.state is None or run_id not in self.state.runs:
            return
        self.state.runs[run_id].activity = activity

    def _make_panel(self) -> Panel:
        """Create the display panel."""
        if self.state is None:
            return Panel("No experiment running")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Run ID")
        table.add_column("Agent")
        table.add_column("#")
        table.add_column("Status")
        table.add_column("Duration")
        table.add_column("Activity", max_width=40, no_wrap=True)

        for run in sorted(self.state.runs.values(), key=lambda r: r.run_id):
            status_style = {
                RunStatus.PENDING: "dim",
                RunStatus.RUNNING: "yellow",
                RunStatus.COMPLETED: "green",
                RunStatus.FAILED: "red",
                RunStatus.TIMEOUT: "red",
            }.get(run.status, "")

            if run.status == RunStatus.RUNNING and run.started_at is not None:
                elapsed = time.monotonic() - run.started_at
                duration_str = f"{elapsed:.1f}s"
            elif run.duration > 0:
                duration_str = f"{run.duration:.1f}s"
            else:
                duration_str = "-"
            activity_str = run.activity if run.status == RunStatus.RUNNING else ""

            table.add_row(
                run.run_id,
                run.agent_id,
                str(run.run_number),
                f"[{status_style}]{run.status.value}[/]",
                duration_str,
                f"[dim]{activity_str}[/]",
            )

        progress_text = (
            f"Progress: {self.state.completed_runs}/{self.state.total_runs} "
            f"({self.state.successful_runs} successful)"
        )

        return Panel(
            table,
            title=f"[bold]{self.state.name}[/]",
            subtitle=progress_text,
        )

    def _refresh(self) -> None:
        """Refresh the display."""
        if self._live:
            self._live.update(self._make_panel())

    def stop(self) -> None:
        """Stop the progress display."""
        if self._live:
            self._live.stop()
            self._live = None

    def print_summary(self) -> None:
        """Print a summary of the experiment."""
        if self.state is None:
            return

        self.console.print()
        self.console.rule("[bold]Experiment Summary")

        successful = [r for r in self.state.runs.values() if r.status == RunStatus.COMPLETED]
        failed = [
            r for r in self.state.runs.values() if r.status in (RunStatus.FAILED, RunStatus.TIMEOUT)
        ]

        self.console.print(f"Total runs: {self.state.total_runs}")
        self.console.print(f"[green]Successful: {len(successful)}[/]")
        self.console.print(f"[red]Failed: {len(failed)}[/]")

        if successful:
            avg_duration = sum(r.duration for r in successful) / len(successful)
            self.console.print(f"Average duration: {avg_duration:.1f}s")

        if failed:
            self.console.print()
            self.console.print("[red]Failed runs:[/]")
            for run in failed:
                error_msg = f": {run.error}" if run.error else ""
                self.console.print(f"  - {run.run_id} ({run.status.value}){error_msg}")
