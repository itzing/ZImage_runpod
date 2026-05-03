# zimg-08 - Disable ComfyUI Manager registry network on startup

## Summary
Switch ComfyUI-Manager network mode from `private` to `offline` so the endpoint does not spend startup time fetching Comfy Registry metadata.

## Scope
- `config.ini` used by Docker image for ComfyUI-Manager
- Apply to both `zimage` and `zimage_mpm` branches

## Acceptance Criteria
- `network_mode = offline` in `config.ini`
- Change is committed and pushed in both target branches
