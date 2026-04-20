---
id: ZIMG-06
title: Support up to 4 dynamic LoRA nodes in z-image workflow
status: done
priority: high
labels: [z-image, lora, workflow, comfyui]
created_at: 2026-04-20
updated_at: 2026-04-20
completed_at: 2026-04-20
assignee: openclaw
---

## Summary
Extend the z-image RunPod endpoint to accept the existing multi-LoRA array contract and dynamically modify the LoRA workflow graph at runtime, supporting up to 4 LoRA nodes without requiring separate static workflow files.

## Desired outcome
- The endpoint accepts up to 4 LoRA entries from Engui.
- The handler dynamically chains `LoraLoaderModelOnly` nodes in the selected workflow before queueing it to ComfyUI.
- Single-LoRA and no-LoRA requests remain backward compatible.

## Acceptance criteria
- [x] Handler validates and normalizes incoming LoRA arrays
- [x] LoRA workflow graph is dynamically expanded to up to 4 chained nodes
- [x] Existing single-LoRA requests still work unchanged
- [x] Repo validation passes

## Completion notes
- added `normalize_lora_entries(...)` to validate and cap incoming LoRA entries to 4
- added `apply_dynamic_loras_to_workflow(...)` to rebuild the model path as `UNETLoader -> LoraLoaderModelOnly x N -> ModelSamplingAuraFlow`
- removed dependence on the static single-LoRA node payload wiring and now patch the workflow in memory before queueing
- validated handler syntax with `python3 -m py_compile handler.py`
