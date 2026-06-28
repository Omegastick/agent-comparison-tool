#!/bin/bash
# Run a single model headless via Pi against a pinned repo commit, capturing the
# action trace, the final assistant message, and the full diff.
#
# Environment variables (in):
#   REPO_URL       git URL of the target repository
#   REPO_COMMIT    commit SHA / ref to pin the checkout to (optional)
#   PROMPT_TEXT    inline task prompt, or
#   PROMPT_FILE    path to a prompt file resolvable inside the container
#   PI_MODEL       Pi model ref, e.g. anthropic/claude-opus-4-8
#   PI_EXTRA_ARGS  extra args appended to the pi invocation (optional)
#   RUN_ID         identifier for this run (logging only)
#   plus the per-provider API-key envs referenced by models.json
#
# Artifacts (out, under /workspace):
#   trace.jsonl  Pi's full NDJSON action trace
#   output.txt   final assistant text
#   diff.patch   git diff vs the pinned base commit, including untracked files
#
# Note: -e is intentionally NOT set. Pi may exit non-zero, but we still want to
# emit the artifacts and propagate Pi's exit code at the end.
set -uo pipefail

REPO_DIR="${HOME}/repo"
TRACE_FILE="/workspace/trace.jsonl"
OUTPUT_FILE="/workspace/output.txt"
DIFF_FILE="/workspace/diff.patch"

log() { echo "[act] $*" >&2; }

setup_repo() {
    log "Cloning ${REPO_URL} into ${REPO_DIR}"
    git init -q "$REPO_DIR"
    cd "$REPO_DIR" || exit 1
    git remote add origin "$REPO_URL"
    # Fetch only the pinned commit (GitHub allows fetching a bare SHA), keeping
    # large target repos like vLLM cheap to check out.
    if [ -n "${REPO_COMMIT:-}" ]; then
        log "Fetching pinned commit ${REPO_COMMIT}"
        git fetch -q --depth=1 origin "$REPO_COMMIT"
    else
        log "Fetching default branch HEAD"
        git fetch -q --depth=1 origin HEAD
    fi
    git checkout -q FETCH_HEAD

    # Pi's editing tools commit; without an identity the first commit aborts
    # with "author identity unknown".
    git config user.name "ACT Agent"
    git config user.email "act-agent@example.invalid"
}

resolve_prompt() {
    if [ -n "${PROMPT_FILE:-}" ]; then
        if [ ! -f "$PROMPT_FILE" ]; then
            log "ERROR: PROMPT_FILE not found: ${PROMPT_FILE}"
            exit 1
        fi
        log "Reading prompt from ${PROMPT_FILE}"
        PROMPT="$(cat "$PROMPT_FILE")"
    elif [ -n "${PROMPT_TEXT:-}" ]; then
        log "Using inline prompt"
        PROMPT="$PROMPT_TEXT"
    else
        log "ERROR: no prompt provided (set PROMPT_TEXT or PROMPT_FILE)"
        exit 1
    fi
}

run_pi() {
    local extra=()
    if [ -n "${PI_EXTRA_ARGS:-}" ]; then
        # shellcheck disable=SC2206
        extra=($PI_EXTRA_ARGS)
    fi
    log "Running pi --model ${PI_MODEL}"
    # --mode json: emit the whole session as NDJSON to stdout -> trace.jsonl.
    # --no-session: ephemeral run. -a: trust the project so Pi runs tools
    # unconfined (Docker isolation is what keeps this safe).
    pi --mode json --no-session -a --model "$PI_MODEL" "${extra[@]}" "$PROMPT" \
        >"$TRACE_FILE"
    PI_EXIT=$?
    log "pi exited with ${PI_EXIT}"
}

extract_output() {
    node /extract-output.mjs "$TRACE_FILE" "$OUTPUT_FILE" || : >"$OUTPUT_FILE"
}

write_diff() {
    # Stage everything (incl. untracked files) and diff against the pinned base
    # so the patch is the complete record even if the agent committed its work.
    git add -A
    git diff --cached "$BASE_COMMIT" >"$DIFF_FILE"
}

log "Starting run ${RUN_ID:-unknown}"
setup_repo
BASE_COMMIT="$(git rev-parse HEAD)"
resolve_prompt
run_pi
extract_output
write_diff

exit "${PI_EXIT:-0}"
