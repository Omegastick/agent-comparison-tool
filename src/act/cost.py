"""Token-usage and cost aggregation from Pi traces.

Cost is computed from ground-truth token counts in each ``trace.jsonl`` (the
provider returns usage per assistant message) multiplied by a configurable
pricing table, rather than trusting Pi's own ``cost`` field — Pi carries no
pricing for z.ai models and reports $0 for them.
"""

import csv
import json
import re
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

# Trailing dated-snapshot suffix on a resolved model id, e.g. the ``-20260514``
# or ``-2026-05-14`` a provider appends when an alias resolves to a pin.
_DATE_SUFFIX_RE = re.compile(r"-(?:\d{8}|\d{4}-\d{2}-\d{2})$")


class ModelPricing(BaseModel):
    """USD per 1,000,000 tokens for a single model."""

    input: float = 0.0
    output: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0


class Pricing(BaseModel):
    """Per-model pricing table loaded from ``pricing.toml``."""

    models: dict[str, ModelPricing] = Field(default_factory=dict)

    def _rates_for(self, model: str) -> ModelPricing | None:
        """Look up rates, tolerating a resolved id's trailing dated-snapshot suffix.

        An exact match wins; failing that, a dated id (e.g. ``gpt-5.4-20260514``)
        falls back to its undated base key so it still prices instead of silently
        dropping to "not priced". A genuinely unknown model still returns ``None``.
        """
        rates = self.models.get(model)
        if rates is None and model:
            stripped = _DATE_SUFFIX_RE.sub("", model)
            if stripped != model:
                rates = self.models.get(stripped)
        return rates

    def cost(self, usage: "Usage") -> float | None:
        """Cost in USD for the given usage, or ``None`` if the model is unpriced."""
        rates = self._rates_for(usage.model)
        if rates is None:
            return None
        return (
            usage.input * rates.input
            + usage.output * rates.output
            + usage.cache_read * rates.cache_read
            + usage.cache_write * rates.cache_write
        ) / 1_000_000


def load_pricing(path: Path) -> Pricing:
    """Load and validate a pricing table from a TOML file."""
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return Pricing.model_validate(data)


class Usage(BaseModel):
    """Aggregated token usage for one run."""

    model: str = ""
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input + self.output + self.cache_read + self.cache_write


def aggregate_usage(trace_path: Path) -> Usage:
    """Sum token usage across the assistant messages in a Pi trace.

    Each ``message_end`` event carries the final per-message usage; summing them
    yields the run total. A missing or malformed trace yields zero usage.
    """
    usage = Usage()
    if not trace_path.exists():
        return usage

    with open(trace_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "message_end":
                continue
            message = event.get("message") or {}
            counts = message.get("usage") or {}
            if message.get("model"):
                usage.model = message["model"]
            usage.input += counts.get("input") or 0
            usage.output += counts.get("output") or 0
            usage.cache_read += counts.get("cacheRead") or 0
            usage.cache_write += counts.get("cacheWrite") or 0

    return usage


class RunCost(BaseModel):
    """Per-run usage and computed cost, for the experiment summary."""

    run_id: str
    agent_id: str
    usage: Usage
    cost_usd: float | None

    @property
    def priced(self) -> bool:
        return self.cost_usd is not None


def summarize_run(run_id: str, agent_id: str, trace_path: Path, pricing: Pricing) -> RunCost:
    """Build the cost record for a single run from its trace."""
    usage = aggregate_usage(trace_path)
    return RunCost(
        run_id=run_id,
        agent_id=agent_id,
        usage=usage,
        cost_usd=pricing.cost(usage),
    )


_CSV_FIELDS = (
    "run_id",
    "agent_id",
    "model",
    "input",
    "output",
    "cache_read",
    "cache_write",
    "total_tokens",
    "cost_usd",
)


def write_summary(rows: list[RunCost], results_path: Path) -> None:
    """Write per-run usage and cost to ``summary.csv`` and ``summary.json``."""
    csv_path = results_path / "summary.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for row in sorted(rows, key=lambda r: r.run_id):
            writer.writerow(
                {
                    "run_id": row.run_id,
                    "agent_id": row.agent_id,
                    "model": row.usage.model,
                    "input": row.usage.input,
                    "output": row.usage.output,
                    "cache_read": row.usage.cache_read,
                    "cache_write": row.usage.cache_write,
                    "total_tokens": row.usage.total_tokens,
                    "cost_usd": "" if row.cost_usd is None else f"{row.cost_usd:.6f}",
                }
            )

    json_path = results_path / "summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([row.model_dump() for row in sorted(rows, key=lambda r: r.run_id)], f, indent=2)
