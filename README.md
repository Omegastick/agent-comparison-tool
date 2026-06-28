# ACT (Agent Comparison Tool)

A tool for comparing AI coding models on the same task. ACT runs several provider-pinned models against one task, each in its own isolated Docker container running the [Pi](https://www.npmjs.com/package/@earendil-works/pi-coding-agent) coding agent, and collects the raw output of each run: the code change it made, its full action trace, and its final message.

ACT is deliberately not a benchmark. There is no grading, no scoring, no ranking, and no "winner". It exists to surface raw model behaviour on a fixed task so the differences can be read by hand afterwards.

## What it does

For an experiment that names N models and one task, ACT:

- Clones the target repository at a pinned commit into an isolated container per run.
- Runs Pi headless with the configured model against the task prompt.
- Collects three raw artifacts per run — nothing else (see [Output layout](#output-layout)).

Each model is pinned to a specific provider and endpoint, so there is no opaque routing: a model always runs against the provider you configured.

## Installation

```bash
uv sync
```

## Prerequisites

- Docker.
- API keys for the providers your experiment uses, exported into the host environment. ACT forwards the referenced keys into the container; the keys are never written into the experiment TOML (the config only carries `$ENV_VAR` references). For the default four-model set:
  - `ANTHROPIC_API_KEY`
  - `OPENAI_API_KEY`
  - `ZAI_API_KEY`

> [!WARNING]
> **Collected artifacts may contain your provider API keys.** Keys are forwarded into each container as plaintext environment variables, and Pi runs tools unconfined, so a model that runs `env` / `echo $ANTHROPIC_API_KEY` could write a key verbatim into its `trace.jsonl`, `output.txt`, or `diff.patch`. As a safety net, ACT scrubs the exact value of every forwarded key out of these text artifacts when it collects them (each key value is replaced with `***REDACTED***`). This is a best-effort substring scrub of *known* key values only — it cannot catch a key the model has transformed (base64, split across lines, etc.). **Always review the artifacts of any run before publishing it.** See [Security & publishing](#security--publishing).

## Models and provider pinning

The default experiments compare four models, each pinned to a first-party provider:

| Model | Pi model ref | Provider | Key env |
|---|---|---|---|
| Claude Sonnet 4.6 | `anthropic/claude-sonnet-4-6` | Anthropic direct | `ANTHROPIC_API_KEY` |
| Claude Opus 4.8 | `anthropic/claude-opus-4-8` | Anthropic direct | `ANTHROPIC_API_KEY` |
| GPT-5.4 | `openai/gpt-5.4` | OpenAI direct | `OPENAI_API_KEY` |
| GLM-5.2 | `zai/glm-5.2` | Zhipu / z.ai direct | `ZAI_API_KEY` |

Provider endpoints and keys come from the experiment's `[providers]` block plus host environment. ACT generates Pi's `models.json` from this block at run time. All four models are Pi built-ins, so a provider entry only needs to carry its API key (an `$ENV_VAR` reference), with `base_url`/`api` overrides supplied only where a provider needs one (e.g. z.ai's `https://api.z.ai/api/paas/v4` endpoint).

## Usage

```bash
uv run act experiments/vllm-jira-ticket.toml
```

Experiments are configured with TOML files; see `experiments/` for the three bundled vLLM tasks. Each experiment names a target repo + pinned commit, a task prompt, run settings, the `[providers]` block, and the list of agents.

Each agent requires:

- `id` — unique identifier for the run directories.
- `model` — a Pi model ref of the form `<provider>/<id>`; the provider segment must have a matching `[providers]` entry.
- `extra_args` — extra CLI arguments passed through to Pi (optional).

## Docker image

The tool runs each model in the `act-agent` Docker image. Rebuild it after changing anything under `docker/`:

```bash
just rebuild
```

## Output layout

Results are written to `results/<experiment-name>-<timestamp>/`. Each run directory holds only the raw artifacts — the full tree is never copied, since the target commit is pinned and the diff is the complete record of what the model changed:

```
results/vllm-binary-fix-2026-06-28-123456/
  config.toml              # copy of the experiment config
  summary.csv              # per-run token usage + cost (one row per run)
  summary.json             # same data as structured JSON
  runs.json                # per-run outcome: status, exit code, error, duration, resolved model id, run date, rate-limit flag
  sonnet-4.6-1/
    diff.patch             # git diff vs the pinned base commit, including untracked AND .gitignore'd files the model created
    trace.jsonl            # Pi's full NDJSON action trace (every tool call + message)
    output.txt             # the model's final assistant message (omitted if extraction finds nothing)
    run-meta.json          # the exact Pi argv + version used for this run (scaffold provenance)
  sonnet-4.6-2/
  opus-4.8-1/
  gpt-5.4-1/
  glm-5.2-1/
  ...
```

`diff.patch` is built with `git add -Af`, so it captures everything the model wrote against the pinned base — including files the target repo's own `.gitignore` would normally drop — making it a complete record rather than only the tracked changes.

`runs.json` is the per-run provenance you'll want when returning to a result later. For each run it records the final `status` (`completed` / `failed` / `timeout`), `exit_code`, `error`, `duration_seconds`, and a `rate_limited` flag (set when the error/logs look like provider throttling). It also records the `model` actually served — read back from the trace so a floating alias (e.g. `claude-opus-4-8`) is resolved to the concrete id the provider returned — alongside `model_source` (`trace` when resolved from the run, `config` when only the configured ref was available) and the `run_date`. Run failures also surface in the end-of-run summary print.

## Cost & token tracking

Each run's `trace.jsonl` carries ground-truth token counts (input, output, cache-read, cache-write) per assistant message. ACT sums these and multiplies by `pricing.toml` — a table of USD-per-1M-token rates keyed by model id — to produce `summary.csv`/`summary.json` and a cost table in the end-of-run print. Cost is computed from these counts rather than from Pi's own cost field, which has no pricing for z.ai models. A model absent from `pricing.toml` is reported as "not priced" (its tokens are still recorded). Point `--pricing` at an alternate table if needed.

## Methodology & caveats

ACT is a comparison tool, not a benchmark, and the way it runs models has consequences you should disclose alongside any results:

- **Models run at unmatched vendor defaults.** ACT does not pin temperature, sampling, or reasoning/thinking budget; unless an agent's `extra_args` sets them, each model runs at *its own provider's defaults*, which differ across providers. Reasoning effort in particular drives both output quality and cost, so the models are not configured identically. Disclose this when presenting outputs.
- **Cost and tokens are not apples-to-apples across providers.** Each per-provider dollar figure is accurate to that provider's real billing, and all four models' prompt caching is captured in the traces (cache reads only fail to appear for contexts too small to cache, well below a normal run). What differs is the billing model: Claude pays a premium on cache writes while OpenAI and GLM do not (see `pricing.toml`), and a provider that routes most context through cache accumulates a far larger token *count* for the same work. **Compare by category (fresh input vs cache read vs output), not by a single total-token figure**, and read a cost gap as part billing-model and part the model's own verbosity. The full per-category breakdown is preserved in `summary.csv`/`summary.json`.
- **Present all N runs.** With `runs_per_agent` (default 3) runs per model, there is real run-to-run variance on open-ended judgment tasks. Show every run rather than cherry-picking one, so the variance is visible.
- **The binary-fix task is a control observation, not a scored test.** It exists to see whether models *converge* on the one objectively-correct fix, not to grade them. There is no ground truth for the judgment tasks and no grading anywhere.
- **Small n.** A handful of runs on a handful of tasks characterises behaviour qualitatively; it does not support statistical claims.

## Security & publishing

`results/` is gitignored by default, so runs never get committed by accident and the publication step is always deliberate.

Before publishing any run (committing it, pasting a trace into an article, sharing a diff):

1. **Confirm the scrub ran and review the artifacts.** ACT redacts the value of every forwarded provider key from `trace.jsonl`, `output.txt`, and `diff.patch` on collection (replacing it with `***REDACTED***`), but this only catches *verbatim* key values. Read the artifacts you intend to publish and check for anything else sensitive — credentials the model fetched, host paths, etc.
2. **Then, if you want to publish a curated run**, override the ignore rule for that specific path so the commit is intentional, e.g.:

   ```bash
   git add -f results/vllm-binary-fix-2026-06-28-123456/
   git commit -m "Add evidence for the article: vLLM binary-fix run"
   ```

   Scrubbing and manual review (step 1) are preconditions for this — never force-add a run you have not reviewed. Prefer committing a single curated run (or a separate `article-evidence/` directory) rather than un-ignoring `results/` wholesale.

## Smoke test

Pi's provider transports and endpoints (Anthropic host-root base URL, OpenAI Responses, the z.ai endpoint/key plan) are the only things that cannot be verified from source. Before relying on a fresh setup, run a small experiment end-to-end with all four providers configured — this requires `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and `ZAI_API_KEY` to be exported on the host — and confirm each run produces a parseable `trace.jsonl`.
