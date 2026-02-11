"""Configuration models for experiment files."""

from pathlib import Path
from typing import Literal

import tomli
from pydantic import BaseModel, Field, model_validator


class ExperimentConfig(BaseModel):
    """Top-level experiment configuration."""

    name: str
    description: str = ""


class TargetConfig(BaseModel):
    """Target repository configuration."""

    repo: str
    commit: str | None = None

    @property
    def is_local(self) -> bool:
        """Check if the repo is a local path."""
        return not self.repo.startswith(("http://", "https://", "git@"))


class PromptConfig(BaseModel):
    """Prompt configuration - either file path or inline text."""

    file: str | None = None
    text: str | None = None

    @model_validator(mode="after")
    def check_file_or_text(self) -> "PromptConfig":
        if self.file is None and self.text is None:
            raise ValueError("Either 'file' or 'text' must be provided")
        if self.file is not None and self.text is not None:
            raise ValueError("Only one of 'file' or 'text' should be provided")
        return self


class SettingsConfig(BaseModel):
    """Experiment settings."""

    runs_per_agent: int = Field(default=3, ge=1, le=10)
    parallel: bool = True
    timeout_minutes: int = Field(default=30, ge=1, le=180)


class AgentConfig(BaseModel):
    """Agent configuration."""

    id: str
    type: Literal["opencode"]
    agent: str | None = None
    model: str | None = None
    extra_args: list[str] = Field(default_factory=list)


class BenchmarkConfig(BaseModel):
    """Complete benchmark configuration."""

    experiment: ExperimentConfig
    target: TargetConfig
    prompt: PromptConfig
    settings: SettingsConfig = Field(default_factory=SettingsConfig)
    agents: list[AgentConfig]

    @model_validator(mode="after")
    def check_agents(self) -> "BenchmarkConfig":
        if not self.agents:
            raise ValueError("At least one agent must be configured")
        ids = [a.id for a in self.agents]
        if len(ids) != len(set(ids)):
            raise ValueError("Agent IDs must be unique")
        return self


def load_config(path: Path) -> BenchmarkConfig:
    """Load and validate a benchmark configuration from a TOML file."""
    with open(path, "rb") as f:
        data = tomli.load(f)
    return BenchmarkConfig.model_validate(data)
