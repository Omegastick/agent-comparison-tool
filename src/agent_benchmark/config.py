"""Configuration models for experiment files."""

from pathlib import Path

import tomllib
from pydantic import BaseModel, Field, model_validator


class ExperimentConfig(BaseModel):
    """Top-level experiment configuration."""

    name: str
    description: str = ""


class TargetConfig(BaseModel):
    """Target repository configuration."""

    repo: str
    commit: str | None = None


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
    timeout_minutes: int = Field(default=10, ge=1, le=180)


class AgentConfig(BaseModel):
    """Agent configuration."""

    id: str
    model: str | None = None
    extra_args: list[str] = Field(default_factory=list)


class AnalysisConfig(BaseModel):
    """AI analysis configuration."""

    model: str = "anthropic/claude-opus-4-5"
    prompt: str = ""


class BenchmarkConfig(BaseModel):
    """Complete benchmark configuration."""

    experiment: ExperimentConfig
    target: TargetConfig
    prompt: PromptConfig
    settings: SettingsConfig = Field(default_factory=SettingsConfig)
    agents: list[AgentConfig]
    analysis: AnalysisConfig | None = None

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
        data = tomllib.load(f)
    return BenchmarkConfig.model_validate(data)
