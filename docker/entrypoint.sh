#!/bin/bash
set -e

# Environment variables:
# - REPO_URL: Git repository URL or local path
# - REPO_COMMIT: Commit hash to checkout (optional)
# - PROMPT_FILE: Path to prompt file within repo
# - PROMPT_TEXT: Inline prompt text (alternative to PROMPT_FILE)
# - OPENCODE_MODEL: Model to use (optional)
# - OPENCODE_EXTRA_ARGS: Extra arguments for opencode (optional)
# - RUN_ID: Unique identifier for this run

LOG_FILE="/workspace/run.log"
METRICS_FILE="/workspace/metrics.json"

setup_repo() {
    if [[ "$REPO_URL" == http* ]] || [[ "$REPO_URL" == git@* ]]; then
        echo "Cloning repository: ${REPO_URL}" | tee -a "$LOG_FILE"
        git clone "$REPO_URL" /workspace/repo 2>&1 | tee -a "$LOG_FILE"
    else
        echo "Copying local repository from: ${REPO_URL}" | tee -a "$LOG_FILE"
        cp -r "$REPO_URL" /workspace/repo
    fi

    cd /workspace/repo

    # Deny question permission so agents don't hang waiting for input
    cat > opencode.json << 'OPENCODE_CONFIG'
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "question": "deny"
  }
}
OPENCODE_CONFIG

    if [ -n "$REPO_COMMIT" ]; then
        echo "Checking out commit: ${REPO_COMMIT}" | tee -a "$LOG_FILE"
        git checkout "$REPO_COMMIT" 2>&1 | tee -a "$LOG_FILE"
    fi
}

resolve_prompt() {
    if [ -n "$PROMPT_FILE" ]; then
        if [ -f "$PROMPT_FILE" ]; then
            echo "Reading prompt from file: ${PROMPT_FILE}" | tee -a "$LOG_FILE"
            PROMPT=$(cat "$PROMPT_FILE")
        else
            echo "ERROR: PROMPT_FILE specified but file not found: ${PROMPT_FILE}" | tee -a "$LOG_FILE"
            exit 1
        fi
    elif [ -n "$PROMPT_TEXT" ]; then
        echo "Using inline prompt" | tee -a "$LOG_FILE"
        PROMPT="$PROMPT_TEXT"
    else
        echo "ERROR: No prompt provided (set PROMPT_FILE or PROMPT_TEXT)" | tee -a "$LOG_FILE"
        exit 1
    fi
}

run_opencode() {
    local opencode_args=()
    if [ -n "$OPENCODE_MODEL" ]; then
        opencode_args+=(-m "$OPENCODE_MODEL")
    fi
    if [ -n "$OPENCODE_EXTRA_ARGS" ]; then
        # shellcheck disable=SC2206
        opencode_args+=($OPENCODE_EXTRA_ARGS)
    fi

    echo "Running: opencode run ${opencode_args[*]}" | tee -a "$LOG_FILE"
    START_TIME=$(date +%s)

    opencode run "$PROMPT" "${opencode_args[@]}" 2>&1 | tee -a "$LOG_FILE"
    EXIT_CODE=${PIPESTATUS[0]}

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
}

collect_metrics() {
    echo "Collecting metrics..." | tee -a "$LOG_FILE"

    echo "Exporting session data..." | tee -a "$LOG_FILE"
    local session_id
    session_id=$(opencode session list --format json -n 1 2>>"$LOG_FILE" | jq -r '.[0].id // empty')
    if [ -n "$session_id" ]; then
        opencode export "$session_id" > /workspace/opencode_session.json 2>>"$LOG_FILE" || true
    fi

    cat > "$METRICS_FILE" << EOF
{
    "run_id": "${RUN_ID}",
    "exit_code": ${EXIT_CODE},
    "duration_seconds": ${DURATION},
    "timestamp_start": "${START_TIME}",
    "timestamp_end": "${END_TIME}"
}
EOF
}

echo "Starting benchmark run: ${RUN_ID}" | tee "$LOG_FILE"
echo "Timestamp: $(date -Iseconds)" | tee -a "$LOG_FILE"

setup_repo
resolve_prompt
run_opencode
collect_metrics

echo "Run completed with exit code: ${EXIT_CODE}" | tee -a "$LOG_FILE"
echo "Duration: ${DURATION} seconds" | tee -a "$LOG_FILE"

exit $EXIT_CODE
