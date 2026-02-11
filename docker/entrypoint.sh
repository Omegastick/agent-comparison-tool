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

LOG_FILE="/workspace/.benchmark/run.log"
METRICS_FILE="/workspace/.benchmark/metrics.json"

mkdir -p -m 755 /workspace/.benchmark

echo "Starting benchmark run: ${RUN_ID}" | tee "$LOG_FILE"
echo "Timestamp: $(date -Iseconds)" | tee -a "$LOG_FILE"

if [[ "$REPO_URL" == http* ]] || [[ "$REPO_URL" == git@* ]]; then
    echo "Cloning repository: ${REPO_URL}" | tee -a "$LOG_FILE"
    git clone "$REPO_URL" /workspace/repo 2>&1 | tee -a "$LOG_FILE"
else
    echo "Copying local repository from: ${REPO_URL}" | tee -a "$LOG_FILE"
    cp -r "$REPO_URL" /workspace/repo
fi

cd /workspace/repo

if [ -n "$REPO_COMMIT" ]; then
    echo "Checking out commit: ${REPO_COMMIT}" | tee -a "$LOG_FILE"
    git checkout "$REPO_COMMIT" 2>&1 | tee -a "$LOG_FILE"
fi

PROMPT=""
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

OPENCODE_ARGS=()
if [ -n "$OPENCODE_MODEL" ]; then
    OPENCODE_ARGS+=(-m "$OPENCODE_MODEL")
fi
if [ -n "$OPENCODE_EXTRA_ARGS" ]; then
    # shellcheck disable=SC2206
    OPENCODE_ARGS+=($OPENCODE_EXTRA_ARGS)
fi

echo "Running: opencode run ${OPENCODE_ARGS[*]}" | tee -a "$LOG_FILE"
START_TIME=$(date +%s)

opencode run "$PROMPT" "${OPENCODE_ARGS[@]}" 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "Collecting metrics..." | tee -a "$LOG_FILE"

HAS_COMMITS="false"
COMMIT_COUNT=$(git rev-list --count HEAD 2>/dev/null || echo "0")
if [ "$COMMIT_COUNT" -gt 0 ]; then
    HAS_COMMITS="true"
fi

cat > "$METRICS_FILE" << EOF
{
    "run_id": "${RUN_ID}",
    "exit_code": ${EXIT_CODE},
    "duration_seconds": ${DURATION},
    "has_commits": ${HAS_COMMITS},
    "timestamp_start": "${START_TIME}",
    "timestamp_end": "${END_TIME}"
}
EOF

echo "Run completed with exit code: ${EXIT_CODE}" | tee -a "$LOG_FILE"
echo "Duration: ${DURATION} seconds" | tee -a "$LOG_FILE"

exit $EXIT_CODE
