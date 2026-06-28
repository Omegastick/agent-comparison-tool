"""Container management for running model-comparison runs via Pi."""

import json
import logging
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docker.errors import ContainerError, ImageNotFound
from docker.models.containers import Container

import docker

from .config import ProviderConfig

logger = logging.getLogger(__name__)

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_TOOL_PREFIXES = ("→ ", "← ", "✱ ", "$ ", "⚙ ", "• ")
_ENV_REF_RE = re.compile(r"\$\{?(\w+)\}?")


def parse_activity_line(raw_line: str) -> str | None:
    """Extract a tool-call activity description from a log line.

    Strips ANSI escape codes and checks for known tool prefixes. Returns the
    cleaned line if it matches, None otherwise.
    """
    cleaned = _ANSI_ESCAPE_RE.sub("", raw_line).strip()
    if any(cleaned.startswith(prefix) for prefix in _TOOL_PREFIXES):
        return cleaned
    return None


def build_models_json(providers: dict[str, ProviderConfig]) -> dict[str, Any]:
    """Build Pi's ``models.json`` payload from the comparison providers block.

    The target models are Pi built-ins, so each provider only contributes its
    ``apiKey`` (an ``$ENV`` reference resolved inside the container) plus any
    ``baseUrl`` / ``api`` override it explicitly sets. Anthropic, for instance,
    pins its baseUrl to the host root (``https://api.anthropic.com``, no
    ``/v1``) because the SDK appends ``/v1/messages`` itself.
    """
    out: dict[str, dict[str, str]] = {}
    for name, provider in providers.items():
        entry: dict[str, str] = {"apiKey": provider.api_key}
        if provider.base_url is not None:
            entry["baseUrl"] = provider.base_url
        if provider.api is not None:
            entry["api"] = provider.api
        out[name] = entry
    return {"providers": out}


def _referenced_env_vars(providers: dict[str, ProviderConfig]) -> set[str]:
    """Collect host env var names referenced (as ``$VAR``) by provider configs."""
    names: set[str] = set()
    for provider in providers.values():
        for value in (provider.api_key, provider.base_url):
            if value:
                names.update(_ENV_REF_RE.findall(value))
    return names


@dataclass
class ContainerConfig:
    """Configuration for a single container run."""

    run_id: str
    repo_url: str
    repo_commit: str | None
    prompt_file: str | None
    prompt_text: str | None
    pi_model: str
    providers: dict[str, ProviderConfig]
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
    """Manages Docker containers for comparison runs."""

    IMAGE_NAME = "act-agent"
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
        """Run Pi headless in a container with the given configuration."""
        self.ensure_image()

        env = {
            "RUN_ID": config.run_id,
            "REPO_URL": config.repo_url,
            "HOME": "/home/agent",
            "PI_MODEL": config.pi_model,
        }
        if config.repo_commit:
            env["REPO_COMMIT"] = config.repo_commit
        if config.prompt_file:
            env["PROMPT_FILE"] = config.prompt_file
        if config.prompt_text:
            env["PROMPT_TEXT"] = config.prompt_text
        if config.extra_args:
            env["PI_EXTRA_ARGS"] = " ".join(config.extra_args)

        # Pi reads `$VAR` references in models.json from the process env, so the
        # referenced host keys have to be forwarded into the container.
        for var in _referenced_env_vars(config.providers):
            value = os.environ.get(var)
            if value is not None:
                env[var] = value

        home_dir = tempfile.mkdtemp(prefix="act-home-")
        models_dir = tempfile.mkdtemp(prefix="act-models-")
        models_path = Path(models_dir) / "models.json"
        models_path.write_text(json.dumps(build_models_json(config.providers), indent=2))

        volumes = {
            str(config.workspace_path): {"bind": "/workspace", "mode": "rw"},
            home_dir: {"bind": "/home/agent", "mode": "rw"},
            str(models_path): {
                "bind": "/home/agent/.pi/agent/models.json",
                "mode": "ro",
            },
        }

        try:
            container = self.client.containers.run(
                self.IMAGE_NAME,
                environment=env,
                volumes=volumes,
                detach=True,
                mem_limit="4g",
                user=f"{os.getuid()}:{os.getgid()}",
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
            shutil.rmtree(home_dir, ignore_errors=True)
            shutil.rmtree(models_dir, ignore_errors=True)

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
