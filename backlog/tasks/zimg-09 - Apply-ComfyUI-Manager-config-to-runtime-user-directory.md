# zimg-09 - Apply ComfyUI Manager config to runtime user directory

## Summary
The endpoint starts ComfyUI with `--user-directory /dev/shm/comfy-runtime/user`, so the baked image config at `/ComfyUI/user/default/ComfyUI-Manager/config.ini` is not used at runtime. Copy the config into the RAM-backed runtime user directory before starting ComfyUI.

## Scope
- `entrypoint.sh`
- Apply to both `zimage` and `zimage_mpm`

## Acceptance Criteria
- Runtime startup creates `$RUNTIME_ROOT/user/default/ComfyUI-Manager`
- Runtime startup copies `config.ini` into that directory before launching ComfyUI
- Change is committed and pushed in both branches
