"""Container management for running agent benchmarks."""

import logging
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from docker.errors import ContainerError, ImageNotFound
from docker.models.containers import Container

import docker

logger = logging.getLogger(__name__)

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_TOOL_PREFIXES = ("→ ", "← ", "✱ ", "$ ", "⚙ ", "• ")


def parse_activity_line(raw_line: str) -> str | None:
    """Extract a tool-call activity description from a log line.

    Strips ANSI escape codes and checks for known OpenCode tool prefixes.
    Returns the cleaned line if it matches, None otherwise.
    """
    cleaned = _ANSI_ESCAPE_RE.sub("", raw_line).strip()
    if any(cleaned.startswith(prefix) for prefix in _TOOL_PREFIXES):
        return cleaned
    return None


@dataclass
class ContainerConfig:
    """Configuration for a single container run."""

    run_id: str
    repo_url: str
    repo_commit: str | None
    prompt_file: str | None
    prompt_text: str | None
    model: str | None
    extra_args: list[str]
    timeout_seconds: int
    workspace_path: Path


@dataclass
class ContainerResult:
    """Result from a container run."""

    run_id: str
    exit_code: int
    logs: str
    workspace_path: Path
    error: str | None = None


@dataclass
class AnalysisContainerConfig:
    """Configuration for running analysis in a container."""

    results_path: Path
    model: str
    prompt: str
    system_prompt: str
    timeout_seconds: int = 600


@dataclass
class AnalysisResult:
    """Result from an analysis container run."""

    exit_code: int
    logs: str
    output: str
    error: str | None = None


class ContainerManager:
    """Manages Docker containers for benchmark runs."""

    IMAGE_NAME = "agent-benchmark-opencode"
    DOCKER_DIR = Path(__file__).parent.parent.parent / "docker"

    def __init__(self) -> None:
        self.client = docker.from_env()
        self._image_built = False
        self._containers: dict[str, Container] = {}

    def ensure_image(self) -> None:
        """Build the Docker image if not already built."""
        if self._image_built:
            return

        try:
            self.client.images.get(self.IMAGE_NAME)
            self._image_built = True
            return
        except ImageNotFound:
            pass

        self.client.images.build(
            path=str(self.DOCKER_DIR),
            tag=self.IMAGE_NAME,
            rm=True,
        )
        self._image_built = True

    def run(
        self,
        config: ContainerConfig,
        activity_callback: Callable[[str], None] | None = None,
    ) -> ContainerResult:
        """Run a container with the given configuration."""
        self.ensure_image()

        env = {
            "RUN_ID": config.run_id,
            "REPO_URL": config.repo_url,
        }
        if config.repo_commit:
            env["REPO_COMMIT"] = config.repo_commit
        if config.prompt_file:
            env["PROMPT_FILE"] = config.prompt_file
        if config.prompt_text:
            env["PROMPT_TEXT"] = config.prompt_text
        if config.model:
            env["OPENCODE_MODEL"] = config.model
        if config.extra_args:
            env["OPENCODE_EXTRA_ARGS"] = " ".join(config.extra_args)

        auth_path = Path.home() / ".local/share/opencode/auth.json"
        volumes = {
            str(config.workspace_path): {"bind": "/workspace", "mode": "rw"},
        }
        if auth_path.exists():
            volumes[str(auth_path)] = {
                "bind": "/root/.local/share/opencode/auth.json",
                "mode": "ro",
            }

        try:
            container = self.client.containers.run(
                self.IMAGE_NAME,
                environment=env,
                volumes=volumes,
                detach=True,
                mem_limit="4g",
            )
            self._containers[config.run_id] = container

            if activity_callback is not None:
                all_logs: list[str] = []
                for chunk in container.logs(stream=True, follow=True):
                    text = chunk.decode("utf-8")
                    all_logs.append(text)
                    activity = parse_activity_line(text)
                    if activity:
                        activity_callback(activity)

                result = container.wait(timeout=config.timeout_seconds)
                exit_code = result.get("StatusCode", 1)
                logs = "".join(all_logs)
            else:
                result = container.wait(timeout=config.timeout_seconds)
                logs = container.logs().decode("utf-8")
                exit_code = result.get("StatusCode", 1)

            return ContainerResult(
                run_id=config.run_id,
                exit_code=exit_code,
                logs=logs,
                workspace_path=config.workspace_path,
            )

        except ContainerError as e:
            stderr = e.stderr
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8")
            return ContainerResult(
                run_id=config.run_id,
                exit_code=1,
                logs=stderr or "",
                workspace_path=config.workspace_path,
                error=str(e),
            )
        except Exception as e:
            return ContainerResult(
                run_id=config.run_id,
                exit_code=1,
                logs="",
                workspace_path=config.workspace_path,
                error=str(e),
            )
        finally:
            if config.run_id in self._containers:
                try:
                    self._containers[config.run_id].remove(force=True)
                except Exception as e:
                    logger.warning("Failed to remove container %s: %s", config.run_id, e)
                del self._containers[config.run_id]

    def run_analysis(
        self, config: AnalysisContainerConfig, stream_output: bool = True
    ) -> AnalysisResult:
        """Run an analysis container with the given configuration.

        Args:
            config: Configuration for the analysis run.
            stream_output: If True, stream container output to stdout in real-time.
        """
        import sys
        import tempfile

        self.ensure_image()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            system_prompt_file = temp_path / "system-prompt.txt"
            system_prompt_file.write_text(config.system_prompt)

            env = {
                "ANALYSIS_PROMPT": config.prompt,
            }
            if config.model:
                env["OPENCODE_MODEL"] = config.model

            auth_path = Path.home() / ".local/share/opencode/auth.json"
            volumes = {
                str(config.results_path): {"bind": "/workspace/results", "mode": "rw"},
                str(system_prompt_file): {
                    "bind": "/workspace/system-prompt.txt",
                    "mode": "ro",
                },
            }
            if auth_path.exists():
                volumes[str(auth_path)] = {
                    "bind": "/root/.local/share/opencode/auth.json",
                    "mode": "ro",
                }

            container_id = f"analysis-{id(config)}"
            all_logs: list[str] = []

            try:
                container = self.client.containers.run(
                    self.IMAGE_NAME,
                    entrypoint="/analyze-entrypoint.sh",
                    environment=env,
                    volumes=volumes,
                    detach=True,
                    mem_limit="4g",
                )
                self._containers[container_id] = container

                if stream_output:
                    for chunk in container.logs(stream=True, follow=True):
                        text = chunk.decode("utf-8")
                        all_logs.append(text)
                        sys.stdout.write(text)
                        sys.stdout.flush()

                result = container.wait(timeout=config.timeout_seconds)
                exit_code = result.get("StatusCode", 1)

                logs = "".join(all_logs) if all_logs else container.logs().decode("utf-8")

                return AnalysisResult(
                    exit_code=exit_code,
                    logs=logs,
                    output="",
                )

            except ContainerError as e:
                stderr = e.stderr
                if isinstance(stderr, bytes):
                    stderr = stderr.decode("utf-8")
                return AnalysisResult(
                    exit_code=1,
                    logs=stderr or "",
                    output="",
                    error=str(e),
                )
            except Exception as e:
                return AnalysisResult(
                    exit_code=1,
                    logs="",
                    output="",
                    error=str(e),
                )
            finally:
                if container_id in self._containers:
                    try:
                        self._containers[container_id].remove(force=True)
                    except Exception as e:
                        logger.warning("Failed to remove analysis container: %s", e)
                    del self._containers[container_id]

    def cleanup(self) -> None:
        """Clean up any running containers."""
        for run_id, container in list(self._containers.items()):
            try:
                container.remove(force=True)
            except Exception as e:
                logger.warning("Failed to remove container %s during cleanup: %s", run_id, e)
            self._containers.pop(run_id, None)


@dataclass
class WorkspaceManager:
    """Manages workspace directories for experiment runs."""

    base_path: Path
    _workspaces: dict[str, Path] = field(default_factory=dict)

    def create(self, run_id: str) -> Path:
        """Create a workspace directory for a run."""
        workspace = self.base_path / run_id
        workspace.mkdir(parents=True, exist_ok=True)
        self._workspaces[run_id] = workspace
        return workspace

    def get(self, run_id: str) -> Path | None:
        """Get the workspace path for a run."""
        return self._workspaces.get(run_id)

    def copy_results(self, run_id: str, dest: Path) -> None:
        """Copy workspace contents to a destination."""
        workspace = self._workspaces.get(run_id)
        if workspace and workspace.exists():
            shutil.copytree(workspace, dest, dirs_exist_ok=True)

    def cleanup(self) -> None:
        """Clean up all workspace directories."""
        for workspace in self._workspaces.values():
            if workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)
        self._workspaces.clear()
