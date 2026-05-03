#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Start ComfyUI in the background (RAM mode)
echo "Starting ComfyUI in RAM mode..."
RUNTIME_ROOT=${RUNTIME_ROOT:-/dev/shm/comfy-runtime}
mkdir -p "$RUNTIME_ROOT/input" "$RUNTIME_ROOT/output" "$RUNTIME_ROOT/temp" "$RUNTIME_ROOT/user/default/ComfyUI-Manager"
cp /ComfyUI/user/default/ComfyUI-Manager/config.ini "$RUNTIME_ROOT/user/default/ComfyUI-Manager/config.ini"
python /ComfyUI/main.py --listen --use-sage-attention \
  --input-directory "$RUNTIME_ROOT/input" \
  --output-directory "$RUNTIME_ROOT/output" \
  --temp-directory "$RUNTIME_ROOT/temp" \
  --user-directory "$RUNTIME_ROOT/user" &

# Wait for ComfyUI to be ready
echo "Waiting for ComfyUI to be ready..."
max_wait=120  # 최대 2분 대기
wait_count=0
while [ $wait_count -lt $max_wait ]; do
    if curl -s http://127.0.0.1:8188/ > /dev/null 2>&1; then
        echo "ComfyUI is ready!"
        break
    fi
    echo "Waiting for ComfyUI... ($wait_count/$max_wait)"
    sleep 2
    wait_count=$((wait_count + 2))
done

if [ $wait_count -ge $max_wait ]; then
    echo "Error: ComfyUI failed to start within $max_wait seconds"
    exit 1
fi

# Start the handler in the foreground
# 이 스크립트가 컨테이너의 메인 프로세스가 됩니다.
echo "Starting the handler..."
exec python handler.py