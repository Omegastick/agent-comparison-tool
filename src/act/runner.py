"""Experiment runner for orchestrating comparison runs."""

import json
import os
import shutil
import tempfile
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import tomli_w
from pydantic import BaseModel

from .config import ComparisonConfig
from .container import (
    ContainerConfig,
    ContainerManager,
    ContainerResult,
    WorkspaceManager,
    _referenced_env_vars,
    referenced_api_key_vars,
)
from .cost import Pricing, RunCost, aggregate_usage, summarize_run, write_summary
from .display import ProgressDisplay, RunStatus

_REDACTED = "***REDACTED***"

_RATE_LIMIT_MARKERS = (
    "rate limit",
    "rate_limit",
    "ratelimit",
    "too many requests",
    "429",
    "overloaded",
    "quota",
)


def _looks_rate_limited(text: str | None) -> bool:
    """Best-effort detection of provider throttling from an error/log string."""
    if not text:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in _RATE_LIMIT_MARKERS)


class RunOutcome(BaseModel):
    """Persisted per-run outcome record, written to ``runs.json``."""

    run_id: str
    agent_id: str
    status: str
    exit_code: int
    error: str | None
    duration_seconds: float
    model: str
    model_source: str
    run_date: str
    rate_limited: bool


@dataclass
class _RunRecord:
    """In-flight outcome captured by a worker, enriched into a RunOutcome later."""

    status: RunStatus
    exit_code: int
    error: str | None
    duration: float
    model_ref: str
    rate_limited: bool


class ExperimentRunner:
    """Orchestrates parallel comparison runs."""

    ARTIFACTS = ("diff.patch", "trace.jsonl", "output.txt", "run-meta.json")

    def __init__(
        self,
        config: ComparisonConfig,
        output_base: Path,
        display: ProgressDisplay,
        pricing: Pricing | None = None,
    ) -> None:
        self.config = config
        self.output_base = output_base
        self.display = display
        self.pricing = pricing or Pricing()
        self.container_manager = ContainerManager()
        self.cost_rows: list[RunCost] = []
        self.run_date = ""
        self._records: dict[str, _RunRecord] = {}
        self._records_lock = threading.Lock()

    def run(self) -> Path:
        """Run the experiment and return the results path."""
        # Fail fast on missing keys before launching any (expensive) container.
        self._validate_provider_keys()

        now = datetime.now()
        self.run_date = now.strftime("%Y-%m-%d")
        timestamp = now.strftime("%Y-%m-%d-%H%M%S")
        experiment_id = f"{self.config.experiment.name}-{timestamp}"
        results_path = self.output_base / experiment_id
        results_path.mkdir(parents=True, exist_ok=True)

        self._save_config(results_path)

        temp_dir = Path(tempfile.mkdtemp(prefix="act-"))
        workspace_manager = WorkspaceManager(temp_dir)
        results: list[tuple[str, str, ContainerResult]] = []

        run_configs = self._create_run_configs(workspace_manager)
        total_runs = len(run_configs)

        self.display.start(self.config.experiment.name, total_runs)

        for run_id, agent_id, run_num, _ in run_configs:
            self.display.add_run(run_id, agent_id, run_num)

        try:
            if self.config.settings.parallel:
                self._run_parallel(run_configs, results)
            else:
                self._run_sequential(run_configs, results)
        finally:
            self._collect_results(results, results_path)
            # Mandatory: scrub forwarded provider key values out of every
            # collected text artifact before anything is summarised or published.
            self._scrub_secrets(results_path)
            self._summarize_costs(results, results_path)
            self._write_outcomes(results, results_path)
            self.display.stop()
            self.display.print_summary()
            self.display.print_cost_summary(self.cost_rows)
            self.container_manager.cleanup()
            workspace_manager.cleanup()
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

        return results_path

    def _create_run_configs(
        self, workspace_manager: WorkspaceManager
    ) -> list[tuple[str, str, int, ContainerConfig]]:
        """Create container configurations for all runs."""
        configs = []
        timeout = self.config.settings.timeout_minutes * 60

        for agent in self.config.agents:
            for run_num in range(1, self.config.settings.runs_per_agent + 1):
                run_id = f"{agent.id}-{run_num}"
                workspace = workspace_manager.create(run_id)

                container_config = ContainerConfig(
                    run_id=run_id,
                    repo_url=self.config.target.repo,
                    repo_commit=self.config.target.commit,
                    prompt_file=self.config.prompt.file,
                    prompt_text=self.config.prompt.text,
                    pi_model=agent.model,
                    providers=self.config.providers,
                    extra_args=agent.extra_args,
                    timeout_seconds=timeout,
                    workspace_path=workspace,
                    image=self.config.settings.image,
                )
                configs.append((run_id, agent.id, run_num, container_config))

        return configs

    def _run_parallel(
        self,
        run_configs: list[tuple[str, str, int, ContainerConfig]],
        results: list[tuple[str, str, ContainerResult]],
    ) -> None:
        """Run containers in parallel."""
        max_workers = min(len(run_configs), 4)
        executor = ThreadPoolExecutor(max_workers=max_workers)

        stagger = self.config.settings.stagger_seconds
        futures: dict[Future[ContainerResult], tuple[str, str, ContainerConfig]] = {}
        for index, (run_id, agent_id, _, config) in enumerate(run_configs):
            # Stagger launches so same-provider runs don't slam a shared rate limit
            # in the same instant; the first launch is never delayed.
            if stagger > 0 and index > 0:
                time.sleep(stagger)
            future = executor.submit(self._run_single, run_id, config)
            futures[future] = (run_id, agent_id, config)

        try:
            for future in as_completed(futures):
                run_id, agent_id, config = futures[future]
                try:
                    result = future.result()
                    results.append((run_id, agent_id, result))
                except Exception as e:
                    results.append(
                        (
                            run_id,
                            agent_id,
                            ContainerResult(
                                run_id=run_id,
                                exit_code=1,
                                logs="",
                                workspace_path=config.workspace_path,
                                error=str(e),
                            ),
                        )
                    )
        except KeyboardInterrupt:
            self._drain_completed_futures(futures, results)
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        finally:
            executor.shutdown(wait=False)

    def _drain_completed_futures(
        self,
        futures: dict[Future[ContainerResult], tuple[str, str, ContainerConfig]],
        results: list[tuple[str, str, ContainerResult]],
    ) -> None:
        """Collect results from already-completed futures not yet in results."""
        collected_ids = {r[0] for r in results}
        for future, (run_id, agent_id, config) in futures.items():
            if run_id in collected_ids or not future.done():
                continue
            try:
                result = future.result(timeout=0)
                results.append((run_id, agent_id, result))
            except Exception as e:
                results.append(
                    (
                        run_id,
                        agent_id,
                        ContainerResult(
                            run_id=run_id,
                            exit_code=1,
                            logs="",
                            workspace_path=config.workspace_path,
                            error=str(e),
                        ),
                    )
                )

    def _run_sequential(
        self,
        run_configs: list[tuple[str, str, int, ContainerConfig]],
        results: list[tuple[str, str, ContainerResult]],
    ) -> None:
        """Run containers sequentially."""
        for run_id, agent_id, _, config in run_configs:
            try:
                result = self._run_single(run_id, config)
                results.append((run_id, agent_id, result))
            except Exception as e:
                results.append(
                    (
                        run_id,
                        agent_id,
                        ContainerResult(
                            run_id=run_id,
                            exit_code=1,
                            logs="",
                            workspace_path=config.workspace_path,
                            error=str(e),
                        ),
                    )
                )

    def _run_single(self, run_id: str, config: ContainerConfig) -> ContainerResult:
        """Run a single container and update display."""
        self.display.update_run(run_id, RunStatus.RUNNING)
        start_time = time.time()

        try:
            result = self.container_manager.run(config)
            duration = time.time() - start_time

            if result.timed_out:
                status = RunStatus.TIMEOUT
            elif result.exit_code == 0:
                status = RunStatus.COMPLETED
            else:
                status = RunStatus.FAILED
            self.display.update_run(run_id, status, duration, result.error)
            rate_limited = _looks_rate_limited(result.error) or _looks_rate_limited(result.logs)
            self._record(run_id, config, status, result.exit_code, result.error, duration, rate_limited)

            return result

        except Exception as e:
            duration = time.time() - start_time
            self.display.update_run(run_id, RunStatus.FAILED, duration, str(e))
            self._record(run_id, config, RunStatus.FAILED, 1, str(e), duration, _looks_rate_limited(str(e)))
            raise

    def _record(
        self,
        run_id: str,
        config: ContainerConfig,
        status: RunStatus,
        exit_code: int,
        error: str | None,
        duration: float,
        rate_limited: bool,
    ) -> None:
        """Capture a worker's outcome; threadsafe for the parallel executor."""
        with self._records_lock:
            self._records[run_id] = _RunRecord(
                status=status,
                exit_code=exit_code,
                error=error,
                duration=duration,
                model_ref=config.pi_model,
                rate_limited=rate_limited,
            )

    def _collect_results(
        self,
        results: list[tuple[str, str, ContainerResult]],
        results_path: Path,
    ) -> None:
        """Collect the lean per-run artifacts (diff.patch, trace.jsonl, output.txt).

        The container writes only these files to its workspace; the target repo
        is cloned elsewhere so results stay small enough to commit and eyeball.
        """
        for run_id, _agent_id, result in results:
            run_path = results_path / run_id
            run_path.mkdir(parents=True, exist_ok=True)

            workspace = result.workspace_path
            if not (workspace and workspace.exists()):
                continue

            for artifact in self.ARTIFACTS:
                src = workspace / artifact
                if src.exists():
                    shutil.copy2(src, run_path / artifact)

    def _validate_provider_keys(self) -> None:
        """Raise if any env var referenced by the providers block is unset.

        Without this, a typo'd or missing key is silently dropped and surfaces as
        an opaque auth failure deep in a trace after N containers have launched.
        """
        referenced = _referenced_env_vars(self.config.providers)
        missing = sorted(var for var in referenced if not os.environ.get(var))
        if missing:
            raise ValueError(
                "Missing required provider environment variable(s): "
                f"{', '.join(missing)}. Set them before running the experiment."
            )

    def _scrub_secrets(self, results_path: Path) -> None:
        """Redact every forwarded provider key value from each run's text artifacts.

        Keys are forwarded into containers as plaintext env, so a model that runs
        ``env``/``echo $KEY`` could capture one verbatim into a publishable
        artifact. Every key in the providers block is covered (a container may be
        forwarded more than its own), and replacement is substring-based so a key
        is caught wherever it appears.
        """
        secrets = sorted(
            {
                value
                for var in referenced_api_key_vars(self.config.providers)
                if (value := os.environ.get(var))
            },
            key=len,
            reverse=True,
        )
        if not secrets:
            return

        for run_dir in results_path.iterdir():
            if not run_dir.is_dir():
                continue
            for artifact in self.ARTIFACTS:
                path = run_dir / artifact
                if not path.exists():
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                scrubbed = text
                for secret in secrets:
                    scrubbed = scrubbed.replace(secret, _REDACTED)
                if scrubbed != text:
                    path.write_text(scrubbed, encoding="utf-8")

    def _write_outcomes(
        self,
        results: list[tuple[str, str, ContainerResult]],
        results_path: Path,
    ) -> None:
        """Persist per-run outcomes (status, exit, duration, resolved model) to runs.json."""
        outcomes: list[RunOutcome] = []
        for run_id, agent_id, result in results:
            record = self._records.get(run_id)

            trace_path = results_path / run_id / "trace.jsonl"
            served_model = aggregate_usage(trace_path).model if trace_path.exists() else ""

            if record is not None:
                status = record.status
                exit_code = record.exit_code
                error = record.error
                duration = record.duration
                model_ref = record.model_ref
                rate_limited = record.rate_limited
            else:
                # Fallback for a run whose worker never recorded (e.g. surfaced
                # only as an executor failure); derive what we can from the result.
                status = (
                    RunStatus.TIMEOUT
                    if result.timed_out
                    else (RunStatus.COMPLETED if result.exit_code == 0 else RunStatus.FAILED)
                )
                exit_code = result.exit_code
                error = result.error
                duration = 0.0
                model_ref = ""
                rate_limited = _looks_rate_limited(result.error) or _looks_rate_limited(result.logs)

            # Prefer the model the provider actually served (from the trace) so a
            # floating alias is resolved to a concrete id; else the configured ref
            # plus the run date documents which alias resolved when.
            model = served_model or model_ref
            model_source = "trace" if served_model else "config"

            outcomes.append(
                RunOutcome(
                    run_id=run_id,
                    agent_id=agent_id,
                    status=status.value,
                    exit_code=exit_code,
                    error=error,
                    duration_seconds=round(duration, 3),
                    model=model,
                    model_source=model_source,
                    run_date=self.run_date,
                    rate_limited=rate_limited,
                )
            )

        outcomes.sort(key=lambda o: o.run_id)
        with open(results_path / "runs.json", "w", encoding="utf-8") as f:
            json.dump([o.model_dump() for o in outcomes], f, indent=2)

    def _summarize_costs(
        self,
        results: list[tuple[str, str, ContainerResult]],
        results_path: Path,
    ) -> None:
        """Aggregate token usage and cost from each run's trace and write a summary."""
        self.cost_rows = [
            summarize_run(
                run_id,
                agent_id,
                results_path / run_id / "trace.jsonl",
                self.pricing,
            )
            for run_id, agent_id, _ in results
        ]
        write_summary(self.cost_rows, results_path)

    def _save_config(self, results_path: Path) -> None:
        """Save the experiment config to results."""
        config_dict = self.config.model_dump(exclude_none=True)
        with open(results_path / "config.toml", "wb") as f:
            tomli_w.dump(config_dict, f)

    def cleanup(self) -> None:
        """Kill any running containers."""
        self.container_manager.cleanup()
