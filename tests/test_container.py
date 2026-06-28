"""Tests for container module utilities."""

from act.config import ProviderConfig
from act.container import _referenced_env_vars, build_models_json, parse_activity_line


class TestParseActivityLine:
    def test_glob_tool_with_ansi(self):
        line = "\x1b[32m✱ Glob\x1b[0m found 3 files"
        assert parse_activity_line(line) == "✱ Glob found 3 files"

    def test_read_tool_with_ansi(self):
        line = "\x1b[34m→ Read\x1b[0m src/main.py"
        assert parse_activity_line(line) == "→ Read src/main.py"

    def test_write_tool_with_ansi(self):
        line = "\x1b[34m← Write\x1b[0m src/output.py"
        assert parse_activity_line(line) == "← Write src/output.py"

    def test_bash_tool_with_ansi(self):
        line = "\x1b[33m$ git status\x1b[0m"
        assert parse_activity_line(line) == "$ git status"

    def test_settings_tool(self):
        line = "⚙ Settings updated"
        assert parse_activity_line(line) == "⚙ Settings updated"

    def test_plain_tool_prefix_no_ansi(self):
        line = "✱ Glob **/*.py"
        assert parse_activity_line(line) == "✱ Glob **/*.py"

    def test_non_tool_line_returns_none(self):
        line = "Starting run..."
        assert parse_activity_line(line) is None

    def test_empty_line_returns_none(self):
        assert parse_activity_line("") is None

    def test_ansi_only_returns_none(self):
        assert parse_activity_line("\x1b[32m\x1b[0m") is None

    def test_line_with_nested_ansi_codes(self):
        line = "\x1b[1m\x1b[34m→ Read\x1b[0m\x1b[0m /workspace/src/main.py"
        assert parse_activity_line(line) == "→ Read /workspace/src/main.py"

    def test_whitespace_stripped(self):
        line = "  \x1b[32m✱ Glob\x1b[0m results  \n"
        assert parse_activity_line(line) == "✱ Glob results"

    def test_bullet_task_with_ansi(self):
        line = "\x1b[0m• \x1b[0mCreate Speckit plan\x1b[90m General Agent\x1b[0m"
        assert parse_activity_line(line) == "• Create Speckit plan General Agent"

    def test_regular_log_with_ansi_returns_none(self):
        line = "\x1b[32mINFO\x1b[0m: Container started successfully"
        assert parse_activity_line(line) is None


def _providers() -> dict[str, ProviderConfig]:
    return {
        "anthropic": ProviderConfig(
            api_key="$ANTHROPIC_API_KEY",
            base_url="https://api.anthropic.com",
        ),
        "openai": ProviderConfig(api_key="$OPENAI_API_KEY"),
        "zai": ProviderConfig(
            api_key="$ZAI_API_KEY",
            base_url="https://api.z.ai/api/coding/paas/v4",
        ),
    }


class TestBuildModelsJson:
    def test_top_level_providers_key(self):
        result = build_models_json(_providers())
        assert set(result) == {"providers"}
        assert set(result["providers"]) == {"anthropic", "openai", "zai"}

    def test_api_keys_are_env_refs(self):
        providers = build_models_json(_providers())["providers"]
        assert providers["anthropic"]["apiKey"] == "$ANTHROPIC_API_KEY"
        assert providers["openai"]["apiKey"] == "$OPENAI_API_KEY"
        assert providers["zai"]["apiKey"] == "$ZAI_API_KEY"

    def test_anthropic_base_url_is_host_root_without_v1(self):
        anthropic = build_models_json(_providers())["providers"]["anthropic"]
        assert anthropic["baseUrl"] == "https://api.anthropic.com"
        assert not anthropic["baseUrl"].endswith("/v1")

    def test_zai_base_url_passed_through(self):
        zai = build_models_json(_providers())["providers"]["zai"]
        assert zai["baseUrl"] == "https://api.z.ai/api/coding/paas/v4"

    def test_provider_without_overrides_carries_only_api_key(self):
        # Built-ins supply everything else, so baseUrl/api are omitted when unset.
        openai = build_models_json(_providers())["providers"]["openai"]
        assert openai == {"apiKey": "$OPENAI_API_KEY"}

    def test_api_override_included_when_set(self):
        providers = {"openai": ProviderConfig(api_key="$OPENAI_API_KEY", api="openai-responses")}
        assert build_models_json(providers)["providers"]["openai"]["api"] == "openai-responses"


class TestReferencedEnvVars:
    def test_collects_env_refs_from_api_keys(self):
        assert _referenced_env_vars(_providers()) == {
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "ZAI_API_KEY",
        }

    def test_collects_refs_from_base_url(self):
        providers = {"custom": ProviderConfig(api_key="$KEY", base_url="https://$HOST/v1")}
        assert _referenced_env_vars(providers) == {"KEY", "HOST"}

    def test_ignores_literal_values(self):
        providers = {"custom": ProviderConfig(api_key="literal-secret")}
        assert _referenced_env_vars(providers) == set()
