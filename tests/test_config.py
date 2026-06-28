"""Tests for ComparisonConfig validation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from act.config import load_config

VALID_CONFIG = """
[experiment]
name = "vllm-comparison"
description = "Compare models on a vLLM task"

[target]
repo = "https://github.com/vllm-project/vllm"
commit = "9036c89ee410b30913ca8b7d362a7d0805583b51"

[prompt]
text = "Implement the requested change."

[settings]
runs_per_agent = 2
parallel = true
timeout_minutes = 30

[providers.anthropic]
api_key = "$ANTHROPIC_API_KEY"

[providers.zai]
base_url = "https://api.z.ai/api/coding/paas/v4"
api_key = "$ZAI_API_KEY"

[[agents]]
id = "sonnet"
model = "anthropic/claude-sonnet-4-6"

[[agents]]
id = "glm"
model = "zai/glm-5.2"
"""


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(content)
    return path


def test_valid_config_loads(tmp_path: Path):
    config = load_config(_write(tmp_path, VALID_CONFIG))

    assert config.experiment.name == "vllm-comparison"
    assert config.target.commit == "9036c89ee410b30913ca8b7d362a7d0805583b51"
    assert {a.id for a in config.agents} == {"sonnet", "glm"}
    assert config.agents[0].provider == "anthropic"
    assert config.providers["anthropic"].api_key == "$ANTHROPIC_API_KEY"
    assert config.providers["zai"].base_url == "https://api.z.ai/api/coding/paas/v4"


def test_stagger_seconds_defaults_to_zero(tmp_path: Path):
    # Backwards-compatible: omitting stagger_seconds keeps the prior behaviour.
    config = load_config(_write(tmp_path, VALID_CONFIG))
    assert config.settings.stagger_seconds == 0.0


def test_unknown_provider_ref_rejected(tmp_path: Path):
    content = """
[experiment]
name = "x"

[target]
repo = "https://github.com/vllm-project/vllm"

[prompt]
text = "go"

[providers.anthropic]
api_key = "$ANTHROPIC_API_KEY"

[[agents]]
id = "gpt"
model = "openai/gpt-5.4"
"""
    with pytest.raises(ValidationError, match="unknown provider"):
        load_config(_write(tmp_path, content))


def test_duplicate_agent_ids_rejected(tmp_path: Path):
    content = """
[experiment]
name = "x"

[target]
repo = "https://github.com/vllm-project/vllm"

[prompt]
text = "go"

[providers.anthropic]
api_key = "$ANTHROPIC_API_KEY"

[[agents]]
id = "dup"
model = "anthropic/claude-sonnet-4-6"

[[agents]]
id = "dup"
model = "anthropic/claude-opus-4-8"
"""
    with pytest.raises(ValidationError, match="Agent IDs must be unique"):
        load_config(_write(tmp_path, content))


def test_model_without_provider_segment_rejected(tmp_path: Path):
    content = """
[experiment]
name = "x"

[target]
repo = "https://github.com/vllm-project/vllm"

[prompt]
text = "go"

[providers.anthropic]
api_key = "$ANTHROPIC_API_KEY"

[[agents]]
id = "bad"
model = "claude-sonnet-4-6"
"""
    with pytest.raises(ValidationError, match="Pi model ref"):
        load_config(_write(tmp_path, content))
