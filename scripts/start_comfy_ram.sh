#!/usr/bin/env bash
set -euo pipefail

# Start ComfyUI with RAM-backed runtime directories to minimize disk footprint.
# Usage:
#   scripts/start_comfy_ram.sh [port]
# Example:
#   scripts/start_comfy_ram.sh 8188

PORT="${1:-8188}"
COMFY_ROOT="${COMFY_ROOT:-/ComfyUI}"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"

RUNTIME_ROOT="${RUNTIME_ROOT:-/dev/shm/comfy-runtime}"
INPUT_DIR="${INPUT_DIR:-$RUNTIME_ROOT/input}"
OUTPUT_DIR="${OUTPUT_DIR:-$RUNTIME_ROOT/output}"
TEMP_DIR="${TEMP_DIR:-$RUNTIME_ROOT/temp}"
USER_DIR="${USER_DIR:-$RUNTIME_ROOT/user}"

mkdir -p "$INPUT_DIR" "$OUTPUT_DIR" "$TEMP_DIR" "$USER_DIR"

# Optional: in-memory sqlite to avoid persistent DB traces
# Uncomment if needed:
# DB_URL="sqlite:///:memory:"

cd "$COMFY_ROOT"

exec "$PYTHON_BIN" main.py   --listen 0.0.0.0   --port "$PORT"   --input-directory "$INPUT_DIR"   --output-directory "$OUTPUT_DIR"   --temp-directory "$TEMP_DIR"   --user-directory "$USER_DIR"
