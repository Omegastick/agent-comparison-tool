"""Configuration models for experiment files."""

import tomllib
from pathlib import Path

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
    # Delay between launching parallel runs. Staggering (or `parallel = false`)
    # avoids two same-provider runs sharing a rate-limit window and converting
    # provider throttling into a spurious FAILED — preferred for article runs.
    stagger_seconds: float = Field(default=0.0, ge=0.0)


class ProviderConfig(BaseModel):
    """Per-provider override for Pi's generated models.json.

    The target models are Pi built-ins, so a provider only needs to carry its
    API key. ``api_key`` is an env-var reference (e.g. ``$ANTHROPIC_API_KEY``)
    resolved from host env at run time, never the literal secret. ``base_url``
    and ``api`` override the built-in defaults only when a provider requires it
    (e.g. z.ai's coding-plan endpoint).
    """

    api_key: str
    base_url: str | None = None
    api: str | None = None


class AgentConfig(BaseModel):
    """A single model under comparison.

    ``model`` is a Pi model ref of the form ``<provider>/<id>`` (e.g.
    ``anthropic/claude-sonnet-4-6``); the provider segment must have a matching
    entry in the experiment's ``[providers]`` block.
    """

    id: str
    model: str
    extra_args: list[str] = Field(default_factory=list)

    @property
    def provider(self) -> str:
        """The provider segment of the Pi model ref."""
        return self.model.split("/", 1)[0]


class ComparisonConfig(BaseModel):
    """Complete model-comparison configuration."""

    experiment: ExperimentConfig
    target: TargetConfig
    prompt: PromptConfig
    settings: SettingsConfig = Field(default_factory=SettingsConfig)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    agents: list[AgentConfig]

    @model_validator(mode="after")
    def check_agents(self) -> "ComparisonConfig":
        if not self.agents:
            raise ValueError("At least one agent must be configured")
        ids = [a.id for a in self.agents]
        if len(ids) != len(set(ids)):
            raise ValueError("Agent IDs must be unique")
        for agent in self.agents:
            if "/" not in agent.model:
                raise ValueError(
                    f"Agent '{agent.id}' model '{agent.model}' must be a "
                    f"'<provider>/<id>' Pi model ref"
                )
            if agent.provider not in self.providers:
                raise ValueError(
                    f"Agent '{agent.id}' references unknown provider "
                    f"'{agent.provider}'; add a [providers.{agent.provider}] entry"
                )
        return self


def load_config(path: Path) -> ComparisonConfig:
    """Load and validate a comparison configuration from a TOML file."""
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return ComparisonConfig.model_validate(data)
