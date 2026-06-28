"""Tests for the experiment runner's result collection."""

from pathlib import Path
from types import SimpleNamespace

from act.container import ContainerResult
from act.runner import ExperimentRunner


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
