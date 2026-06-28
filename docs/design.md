# Design rationale

ACT is a *comparison* tool, not a benchmark. It runs N provider-pinned models against one fixed task, each in its own isolated container, and collects the raw output of each run so the differences can be read by hand. There is no grading, scoring, ranking, or "winner".

A few decisions follow from that goal:

- **Thin scaffold (Pi).** Each model runs under the [Pi](https://www.npmjs.com/package/@earendil-works/pi-coding-agent) coding agent with a minimal, identical harness. A heavy harness would normalise away the very model differences the tool exists to surface, so the scaffold is kept as thin as possible and is identical across models.
- **Provider pinning, no opaque routing.** Every model is pinned to a specific first-party provider and endpoint. A model always runs against the provider you configured; there is no fallback or routing layer that could silently swap the model serving a request.
- **Raw artifacts only.** Per run, ACT keeps the diff, the full action trace, and the final message, plus descriptive token/cost and per-run outcome provenance. It does not generate analysis or reports; interpretation is done by hand afterwards.
- **Container isolation is load-bearing.** Pi runs tools unconfined inside the container, so the Docker boundary (non-root user, dropped capabilities, no Docker socket, memory/pid limits) is what keeps a run safe, not optional hardening.

See the top-level [README](../README.md) for usage, the output layout, cost/token caveats, and the security and publishing checklist.
