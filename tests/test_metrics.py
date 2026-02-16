"""Tests for metrics collection."""

import json
from pathlib import Path

from act.metrics import (
    collect_run_metrics,
    extract_token_usage_from_session,
    load_container_metrics,
)


class TestLoadContainerMetrics:
    def test_loads_metrics_file(self, tmp_path: Path):
        metrics = {"run_id": "test-1", "exit_code": 0, "duration_seconds": 42}
        (tmp_path / "metrics.json").write_text(json.dumps(metrics))

        result = load_container_metrics(tmp_path)
        assert result == metrics

    def test_missing_file_returns_empty_dict(self, tmp_path: Path):
        assert load_container_metrics(tmp_path) == {}

    def test_malformed_json_returns_empty_dict(self, tmp_path: Path):
        (tmp_path / "metrics.json").write_text("not json{{{")
        assert load_container_metrics(tmp_path) == {}


class TestExtractTokenUsageFromSession:
    def test_sums_tokens_across_messages(self, tmp_path: Path):
        session = {
            "info": {},
            "messages": [
                {
                    "info": {
                        "tokens": {
                            "total": 100,
                            "input": 10,
                            "output": 50,
                            "reasoning": 0,
                            "cache": {"read": 30, "write": 10},
                        }
                    }
                },
                {
                    "info": {
                        "tokens": {
                            "total": 200,
                            "input": 20,
                            "output": 100,
                            "reasoning": 5,
                            "cache": {"read": 60, "write": 15},
                        }
                    }
                },
            ],
        }
        (tmp_path / "opencode_session.json").write_text(json.dumps(session))

        result = extract_token_usage_from_session(tmp_path)
        assert result == {
            "total": 300,
            "input": 30,
            "output": 150,
            "reasoning": 5,
            "cache_read": 90,
            "cache_write": 25,
        }

    def test_missing_file_returns_empty_dict(self, tmp_path: Path):
        assert extract_token_usage_from_session(tmp_path) == {}

    def test_malformed_json_returns_empty_dict(self, tmp_path: Path):
        (tmp_path / "opencode_session.json").write_text("broken")
        assert extract_token_usage_from_session(tmp_path) == {}

    def test_messages_without_tokens_are_skipped(self, tmp_path: Path):
        session = {
            "info": {},
            "messages": [
                {"info": {}},
                {"info": {"tokens": {"total": 50, "input": 10, "output": 40}}},
                {"other": "data"},
            ],
        }
        (tmp_path / "opencode_session.json").write_text(json.dumps(session))

        result = extract_token_usage_from_session(tmp_path)
        assert result["total"] == 50
        assert result["input"] == 10
        assert result["output"] == 40
        assert result["reasoning"] == 0
        assert result["cache_read"] == 0
        assert result["cache_write"] == 0

    def test_empty_message_list(self, tmp_path: Path):
        (tmp_path / "opencode_session.json").write_text(json.dumps({"info": {}, "messages": []}))

        result = extract_token_usage_from_session(tmp_path)
        assert result == {
            "total": 0,
            "input": 0,
            "output": 0,
            "reasoning": 0,
            "cache_read": 0,
            "cache_write": 0,
        }


class TestCollectRunMetrics:
    def test_reads_token_usage_from_session(self, tmp_path: Path):
        container_metrics = {"duration_seconds": 120}
        (tmp_path / "metrics.json").write_text(json.dumps(container_metrics))

        session = {
            "info": {},
            "messages": [
                {
                    "info": {
                        "tokens": {
                            "total": 500,
                            "input": 100,
                            "output": 300,
                            "reasoning": 10,
                            "cache": {"read": 70, "write": 20},
                        }
                    }
                }
            ],
        }
        (tmp_path / "opencode_session.json").write_text(json.dumps(session))

        metrics = collect_run_metrics(
            run_id="test-1",
            agent_id="agent-a",
            workspace_path=tmp_path,
            exit_code=0,
        )
        assert metrics.token_usage["total"] == 500
        assert metrics.token_usage["input"] == 100
        assert metrics.token_usage["cache_read"] == 70
        assert metrics.duration_seconds == 120

    def test_defaults_to_empty_dict_when_session_missing(self, tmp_path: Path):
        metrics = collect_run_metrics(
            run_id="test-1",
            agent_id="agent-a",
            workspace_path=tmp_path,
            exit_code=1,
            error="timeout",
        )
        assert metrics.token_usage == {}
        assert metrics.error == "timeout"
