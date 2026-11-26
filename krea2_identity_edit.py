"""Trusted single-reference Krea2 Identity Edit graph. No GPU/runtime imports.

Node contract: lbouaraba/comfyui-krea2edit, pinned in Dockerfile.
Uses the v1.2 identity adapter and the same conditioning as Dataset Studio.
"""
import math

IDENTITY_LORA = "krea/krea2_identity_edit_v1_2.safetensors"
IDENTITY_VERSION = "krea2-identity-v1.2"


def _number(value, name, lower, upper, integer=False):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not lower <= number <= upper or (integer and number != int(number)):
        raise ValueError(f"{name} is out of range")
    return int(number) if integer else number


def build_identity_edit(*, image_path, prompt, seed, width, height, steps=8,
                        ref_boost=0.25, grounding_px=512, identity_strength=1.0,
                        generation_loras=None):
    if not isinstance(image_path, str) or not image_path:
        raise ValueError("Identity Edit requires a source image")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 64000:
        raise ValueError("Identity Edit requires a non-empty instruction")
    width = _number(width, "width", 512, 2048, True)
    height = _number(height, "height", 512, 2048, True)
    if width % 64 or height % 64 or width * height > 2 * 1024 * 1024:
        raise ValueError("Identity Edit dimensions must be multiples of 64 and at most 2 MP")
    seed = _number(seed, "seed", 0, 2147483647, True)
    steps = _number(steps, "steps", 1, 50, True)
    ref_boost = _number(ref_boost, "ref_boost", 0, 10)
    grounding_px = _number(grounding_px, "grounding_px", 512, 1536, True)
    identity_strength = _number(identity_strength, "identity_strength", 0, 1.5)
    if len(generation_loras or []) > 8:
        raise ValueError("At most eight additional LoRAs are supported")
    graph = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "krea2_turbo_fp8_scaled.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "4": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": IDENTITY_LORA, "strength_model": identity_strength}},
        "5": {"class_type": "LoadImage", "inputs": {"image": image_path}},
        "6": {"class_type": "VAEEncode", "inputs": {"pixels": ["5", 0], "vae": ["3", 0]}},
        "7": {"class_type": "Krea2EditModelPatch", "inputs": {
            "model": ["4", 0], "source_latent": ["6", 0],
            "vae": ["3", 0], "source_image": ["5", 0],
            "target_latent": ["10", 0], "fit_mode": "fit",
            "ref_boost": ref_boost, "ref_boost_a": 1.0}},
        "8": {"class_type": "Krea2EditGroundedEncode", "inputs": {
            "clip": ["2", 0], "prompt": prompt, "image": ["5", 0], "grounding_px": grounding_px}},
        "9": {"class_type": "Krea2EditGroundedEncode", "inputs": {
            "clip": ["2", 0], "prompt": "", "image": ["5", 0], "grounding_px": grounding_px}},
        "10": {"class_type": "EmptySD3LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "11": {"class_type": "KSampler", "inputs": {
            "model": ["7", 0], "positive": ["8", 0], "negative": ["9", 0],
            "latent_image": ["10", 0], "seed": seed, "steps": steps,
            "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": "krea_identity"}},
    }
    previous = "4"
    for index, (name, weight) in enumerate(generation_loras or []):
        if not isinstance(name, str) or not name:
            raise ValueError("Additional LoRA name is required")
        if name.rsplit("/", 1)[-1] == IDENTITY_LORA.rsplit("/", 1)[-1]:
            raise ValueError("The baked identity adapter cannot be added twice")
        key = f"identity_extra_{index}"
        graph[key] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": [previous, 0], "lora_name": name,
            "strength_model": _number(weight, "LoRA strength", -10, 10)}}
        previous = key
    graph["7"]["inputs"]["model"] = [previous, 0]
    return graph
