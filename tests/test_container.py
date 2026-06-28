"""Tests for container module utilities."""

from act.config import ProviderConfig
from act.container import _referenced_env_vars, build_models_json


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
