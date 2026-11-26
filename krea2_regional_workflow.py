"""Headless regional Krea2 Turbo graph. No canvas or external segmentation."""
import copy
import hashlib
import math
from pathlib import Path
from PIL import Image

MAX_REGIONS = 4
MAX_LORAS = 8

def validate_regions(regional, width, height):
    if not isinstance(regional, dict) or set(regional) != {"regions"}:
        raise ValueError("Invalid regional configuration")
    regions = regional["regions"]
    if not isinstance(regions, list) or not 1 <= len(regions) <= MAX_REGIONS:
        raise ValueError("Supply 1..4 regions")
    for i, region in enumerate(regions):
        if not isinstance(region, dict) or set(region) != {"prompt", "loras", "mask_role", "mask_sha256"}:
            raise ValueError("Invalid region fields")
        if not isinstance(region["prompt"], str) or not region["prompt"].strip() or len(region["prompt"]) > 64000:
            raise ValueError("Region prompt is required (max 64000 characters)")
        if region["mask_role"] != f"region_mask_{i}":
            raise ValueError("Invalid region mask role")
        sha = region["mask_sha256"]
        if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError("Invalid region mask hash")
        entries = region["loras"]
        if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_LORAS:
            raise ValueError("Each region requires compatible LoRAs")
        for entry in entries:
            if not isinstance(entry, list) or len(entry) != 2 or not isinstance(entry[0], str) or not entry[0]:
                raise ValueError("Invalid regional LoRA")
            if isinstance(entry[1], bool) or not isinstance(entry[1], (int, float)) or not math.isfinite(entry[1]) or not -10 <= entry[1] <= 10:
                raise ValueError("Invalid regional LoRA weight")
    if sum(len(x["loras"]) for x in regions) > MAX_LORAS:
        raise ValueError("Too many regional LoRAs")
    if any(isinstance(v, bool) or not isinstance(v, int) or not 512 <= v <= 2048 or v % 64 for v in (width, height)):
        raise ValueError("Regional dimensions must be 512..2048 and multiples of 64")
    if width * height > 2097152:
        raise ValueError("Regional generation supports at most 2 megapixels")
    return regions

def prepare_regions(job_input, task_dir, width, height, decrypt_media, stage_loras):
    binding = job_input.get("__secure_binding")
    if not binding or not job_input.get("__regional_authenticated"):
        raise ValueError("Regional generation requires authenticated encrypted input")
    regions = validate_regions(job_input.get("regional"), width, height)
    if sum(len(r["loras"]) for r in regions) + len(job_input.get("lora") or []) > MAX_LORAS:
        raise ValueError("At most eight LoRA slots across base and regions")
    result = []
    for region in regions:
        role = region["mask_role"]
        matches = [d for d in job_input.get("media_inputs", []) if d.get("role") == role]
        if len(matches) != 1:
            raise ValueError("Each region requires exactly one encrypted mask")
        descriptor = matches[0]
        mb = descriptor.get("envelope", {}).get("binding", {})
        if any(mb.get(k) != binding.get(k) for k in ("job_id", "model_id", "attempt_id")) or mb.get("direction") != "engui_to_endpoint" or mb.get("role") != role or mb.get("kind") != "image":
            raise ValueError("Region mask binding does not match this generation")
        path = Path(task_dir) / (role + ".png")
        decrypt_media(descriptor, str(path))
        if hashlib.sha256(path.read_bytes()).hexdigest() != region["mask_sha256"]:
            raise ValueError("Region mask hash mismatch")
        with Image.open(path) as image:
            if image.size != (width, height):
                raise ValueError("Region mask dimensions do not match output")
            rgba = image.convert("RGBA")
            bands = rgba.split()
            if bands[3].getextrema() != (255, 255) or bands[0].tobytes() != bands[1].tobytes() or bands[0].tobytes() != bands[2].tobytes():
                raise ValueError("Region mask must be opaque grayscale")
            if bands[0].getextrema()[1] == 0:
                raise ValueError("Region mask is empty")
        result.append({"prompt": region["prompt"], "loras": stage_loras(region["loras"]), "mask_path": str(path)})
    return result

def configure_regional(graph, regions):
    """Preserve the existing Turbo sampler/schedule and optional global LoRAs."""
    graph = copy.deepcopy(graph)
    sampler = graph["3"]["inputs"]
    if float(sampler["cfg"]) != 1.0:
        raise ValueError("Krea2 Turbo regional generation requires CFG 1")
    previous = None
    for i, region in enumerate(regions):
        prefix = f"regional_{i}"
        graph[prefix + "_text"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": ["30", 0], "text": region["prompt"]}}
        graph[prefix + "_mask"] = {"class_type": "LoadImageMask", "inputs": {"image": region["mask_path"], "channel": "red"}}
        prior_lora = None
        for j, (name, weight) in enumerate(region["loras"]):
            key = prefix + f"_lora_{j}"
            inputs = {"lora_name": name, "strength": weight}
            if prior_lora: inputs["prev_loras"] = [prior_lora, 0]
            graph[key] = {"class_type": "Krea2LoRA", "inputs": inputs}
            prior_lora = key
        inputs = {"conditioning": [prefix + "_text", 0], "mask": [prefix + "_mask", 0], "loras": [prior_lora, 0]}
        if previous: inputs["prev_regions"] = [previous, 0]
        graph[prefix] = {"class_type": "Krea2RegionalPrompt", "inputs": inputs}
        previous = prefix
    graph["regional_apply"] = {"class_type": "Krea2ApplyRegional", "inputs": {
        "model": list(sampler["model"]), "conditioning": list(sampler["positive"]), "regions": [previous, 0],
        "restrict_img_attn": False, "exclusive_masks": True,
        "adaptive_masks": "off", "adaptive_steps": 2, "adaptive_threshold": 0.85,
        "base_loras_exclude_regions": False, "region_lock_strength": 0.0,
        "region_lock_start": 0.25, "region_lock_end": 0.7, "restrict_end_percent": 1.0,
        "dynamic_vram_mode": "regional safe", "unmaskable_layers": "skip",
    }}
    sampler["model"] = ["regional_apply", 0]
    sampler["positive"] = ["regional_apply", 1]
    graph["33"]["inputs"]["conditioning"] = ["regional_apply", 1]
    return graph
