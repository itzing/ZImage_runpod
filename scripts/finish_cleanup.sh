#!/usr/bin/env bash
set -euo pipefail

# Cleanup script to run after each job.
# Removes Comfy history entries and clears runtime directories.
#
# Usage:
#   scripts/finish_cleanup.sh <prompt_id>
#
# Env vars:
#   COMFY_BASE_URL  default: http://127.0.0.1:8188
#   RUNTIME_ROOT    default: /dev/shm/comfy-runtime
#   INPUT_DIR       default: $RUNTIME_ROOT/input
#   OUTPUT_DIR      default: $RUNTIME_ROOT/output
#   TEMP_DIR        default: $RUNTIME_ROOT/temp

PROMPT_ID="${1:-}"
COMFY_BASE_URL="${COMFY_BASE_URL:-http://127.0.0.1:8188}"

RUNTIME_ROOT="${RUNTIME_ROOT:-/dev/shm/comfy-runtime}"
INPUT_DIR="${INPUT_DIR:-$RUNTIME_ROOT/input}"
OUTPUT_DIR="${OUTPUT_DIR:-$RUNTIME_ROOT/output}"
TEMP_DIR="${TEMP_DIR:-$RUNTIME_ROOT/temp}"

post_json() {
  local endpoint="$1"
  local payload="$2"
  curl -fsS -X POST "$COMFY_BASE_URL/$endpoint"     -H 'Content-Type: application/json'     --data "$payload" >/dev/null || true
}

# 1) Remove history for this prompt (or clear all if prompt_id not provided)
if [[ -n "$PROMPT_ID" ]]; then
  post_json "history" "{"delete":["$PROMPT_ID"]}"
else
  post_json "history" '{"clear":true}'
fi

# 2) Clear runtime dirs
for dir in "$INPUT_DIR" "$OUTPUT_DIR" "$TEMP_DIR"; do
  if [[ -d "$dir" ]]; then
    find "$dir" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
  fi
done

# 3) Optional: ask Comfy to free memory / unload models
post_json "free" '{"free_memory":true,"unload_models":true}'
