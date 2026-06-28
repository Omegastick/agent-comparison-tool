"""Tests for the experiment runner's result collection."""

import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from act.config import ProviderConfig
from act.container import ContainerConfig, ContainerResult
from act.display import RunStatus
from act.runner import ExperimentRunner, _looks_rate_limited, _RunRecord


def _make_workspace(tmp_path: Path, run_id: str) -> Path:
    """Create a container workspace populated like a real Pi run."""
    workspace = tmp_path / "ws" / run_id
    workspace.mkdir(parents=True)
    (workspace / "diff.patch").write_text("diff --git a/x b/x\n")
    (workspace / "trace.jsonl").write_text('{"type": "session"}\n')
    (workspace / "output.txt").write_text("final message\n")
    return workspace


def _collect(results, results_path: Path) -> None:
    # _collect_results only reads self.ARTIFACTS, so a stand-in avoids the
    # docker client that ExperimentRunner.__init__ would otherwise create.
    runner = SimpleNamespace(ARTIFACTS=ExperimentRunner.ARTIFACTS)
    ExperimentRunner._collect_results(runner, results, results_path)  # type: ignore[arg-type]


class TestCollectResults:
    def test_copies_only_lean_artifacts(self, tmp_path: Path):
        workspace = _make_workspace(tmp_path, "opus-1")
        results = [("opus-1", "opus", ContainerResult("opus-1", 0, "", workspace))]

        results_path = tmp_path / "results"
        _collect(results, results_path)

        run_dir = results_path / "opus-1"
        assert {p.name for p in run_dir.iterdir()} == {
            "diff.patch",
            "trace.jsonl",
            "output.txt",
        }

    def test_does_not_copy_repo_tree_or_metrics(self, tmp_path: Path):
        workspace = _make_workspace(tmp_path, "opus-1")
        # Simulate stray files the lean layout must not pick up.
        (workspace / "metrics.json").write_text("{}")
        repo = workspace / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("vllm")

        results = [("opus-1", "opus", ContainerResult("opus-1", 0, "", workspace))]
        results_path = tmp_path / "results"
        _collect(results, results_path)

        run_dir = results_path / "opus-1"
        assert not (run_dir / "metrics.json").exists()
        assert not (run_dir / "repo").exists()

    def test_creates_run_dir_even_with_missing_artifacts(self, tmp_path: Path):
        # A failed run may leave no workspace files; the dir is still created.
        workspace = tmp_path / "ws" / "glm-1"
        workspace.mkdir(parents=True)
        results = [
            ("glm-1", "glm", ContainerResult("glm-1", 1, "boom", workspace, error="boom")),
        ]
        results_path = tmp_path / "results"
        _collect(results, results_path)

        run_dir = results_path / "glm-1"
        assert run_dir.is_dir()
        assert list(run_dir.iterdir()) == []


def _providers() -> dict[str, ProviderConfig]:
    return {
        "anthropic": ProviderConfig(api_key="$ANTHROPIC_API_KEY"),
        "openai": ProviderConfig(api_key="$OPENAI_API_KEY"),
    }


class TestValidateProviderKeys:
    def test_raises_listing_missing_vars(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        stub = SimpleNamespace(config=SimpleNamespace(providers=_providers()))

        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            ExperimentRunner._validate_provider_keys(stub)  # type: ignore[arg-type]

    def test_passes_when_all_set(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
        monkeypatch.setenv("OPENAI_API_KEY", "y")
        stub = SimpleNamespace(config=SimpleNamespace(providers=_providers()))

        ExperimentRunner._validate_provider_keys(stub)  # type: ignore[arg-type]


class TestScrubSecrets:
    def _scrub(self, stub, results_path: Path) -> None:
        ExperimentRunner._scrub_secrets(stub, results_path)  # type: ignore[arg-type]

    def test_redacts_every_provider_key_across_artifacts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-AAA")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-oai-secret-BBB")
        results_path = tmp_path / "results"
        run_dir = results_path / "opus-1"
        run_dir.mkdir(parents=True)
        # A run may be forwarded keys other than its own, so all must be scrubbed.
        (run_dir / "trace.jsonl").write_text('{"env": "sk-ant-secret-AAA"}\n')
        (run_dir / "output.txt").write_text("leaked sk-oai-secret-BBB here")
        (run_dir / "diff.patch").write_text("no secrets here\n")

        stub = SimpleNamespace(
            config=SimpleNamespace(providers=_providers()),
            ARTIFACTS=ExperimentRunner.ARTIFACTS,
        )
        self._scrub(stub, results_path)

        trace = (run_dir / "trace.jsonl").read_text()
        output = (run_dir / "output.txt").read_text()
        assert "sk-ant-secret-AAA" not in trace
        assert "***REDACTED***" in trace
        assert "sk-oai-secret-BBB" not in output
        assert "***REDACTED***" in output
        assert (run_dir / "diff.patch").read_text() == "no secrets here\n"

    def test_noop_when_no_keys_resolved(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        results_path = tmp_path / "results"
        run_dir = results_path / "opus-1"
        run_dir.mkdir(parents=True)
        (run_dir / "trace.jsonl").write_text("plain content\n")

        stub = SimpleNamespace(
            config=SimpleNamespace(providers=_providers()),
            ARTIFACTS=ExperimentRunner.ARTIFACTS,
        )
        self._scrub(stub, results_path)

        assert (run_dir / "trace.jsonl").read_text() == "plain content\n"


class TestWriteOutcomes:
    def test_persists_outcome_with_resolved_model_from_trace(self, tmp_path: Path):
        results_path = tmp_path / "results"
        run_dir = results_path / "opus-1"
        run_dir.mkdir(parents=True)
        (run_dir / "trace.jsonl").write_text(
            json.dumps(
                {
                    "type": "message_end",
                    "message": {"model": "claude-opus-4-8-20260514", "usage": {"output": 5}},
                }
            )
            + "\n"
        )

        stub = SimpleNamespace(
            run_date="2026-06-28",
            _records={
                "opus-1": _RunRecord(
                    status=RunStatus.COMPLETED,
                    exit_code=0,
                    error=None,
                    duration=12.5,
                    model_ref="anthropic/claude-opus-4-8",
                    rate_limited=False,
                )
            },
        )
        results = [("opus-1", "opus", ContainerResult("opus-1", 0, "", run_dir))]
        ExperimentRunner._write_outcomes(stub, results, results_path)  # type: ignore[arg-type]

        rows = json.loads((results_path / "runs.json").read_text())
        assert len(rows) == 1
        row = rows[0]
        assert row["status"] == "completed"
        assert row["exit_code"] == 0
        assert row["duration_seconds"] == 12.5
        assert row["model"] == "claude-opus-4-8-20260514"
        assert row["model_source"] == "trace"
        assert row["run_date"] == "2026-06-28"

    def test_timeout_outcome_falls_back_to_configured_ref(self, tmp_path: Path):
        results_path = tmp_path / "results"
        (results_path / "glm-1").mkdir(parents=True)  # no trace

        stub = SimpleNamespace(
            run_date="2026-06-28",
            _records={
                "glm-1": _RunRecord(
                    status=RunStatus.TIMEOUT,
                    exit_code=1,
                    error="killed on timeout",
                    duration=600.0,
                    model_ref="zai/glm-5.2",
                    rate_limited=False,
                )
            },
        )
        results = [
            ("glm-1", "glm", ContainerResult("glm-1", 1, "", results_path / "glm-1", timed_out=True))
        ]
        ExperimentRunner._write_outcomes(stub, results, results_path)  # type: ignore[arg-type]

        row = json.loads((results_path / "runs.json").read_text())[0]
        assert row["status"] == "timeout"
        assert row["model"] == "zai/glm-5.2"
        assert row["model_source"] == "config"


class TestRunSingleStatus:
    def _run(self, result: ContainerResult) -> RunStatus:
        stub = SimpleNamespace(
            display=SimpleNamespace(update_run=lambda *a, **k: None),
            container_manager=SimpleNamespace(run=lambda config: result),
            _records={},
            _records_lock=threading.Lock(),
        )
        stub._record = ExperimentRunner._record.__get__(stub)
        config = ContainerConfig(
            run_id=result.run_id,
            repo_url="r",
            repo_commit=None,
            prompt_file=None,
            prompt_text="go",
            pi_model="anthropic/claude-opus-4-8",
            providers={},
            extra_args=[],
            timeout_seconds=10,
            workspace_path=Path("/tmp"),
        )
        ExperimentRunner._run_single(stub, result.run_id, config)  # type: ignore[arg-type]
        return stub._records[result.run_id].status

    def test_timed_out_result_maps_to_timeout(self, tmp_path: Path):
        result = ContainerResult("t-1", 1, "", tmp_path, error="timeout", timed_out=True)
        assert self._run(result) == RunStatus.TIMEOUT

    def test_zero_exit_maps_to_completed(self, tmp_path: Path):
        assert self._run(ContainerResult("c-1", 0, "", tmp_path)) == RunStatus.COMPLETED

    def test_nonzero_exit_maps_to_failed(self, tmp_path: Path):
        assert self._run(ContainerResult("f-1", 1, "", tmp_path)) == RunStatus.FAILED

    def test_rate_limit_marker_recorded(self, tmp_path: Path):
        result = ContainerResult("r-1", 1, "HTTP 429 Too Many Requests", tmp_path)
        stub = SimpleNamespace(
            display=SimpleNamespace(update_run=lambda *a, **k: None),
            container_manager=SimpleNamespace(run=lambda config: result),
            _records={},
            _records_lock=threading.Lock(),
        )
        stub._record = ExperimentRunner._record.__get__(stub)
        config = ContainerConfig(
            run_id="r-1",
            repo_url="r",
            repo_commit=None,
            prompt_file=None,
            prompt_text="go",
            pi_model="anthropic/claude-opus-4-8",
            providers={},
            extra_args=[],
            timeout_seconds=10,
            workspace_path=tmp_path,
        )
        ExperimentRunner._run_single(stub, "r-1", config)  # type: ignore[arg-type]
        assert stub._records["r-1"].rate_limited


def test_looks_rate_limited():
    assert _looks_rate_limited("Error 429: rate limit exceeded")
    assert _looks_rate_limited("provider Overloaded")
    assert not _looks_rate_limited("auth failure")
    assert not _looks_rate_limited(None)
