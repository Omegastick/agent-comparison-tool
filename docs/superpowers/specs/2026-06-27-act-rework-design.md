# ACT Rework — Model-Comparison Tool

Date: 2026-06-27
Status: design approved; tool rework ready to plan. All three vLLM tasks are chosen (§8); writing their experiment configs is the remaining task-side step.

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

## 8. The three vLLM tasks (chosen)

Each task shape mapped to a real vLLM home. Surveyed and adversarially reality-checked against vLLM `main` @ `9036c89ee410b30913ca8b7d362a7d0805583b51` (2026-06-27); pin `target.commit` there so each gap/defect is present at run time.

1. **Jira ticket from a vague need (judgment) — scheduler priority-preemption starvation** (issue #40004). Stakeholder need: "we tag requests as high-priority, but under heavy load they still wait behind already-running low-priority work — priority seems to do nothing once the box is full." The model must understand vLLM's V1 scheduler (running vs waiting queues, the KV-cache-block budget vs the `max_num_seqs` concurrency-slot budget, where preemption currently fires) and decompose that into well-scoped tickets. Code area: `vllm/v1/core/sched/`. No single correct ticket — this is a subjective decomposition/ticket-quality test.
2. **Shape an API (judgment) — per-request timing metrics** (issue #40076). vLLM tracks per-request timing (queue/prefill/decode/ITL) internally but only exposes it as aggregate Prometheus/OTel; a caller can't get the timings for their own request. Genuinely open design fork with no agreed answer — response-body field vs HTTP headers vs OTEL are competing live proposals and maintainers are split. The opt-in surface, schema, and streaming placement are all real design calls. Code area: `vllm/entrypoints/openai/`.
3. **Binary fix (control) — `moe_wna16` GEMM output-index integer overflow** (issue #45884). In `csrc/libtorch_stable/moe/moe_wna16.cu` (~line 219), the output offset `token_index * size_n + offset_n` is computed in 32-bit and overflows for large token counts, causing an out-of-bounds `atomicAdd`. One correct fix: widen to 64-bit before the multiply (`static_cast<int64_t>(token_index) * size_n + offset_n`), matching the in-file precedent at lines ~95-97. **Verified clean control** (reality-check, 2026-06-28): present at the pinned commit and current main, unmerged, no maintainer/reviewer dispute in any thread, two independent PRs (#45907, #46209) converge on the identical cast. This is the objectively-correct-answer the control task requires.

**Framing / authoring rules.** Tasks 1 and 2 are subjective (judgment) and task 3 is the objective control; there is no ground-truth grading — Isaac assesses the outputs qualitatively. So the only authoring rules that matter:
- Give the model the **need / symptom only** — no issue link, no PR reference, no in-container GitHub access — so it reasons from the codebase, not from a public thread. This neutralises the "the answer is discussed online" concern; it is *not* a reason to avoid real or popular issues.
- Pin `target.commit` so the gap/defect is present at run time.
- For the binary control specifically, the fix must be objectively correct so that model *convergence* is meaningful — verified for task 3 above. (The earlier "benchmark-hygiene" objections — contamination, merge-race, grading against a canonical PR — do not apply here: this is a subjective comparison, not a graded benchmark.)

Mild residual (judgment tasks only, not a blocker): a heavily-discussed need may be partly memorised by the models, nudging them toward the community's framing rather than fresh reasoning — unavoidable for any real popular issue.

Next action: write the three task configs under `experiments/` (the vague-need prompt per task, the pinned commit, the four agents).

## 9. Verify-before-coding (smoke test)

Before writing implementation code, confirm in a throwaway container:
- `pi --help` on the pinned version shows `--mode json`, `--no-session`, `-a`, `--model` as expected.
- A trivial headless run against each of the four models succeeds end-to-end and emits a parseable NDJSON trace (this is the live check that Anthropic host-root baseUrl, OpenAI Responses, and the z.ai endpoint/key plan all work — the only things not provable from source).

## 10. Out of scope (deliberate)

- Any analysis, scoring, or report generation (Isaac does this by hand).
- Provider fallback / OpenRouter routing.
- Capturing token-usage/cost metrics (the trace carries usage if ever needed; not collected as a first-class artifact).
- A custom tool-loop runtime — Pi clears the bar, so the fallback is not built.
