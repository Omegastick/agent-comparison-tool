#!/bin/bash
set -e

# Environment variables expected:
# - REPO_URL: Git repository URL or local path
# - REPO_COMMIT: Commit hash to checkout (optional)
# - PROMPT_FILE: Path to prompt file within repo
# - PROMPT_TEXT: Inline prompt text (alternative to PROMPT_FILE)
# - OPENCODE_AGENT: Agent to use (optional)
# - OPENCODE_MODEL: Model to use (optional)
# - OPENCODE_EXTRA_ARGS: Extra arguments for opencode (optional)
# - RUN_ID: Unique identifier for this run

LOG_FILE="/workspace/.benchmark/run.log"
METRICS_FILE="/workspace/.benchmark/metrics.json"

mkdir -p /workspace/.benchmark

echo "Starting benchmark run: ${RUN_ID}" | tee "$LOG_FILE"
echo "Timestamp: $(date -Iseconds)" | tee -a "$LOG_FILE"

# Clone or copy repository
if [[ "$REPO_URL" == http* ]] || [[ "$REPO_URL" == git@* ]]; then
    echo "Cloning repository: ${REPO_URL}" | tee -a "$LOG_FILE"
    git clone "$REPO_URL" /workspace/repo 2>&1 | tee -a "$LOG_FILE"
else
    echo "Copying local repository from: ${REPO_URL}" | tee -a "$LOG_FILE"
    cp -r "$REPO_URL" /workspace/repo
fi

cd /workspace/repo

# Checkout specific commit if provided
if [ -n "$REPO_COMMIT" ]; then
    echo "Checking out commit: ${REPO_COMMIT}" | tee -a "$LOG_FILE"
    git checkout "$REPO_COMMIT" 2>&1 | tee -a "$LOG_FILE"
fi

# Get the prompt
PROMPT=""
if [ -n "$PROMPT_FILE" ] && [ -f "$PROMPT_FILE" ]; then
    echo "Reading prompt from file: ${PROMPT_FILE}" | tee -a "$LOG_FILE"
    PROMPT=$(cat "$PROMPT_FILE")
elif [ -n "$PROMPT_TEXT" ]; then
    echo "Using inline prompt" | tee -a "$LOG_FILE"
    PROMPT="$PROMPT_TEXT"
else
    echo "ERROR: No prompt provided" | tee -a "$LOG_FILE"
    exit 1
fi

# Build opencode command
OPENCODE_CMD="opencode"
if [ -n "$OPENCODE_AGENT" ]; then
    OPENCODE_CMD="$OPENCODE_CMD --agent $OPENCODE_AGENT"
fi
if [ -n "$OPENCODE_MODEL" ]; then
    OPENCODE_CMD="$OPENCODE_CMD --model $OPENCODE_MODEL"
fi
if [ -n "$OPENCODE_EXTRA_ARGS" ]; then
    OPENCODE_CMD="$OPENCODE_CMD $OPENCODE_EXTRA_ARGS"
fi

# Run opencode
echo "Running: $OPENCODE_CMD" | tee -a "$LOG_FILE"
START_TIME=$(date +%s)

# Run opencode with the prompt, capture output
$OPENCODE_CMD --prompt "$PROMPT" --yes 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Collect metrics
echo "Collecting metrics..." | tee -a "$LOG_FILE"

# Check if there are commits
HAS_COMMITS=$(git log --oneline -1 2>/dev/null && echo "true" || echo "false")

# Get diff stats if there are changes
DIFF_STATS=""
if [ "$HAS_COMMITS" = "true" ]; then
    DIFF_STATS=$(git diff --stat HEAD~1 2>/dev/null || echo "")
fi

# Write metrics
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
