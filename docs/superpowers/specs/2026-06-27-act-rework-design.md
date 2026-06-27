# ACT Rework — Model-Comparison Tool

Date: 2026-06-27
Status: design approved; tool rework ready to plan. The three concrete vLLM tasks are a tracked follow-up (see §8).

## 1. Why this exists

This tool supports a deep, qualitative article comparing AI coding models. The article's spine: *why do good engineers disagree about whether models differ?* Many of Isaac's colleagues say they can't tell Sonnet from Opus; Isaac's position is that the differences are real but **conditional** — they surface on judgment/understanding-heavy work and vanish on binary, well-specified work. The article shows the actual model outputs and characterises how they differ. It is **not** a benchmark, has **no winner, no scores**, and Isaac does all analysis himself afterwards.

The tool's only job: run N models on the same task in isolated containers and collect the raw outputs plus full action traces. That is the entire scope.

## 2. Goals / non-goals

Goals:
- Run one task across multiple models, each in an isolated container, reproducibly.
- Capture, per run: the code change the model made, its full action trace, and its final message.
- Pin every model to a specific provider/endpoint (no opaque routing).

Non-goals (explicit — do not build these):
- No grading, scoring, ranking, or "winner".
- No AI-analysis / judge step, no generated analysis report.
- No aggregate metrics dashboards. (Operational facts like "did a run fail" surface in the run summary only.)
- No multi-task orchestration beyond running the configured agents on one task.

## 3. Decisions (locked)

- It is a **comparison tool, not a benchmark**. Purge "benchmark" framing repo-wide.
- **Strip the grading AND AI-analysis steps entirely.**
- **Runtime: Pi** (`@earendil-works/pi-coding-agent`), replacing OpenCode. Rationale: thin scaffolding is the methodologically correct choice — a heavy harness normalises away the very model differences the experiment tries to surface. Verified viable for all four models (§6).
- **Models under test:** Claude Sonnet 4.6, Claude Opus 4.8, GPT-5.4, GLM-5.2.
- **Provider pinning (fairness/reproducibility):** Claude via Anthropic direct; GPT-5.4 via OpenAI direct; GLM-5.2 via Zhipu/z.ai direct (first-party — "lab-made models from their own lab"). No OpenRouter. If OpenRouter were ever used, the exact sub-provider must be pinned.
- **Target repo:** `https://github.com/vllm-project/vllm`, pinned to a specific commit.

## 4. What gets removed

- `src/act/analysis.py` (entire AI-analysis/scoring step).
- `analyze` and `run-and-analyze` CLI commands; `AnalysisConfig`; `AnalysisContainerConfig`; `run_analysis`; `docker/analyze-entrypoint.sh`.
- `src/act/metrics.py` OpenCode session-token scraping (`extract_token_usage_from_session`, `RunMetrics`, the per-run `metrics.json` artifact).
- The `list` command (use `ls results/`).
- All "benchmark" naming: `BenchmarkConfig` → `ComparisonConfig`; Docker image `act-opencode` → `act-agent`; README rewritten around comparison, not benchmarking/OpenCode.

## 5. Architecture (kept / modified)

- **`cli.py`** — keep `run` only. Drop `analyze`, `run-and-analyze`, `list`.
- **`config.py`** — `ComparisonConfig` (experiment / target / prompt / settings / agents). Agents carry a Pi model ref; a light `[providers]` block carries non-default overrides (see §7).
- **`runner.py`** — orchestration kept (parallel/sequential via `ThreadPoolExecutor`, workspace management, timeouts). Result collection simplified per §5.1.
- **`container.py`** — rewritten to launch Pi instead of OpenCode: generate Pi's `models.json`, mount it + the API keys, run Pi headless, capture the NDJSON trace. Analysis-container code removed. `ContainerManager` / `WorkspaceManager` structure retained.
- **`display.py`** — simplified to **status-only** (pending / running / done / failed + elapsed per run). The live per-tool activity parsing (`parse_activity_line`, the OpenCode tool-prefix matcher) is **removed** — the full tool-by-tool record lives in `trace.jsonl`.
- **`docker/Dockerfile`** — `node:24-bookworm-slim`; `apt-get install bash ca-certificates git ripgrep`; `npm install -g --ignore-scripts @earendil-works/pi-coding-agent@0.80.2`. (Pin the version for reproducibility.)
- **`docker/entrypoint.sh`** — clone the repo at the pinned commit, set a **git identity** (`git config user.name/user.email` — fixes the "author identity unknown" failure agents hit on first commit), run Pi headless, write the trace + output.

### 5.1 Output layout (lean — raw artifacts only)

```
results/<name>-<timestamp>/
  config.toml
  <agent-id>-<run>/
    diff.patch     # git diff vs the pinned base commit + any new/untracked files — the artifact
    trace.jsonl    # Pi's full NDJSON action trace (every tool call + message)
    output.txt     # final assistant text
```

Rationale for `diff.patch` instead of copying the whole `repo/`: vLLM is large; copying the full tree per run × 4 models × N runs is wasteful and un-committable. The base commit is pinned, so the diff (plus untracked files) is the complete record of what the model did, and results stay small enough to commit and eyeball. There is no per-run `run.json`; provenance is the directory name + `config.toml`, and run failures surface in the end-of-run summary print.

## 6. Pi runtime (verified against source, pi-mono @ 5a07388, npm 0.80.2)

- **Install:** NPM `@earendil-works/pi-coding-agent` (NOT the unrelated PyPI `pi-coding-agent`). Runtime deps: Node 24, bash, git, ripgrep.
- **Headless invocation:** `pi --mode json --no-session -a --model <provider>/<id> "<prompt>" > trace.jsonl`. `--provider`/`--model` is **mandatory** (Pi's default provider is `google`). `--mode json` emits all session events as NDJSON to stdout; `--no-session` is ephemeral; `-a` grants project trust (Pi runs tools unconfined and has no per-call approval — hence Docker isolation is load-bearing, not optional).
- **Trace format:** NDJSON. First line is a session header (`{"type":"session","version":3,...}`), then `agent_start` / `turn_start` / `message_*` / `tool_execution_start|update|end` / `turn_end` / `agent_end`. A tool event looks like `{"type":"tool_execution_end","toolCallId":...,"toolName":"bash","result":{...},"isError":false}`.
- **Config file:** `~/.pi/agent/models.json` (override dir via `PI_CODING_AGENT_DIR`). `apiKey` values support `$VAR` env interpolation. All four target models are **built-in**, so the tool only needs to override `apiKey` per provider — no custom model definitions required.

## 7. Provider config

The tool generates `~/.pi/agent/models.json` from the experiment's `[providers]` block + host env. Keys come from host env (uncommitted `.env`), never the TOML.

| Model | Pi ref | Provider | Transport | baseUrl | Key env |
|---|---|---|---|---|---|
| Claude Sonnet 4.6 | `anthropic/claude-sonnet-4-6` | anthropic | anthropic-messages | `https://api.anthropic.com` (host root, **no `/v1`**) | `ANTHROPIC_API_KEY` |
| Claude Opus 4.8 | `anthropic/claude-opus-4-8` | anthropic | anthropic-messages | `https://api.anthropic.com` | `ANTHROPIC_API_KEY` |
| GPT-5.4 | `openai/gpt-5.4` | openai | **openai-responses** | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| GLM-5.2 | `zai/glm-5.2` | zai | openai-completions | `https://api.z.ai/api/coding/paas/v4` (Coding Plan) or `…/api/paas/v4` (general) — match the key's plan | `ZAI_API_KEY` |

Generated `models.json` (minimal — built-ins carry everything else):
```json
{
  "providers": {
    "anthropic": { "apiKey": "$ANTHROPIC_API_KEY" },
    "openai":    { "apiKey": "$OPENAI_API_KEY" },
    "zai":       { "baseUrl": "https://api.z.ai/api/coding/paas/v4", "apiKey": "$ZAI_API_KEY" }
  }
}
```

Notes / corrections (source-verified):
- **Anthropic `/v1` gotcha:** the SDK appends `/v1/messages`; pinning `…/v1` yields `/v1/v1/messages` → 404. Use the host root. The built-in already defaults to this, so the `baseUrl` override is optional.
- **GPT-5.4 transport:** the built-in `gpt-5.4` uses `openai-responses`. Prefer it — forcing `openai-completions` (which would require a full custom model def with `"api":"openai-completions"`) works but loses cross-turn encrypted-reasoning replay + cache affinity, degrading agentic quality/cost on a reasoning model. Optional stricter reproducibility: define a custom model `gpt-5.4-2026-03-05` under `openai` with `"api":"openai-responses"` to pin the exact dated snapshot.
- **z.ai:** use the built-in `zai/glm-5.2` (it carries the correct z.ai compat: `thinkingFormat:"zai"`, `zaiToolStream:true`, `supportsReasoningEffort:true`). Do **not** rely on baseUrl-only auto-detection to supply those — a hand-rolled custom provider would not get them.

## 8. The three vLLM tasks (tracked next step — not yet final)

Task shapes: (1) write a Jira ticket from a vague need; (2) shape an API; (3) one genuinely-binary fix. All reference the real vLLM codebase. Surveyed and adversarially reality-checked against vLLM `main` @ `9036c89ee410b30913ca8b7d362a7d0805583b51` (2026-06-27).

**Authoring methodology (applies to all three — a finding from the survey):** nearly every real candidate has open PRs racing to merge *and* a pre-chewed solution sitting in its issue thread. To keep the comparison measuring capability rather than cribbing/luck:
- Pin `target.commit` to `9036c89…` so the defect/gap is present at run time.
- Phrase each task as the **stakeholder need / symptom only** — no issue link, no PR reference, no solution hints.
- Deny the in-container agent network access to GitHub issues.
- Re-verify each task is still unsolved on the pinned commit immediately before running.

Current candidate state:

- **Shape-an-API — ACCEPTED:** "expose per-request timing metrics to the caller" (vLLM tracks queue/prefill/decode/ITL internally but only as aggregate Prometheus/OTel; the caller can't get it for their own request). Genuine open design fork — body field vs response headers vs OTEL are competing live proposals, maintainers split, no single correct answer. Confirmed not implemented on the pinned commit. Caveat: a draft PR exists as prior art (leakage risk — withhold it).
- **Jira-ticket — RE-PICK NEEDED:** the strongest *shape* match (scheduler priority-preemption starvation) is contaminated (4 racing PRs + spoon-fed fix in-thread) and merge-race-risky. Cleaner unverified alternates to reality-check next: `cache_salt` prompt-cache isolation parity gap on the Anthropic Messages entrypoint (small, additive plumbing across an analogous surface); or a LoRA cache-residency Prometheus metric (small, additive).
- **Binary-fix — RE-PICK NEEDED:** the surveyed top pick (a test `enforce_eager` one-liner) is **not** actually binary — maintainers dispute the diagnosis and both convergent PRs were closed as bad. The genuinely-binary candidate to reality-check next is the **`moe_wna16` GEMM int32→int64 output-index overflow** (`csrc/.../moe_wna16.cu`): a 64-bit cast with an explicit in-file precedent (lines 95-97) dictating the exact form. One correct outcome by inspection; behavioural repro is GPU-gated but the fix is decidable from the source.

Next action for this section: a short reality-check pass on the two alternates (jira `cache_salt` / LoRA-metric; binary `moe_wna16` overflow), then write the three task configs under `experiments/`.

## 9. Verify-before-coding (smoke test)

Before writing implementation code, confirm in a throwaway container:
- `pi --help` on the pinned version shows `--mode json`, `--no-session`, `-a`, `--model` as expected.
- A trivial headless run against each of the four models succeeds end-to-end and emits a parseable NDJSON trace (this is the live check that Anthropic host-root baseUrl, OpenAI Responses, and the z.ai endpoint/key plan all work — the only things not provable from source).

## 10. Out of scope (deliberate)

- Any analysis, scoring, or report generation (Isaac does this by hand).
- Provider fallback / OpenRouter routing.
- Capturing token-usage/cost metrics (the trace carries usage if ever needed; not collected as a first-class artifact).
- A custom tool-loop runtime — Pi clears the bar, so the fallback is not built.
