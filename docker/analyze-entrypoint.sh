#!/bin/bash
set -e

# Environment variables:
# - ANALYSIS_PROMPT: User-provided analysis prompt
# - OPENCODE_MODEL: Model to use for analysis

cd /workspace/results

# Build the full prompt from system prompt file and user prompt
FULL_PROMPT=""
if [ -f "/workspace/system-prompt.txt" ]; then
    SYSTEM_PROMPT=$(cat /workspace/system-prompt.txt)
    FULL_PROMPT="${SYSTEM_PROMPT}

## User Analysis Request

${ANALYSIS_PROMPT}"
else
    FULL_PROMPT="${ANALYSIS_PROMPT}"
fi

OPENCODE_ARGS=()
if [ -n "$OPENCODE_MODEL" ]; then
    OPENCODE_ARGS+=(-m "$OPENCODE_MODEL")
fi

# Run opencode - agent writes directly to /workspace/results/analysis.md
opencode run "$FULL_PROMPT" "${OPENCODE_ARGS[@]}"
