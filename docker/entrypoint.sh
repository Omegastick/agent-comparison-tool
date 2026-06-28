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
#   trace.jsonl   Pi's full NDJSON action trace
#   output.txt    assistant text (omitted if extraction finds nothing)
#   diff.patch    git diff vs the pinned base commit, including untracked files
#   run-meta.json the exact pi invocation + version, for scaffold provenance
#
# Note: -e is intentionally NOT set. Pi may exit non-zero, but we still want to
# emit the artifacts and propagate Pi's exit code at the end.
set -uo pipefail

REPO_DIR="${HOME}/repo"
TRACE_FILE="/workspace/trace.jsonl"
OUTPUT_FILE="/workspace/output.txt"
DIFF_FILE="/workspace/diff.patch"
META_FILE="/workspace/run-meta.json"

PI_PID=""
PI_EXIT=""
BASE_COMMIT=""
FINALIZED=""

log() { echo "[act] $*" >&2; }

setup_repo() {
    # A prepared image (e.g. the debug image) ships the target repo already
    # checked out at the pinned commit, with its environment installed. Use it
    # in place and skip cloning. It is built root-owned but we run as a non-root
    # host user, so mark it a safe git directory before touching .git.
    if [ -n "${ACT_REPO_DIR:-}" ] && [ -d "${ACT_REPO_DIR}/.git" ]; then
        log "Using prepared repo at ${ACT_REPO_DIR} (skipping clone)"
        REPO_DIR="$ACT_REPO_DIR"
        cd "$REPO_DIR" || exit 1
        git config --global --add safe.directory "$REPO_DIR"
        # The image makes the tree world-writable for the non-root runtime user,
        # which flips every file's mode bit; ignore mode changes so the diff is
        # only the agent's content edits.
        git config core.fileMode false
        git config user.name "ACT Agent"
        git config user.email "act-agent@example.invalid"
        return
    fi

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
    #
    # Pi runs in the background so a SIGTERM (docker stop / timeout) is handled
    # promptly by the trap below instead of being deferred until a foreground pi
    # returns; we forward the signal to pi and then flush artifacts on exit.
    pi --mode json --no-session -a --model "$PI_MODEL" "${extra[@]}" "$PROMPT" \
        >"$TRACE_FILE" &
    PI_PID=$!
    wait "$PI_PID"
    PI_EXIT=$?
    log "pi exited with ${PI_EXIT}"
}

write_run_meta() {
    # Pi exposes no dump of its resolved system prompt / tool definitions, so the
    # "identical minimal scaffold across models" claim is made provable instead
    # from the pinned Pi version plus the byte-identical argv recorded here. The
    # prompt itself is the first user message in trace.jsonl.
    local pi_version
    pi_version="$(pi --version 2>/dev/null | head -n1)"
    RUN_ID="${RUN_ID:-}" PI_MODEL="${PI_MODEL:-}" \
    PI_EXTRA_ARGS="${PI_EXTRA_ARGS:-}" PI_VERSION="$pi_version" \
        node -e '
            const fs = require("node:fs");
            const argv = ["pi", "--mode", "json", "--no-session", "-a",
                "--model", process.env.PI_MODEL]
                .concat((process.env.PI_EXTRA_ARGS || "").split(" ").filter(Boolean));
            fs.writeFileSync(process.argv[1], JSON.stringify({
                run_id: process.env.RUN_ID || null,
                model: process.env.PI_MODEL || null,
                pi_version: process.env.PI_VERSION || null,
                pi_argv: argv,
                prompt: "see first user message in trace.jsonl",
                note: "Pi emits no system-prompt/tool-definition dump; scaffold reproducibility rests on the pinned Pi version and identical argv across models.",
            }, null, 2) + "\n");
        ' "$META_FILE" || log "WARN: failed to write run-meta.json"
}

extract_output() {
    # No `|| : >output.txt`: on extraction failure we leave output.txt absent and
    # let the extractor's stderr/non-zero exit be the clear marker. The full data
    # always survives in trace.jsonl.
    if [ ! -s "$TRACE_FILE" ]; then
        log "WARN: trace.jsonl is empty/missing; skipping output extraction"
        return
    fi
    if ! node /extract-output.mjs "$TRACE_FILE" "$OUTPUT_FILE"; then
        log "ERROR: output extraction failed; output.txt not written (trace.jsonl intact)"
    fi
}

write_diff() {
    # Only meaningful once the repo exists and we have a base to diff against;
    # the trap may fire before setup_repo finishes (e.g. SIGTERM during clone).
    if [ -z "$BASE_COMMIT" ] || [ ! -d "${REPO_DIR}/.git" ]; then
        log "WARN: repo not initialised; skipping diff"
        return
    fi
    cd "$REPO_DIR" || return
    # Stage everything against the pinned base so the patch is the complete record
    # even if the agent committed its work. -f forces in files the target repo's
    # .gitignore would otherwise drop, so agent-created ignored files still show.
    git add -Af
    git diff --cached "$BASE_COMMIT" >"$DIFF_FILE"
}

# Runs on every exit path -- normal completion, pi failure, or SIGTERM from
# docker stop / timeout -- so the artifacts always reflect whatever state exists.
# Guarded so it runs at most once.
finalize() {
    [ -n "$FINALIZED" ] && return
    FINALIZED=1
    write_run_meta
    write_diff
    extract_output
}

# On SIGTERM/SIGINT, forward to pi so it can flush its trace, then exit (which
# triggers the EXIT trap -> finalize). 143 = 128 + SIGTERM.
terminate() {
    log "Received termination signal; stopping pi (pid ${PI_PID:-none})"
    if [ -n "$PI_PID" ]; then
        kill -TERM "$PI_PID" 2>/dev/null
        wait "$PI_PID" 2>/dev/null
        PI_EXIT=$?
    fi
    exit 143
}

trap terminate TERM INT
trap finalize EXIT

log "Starting run ${RUN_ID:-unknown}"
setup_repo
BASE_COMMIT="$(git rev-parse HEAD)"
resolve_prompt
run_pi

exit "${PI_EXIT:-0}"
