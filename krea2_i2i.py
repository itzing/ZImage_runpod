"""Krea2-only init-image graph configuration; no model downloads or GPU imports."""
import math

def configure_i2i(graph, *, image_path, prompt, seed, steps, cfg, width, height, denoise, negative_prompt=""):
    if not image_path:
        raise ValueError("Krea2 i2i requires an init image.")
    if not math.isfinite(float(denoise)) or not 0 <= float(denoise) <= 1:
        raise ValueError("denoise must be a finite number in [0, 1].")
    graph["61"]["inputs"]["image"] = image_path
    graph["63"]["inputs"].update(width=width, height=height)
    graph["27"]["inputs"]["text"] = prompt
    graph["3"]["inputs"].update(seed=seed, steps=steps, cfg=cfg, denoise=float(denoise))
    if negative_prompt:
        graph["34"] = {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["30", 0]}}
        graph["3"]["inputs"]["negative"] = ["34", 0]
    return graph
