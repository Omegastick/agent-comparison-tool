#!/bin/bash
set -e

cd /workspace/results

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

# Prevent OpenCode from hanging on interactive prompts
cat > opencode.json << 'OPENCODE_CONFIG'
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "question": "deny"
  }
}
OPENCODE_CONFIG

opencode run "$FULL_PROMPT" "${OPENCODE_ARGS[@]}"
