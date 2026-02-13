"""Experiment runner for orchestrating benchmark runs."""

import shutil
import tempfile
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import tomli_w

from .config import BenchmarkConfig
from .container import ContainerConfig, ContainerManager, ContainerResult, WorkspaceManager
from .display import ProgressDisplay, RunStatus
from .metrics import collect_run_metrics, save_metrics


class ExperimentRunner:
    """Orchestrates parallel benchmark runs."""

    def __init__(
        self,
        config: BenchmarkConfig,
        output_base: Path,
        display: ProgressDisplay,
    ) -> None:
        self.config = config
        self.output_base = output_base
        self.display = display
        self.container_manager = ContainerManager()

    def run(self) -> Path:
        """Run the experiment and return the results path."""
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
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
            self._collect_results(results, results_path, workspace_manager)
            self.display.stop()
            self.display.print_summary()
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
                    model=agent.model,
                    extra_args=agent.extra_args,
                    timeout_seconds=timeout,
                    workspace_path=workspace,
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

        futures: dict[Future[ContainerResult], tuple[str, str, ContainerConfig]] = {}
        for run_id, agent_id, _, config in run_configs:
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

        def on_activity(activity: str) -> None:
            self.display.update_activity(run_id, activity)

        try:
            result = self.container_manager.run(config, activity_callback=on_activity)
            duration = time.time() - start_time

            status = RunStatus.COMPLETED if result.exit_code == 0 else RunStatus.FAILED
            self.display.update_run(run_id, status, duration, result.error)

            return result

        except Exception as e:
            duration = time.time() - start_time
            self.display.update_run(run_id, RunStatus.FAILED, duration, str(e))
            raise

    def _collect_results(
        self,
        results: list[tuple[str, str, ContainerResult]],
        results_path: Path,
        workspace_manager: WorkspaceManager,
    ) -> None:
        """Collect and save results from all runs."""
        for run_id, agent_id, result in results:
            run_path = results_path / run_id
            run_path.mkdir(parents=True, exist_ok=True)

            if result.workspace_path and result.workspace_path.exists():
                workspace_manager.copy_results(run_id, run_path)

                # Nested .git dirs are treated as submodules when results are committed
                repo_git = run_path / "repo" / ".git"
                if repo_git.exists():
                    shutil.rmtree(repo_git, ignore_errors=True)

            metrics = collect_run_metrics(
                run_id=run_id,
                agent_id=agent_id,
                workspace_path=result.workspace_path,
                logs=result.logs,
                exit_code=result.exit_code,
                error=result.error,
            )
            save_metrics(metrics, run_path / "metrics.json")

    def _save_config(self, results_path: Path) -> None:
        """Save the experiment config to results."""
        config_dict = self.config.model_dump(exclude_none=True)
        with open(results_path / "config.toml", "wb") as f:
            tomli_w.dump(config_dict, f)

    def cleanup(self) -> None:
        """Kill any running containers."""
        self.container_manager.cleanup()
