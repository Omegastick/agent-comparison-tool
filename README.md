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
- API keys for the providers your experiment uses, exported into the host environment (ACT forwards the referenced keys into the container; they are never written into the TOML). For the default four-model set:
  - `ANTHROPIC_API_KEY`
  - `OPENAI_API_KEY`
  - `ZAI_API_KEY`

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
  summary.csv              # per-run token usage + cost
  summary.json             # same data as structured JSON
  sonnet-4.6-1/
    diff.patch             # git diff vs the pinned base commit, plus any new/untracked files
    trace.jsonl            # Pi's full NDJSON action trace (every tool call + message)
    output.txt             # the model's final assistant message
  sonnet-4.6-2/
  opus-4.8-1/
  gpt-5.4-1/
  glm-5.2-1/
  ...
```

Run failures surface in the end-of-run summary print; there is no separate per-run status file.

## Cost & token tracking

Each run's `trace.jsonl` carries ground-truth token counts (input, output, cache-read, cache-write) per assistant message. ACT sums these and multiplies by `pricing.toml` — a table of USD-per-1M-token rates keyed by model id — to produce `summary.csv`/`summary.json` and a cost table in the end-of-run print. Cost is computed from these counts rather than from Pi's own cost field, which has no pricing for z.ai models. A model absent from `pricing.toml` is reported as "not priced" (its tokens are still recorded). Point `--pricing` at an alternate table if needed.

## Smoke test

Pi's provider transports and endpoints (Anthropic host-root base URL, OpenAI Responses, the z.ai endpoint/key plan) are the only things that cannot be verified from source. Before relying on a fresh setup, run a small experiment end-to-end with all four providers configured — this requires `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and `ZAI_API_KEY` to be exported on the host — and confirm each run produces a parseable `trace.jsonl`.
