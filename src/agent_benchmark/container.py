"""Container management for running agent benchmarks."""

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import docker

logger = logging.getLogger(__name__)
from docker.errors import ContainerError, ImageNotFound
from docker.models.containers import Container


@dataclass
class ContainerConfig:
    """Configuration for a single container run."""

    run_id: str
    repo_url: str
    repo_commit: str | None
    prompt_file: str | None
    prompt_text: str | None
    agent: str | None
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

    def run(self, config: ContainerConfig) -> ContainerResult:
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
        if config.agent:
            env["OPENCODE_AGENT"] = config.agent
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

    def cleanup(self) -> None:
        """Clean up any running containers."""
        for run_id, container in list(self._containers.items()):
            try:
                container.remove(force=True)
            except Exception as e:
                logger.warning("Failed to remove container %s during cleanup: %s", run_id, e)
            del self._containers[run_id]


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
