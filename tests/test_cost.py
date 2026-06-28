"""Tests for token-usage aggregation and cost computation."""

import json
from pathlib import Path

from act.cost import (
    Pricing,
    aggregate_usage,
    load_pricing,
    summarize_run,
    write_summary,
)

PRICING_TOML = """
[models."claude-opus-4-8"]
input = 5.00
output = 25.00
cache_read = 0.50
cache_write = 6.25
"""


def _message_end(model: str, **counts: int) -> str:
    usage = {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, **counts}
    return json.dumps({"type": "message_end", "message": {"model": model, "usage": usage}})


def _write_trace(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_aggregate_sums_message_end_events(tmp_path: Path) -> None:
    trace = tmp_path / "trace.jsonl"
    _write_trace(
        trace,
        [
            json.dumps({"type": "message_start", "message": {"model": "claude-opus-4-8"}}),
            _message_end("claude-opus-4-8", output=74, cacheWrite=2177),
            _message_end("claude-opus-4-8", output=22, cacheRead=2177, cacheWrite=101),
        ],
    )

    usage = aggregate_usage(trace)

    assert usage.model == "claude-opus-4-8"
    assert usage.output == 96
    assert usage.cache_read == 2177
    assert usage.cache_write == 2278
    assert usage.total_tokens == 96 + 2177 + 2278


def test_aggregate_ignores_non_message_end_and_blank_lines(tmp_path: Path) -> None:
    trace = tmp_path / "trace.jsonl"
    _write_trace(
        trace,
        [
            "",
            json.dumps({"type": "message_update", "message": {"usage": {"output": 999}}}),
            _message_end("gpt-5.4", input=10, output=5),
        ],
    )

    usage = aggregate_usage(trace)

    assert usage.input == 10
    assert usage.output == 5


def test_aggregate_tolerates_malformed_lines(tmp_path: Path) -> None:
    trace = tmp_path / "trace.jsonl"
    _write_trace(trace, ["not json", _message_end("gpt-5.4", output=7)])

    assert aggregate_usage(trace).output == 7


def test_aggregate_missing_trace_is_zero(tmp_path: Path) -> None:
    usage = aggregate_usage(tmp_path / "absent.jsonl")
    assert usage.total_tokens == 0
    assert usage.model == ""


def test_cost_computed_from_pricing(tmp_path: Path) -> None:
    pricing = load_pricing_from_str(tmp_path)
    trace = tmp_path / "trace.jsonl"
    _write_trace(trace, [_message_end("claude-opus-4-8", output=1000)])

    row = summarize_run("opus-1", "opus", trace, pricing)

    # 1000 output tokens at $25 / 1M = $0.025
    assert row.cost_usd is not None
    assert abs(row.cost_usd - 0.025) < 1e-9
    assert row.priced


def test_unpriced_model_reports_none(tmp_path: Path) -> None:
    pricing = load_pricing_from_str(tmp_path)
    trace = tmp_path / "trace.jsonl"
    _write_trace(trace, [_message_end("glm-5.2", output=1000)])

    row = summarize_run("glm-1", "glm", trace, pricing)

    assert row.cost_usd is None
    assert not row.priced
    assert row.usage.total_tokens == 1000  # tokens still recorded


def test_empty_pricing_table_prices_nothing(tmp_path: Path) -> None:
    trace = tmp_path / "trace.jsonl"
    _write_trace(trace, [_message_end("claude-opus-4-8", output=1000)])

    row = summarize_run("opus-1", "opus", trace, Pricing())

    assert row.cost_usd is None


def test_write_summary_emits_csv_and_json(tmp_path: Path) -> None:
    pricing = load_pricing_from_str(tmp_path)
    trace = tmp_path / "trace.jsonl"
    _write_trace(trace, [_message_end("claude-opus-4-8", output=1000)])
    priced = summarize_run("opus-1", "opus", trace, pricing)
    unpriced = summarize_run("glm-1", "glm", tmp_path / "missing.jsonl", pricing)

    write_summary([priced, unpriced], tmp_path)

    csv_text = (tmp_path / "summary.csv").read_text(encoding="utf-8")
    assert "run_id,agent_id,model" in csv_text
    assert "0.025000" in csv_text  # priced run
    rows = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert {r["run_id"] for r in rows} == {"opus-1", "glm-1"}
    assert next(r for r in rows if r["run_id"] == "glm-1")["cost_usd"] is None


def load_pricing_from_str(tmp_path: Path) -> Pricing:
    path = tmp_path / "pricing.toml"
    path.write_text(PRICING_TOML, encoding="utf-8")
    return load_pricing(path)
