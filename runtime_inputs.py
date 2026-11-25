"""Private per-job staging inside ComfyUI's configured RAM input root."""
import os


def comfy_input_directory(task_id):
    if not task_id or os.path.basename(task_id) != task_id or task_id in (".", ".."):
        raise ValueError("Invalid task directory")
    root = os.path.realpath(os.path.join(os.getenv("RUNTIME_ROOT", "/dev/shm/comfy-runtime"), "input"))
    os.makedirs(root, exist_ok=True)
    path = os.path.join(root, task_id)
    # A fresh UUID directory must not already exist or be a symlink.
    os.mkdir(path, mode=0o700)
    return path
