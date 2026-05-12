# zimg-10 - Add Z-Image I2I workflow and handler mode

## Summary
Add a clean Z-Image image-to-image mode for Engui Create Image desktop. This should be based on the existing Z-Image text/LoRA workflow, not on the full Reddit workflow with QwenVL/SAM/rgthree nodes.

## Scope
- `workflow/z_image_i2i.json`
- `handler.py`
- endpoint request examples/docs as needed

## Requirements
- Create `workflow/z_image_i2i.json` using the current Z-Image model/CLIP/VAE stack.
- Add an init image path through `LoadImage -> VAEEncode -> KSampler.latent_image -> VAEDecode -> SaveImage`.
- Wire `denoise` into the I2I KSampler, defaulting to `0.35`.
- Reuse the existing dynamic LoRA chain; do not add rgthree LoRA nodes.
- Support endpoint mode aliases:
  - `mode: "i2i"`
  - `task: "i2i"`
  - `task_type: "image_to_image"`
- Ensure I2I workflow selection is distinct from Control workflow selection.
- Use the existing secure media input flow for the init image.
- Keep sensitive prompt, negative prompt, and LoRA fields inside the existing secure contract.

## Acceptance Criteria
- Handler selects `workflow/z_image_i2i.json` for all supported I2I aliases.
- Missing init image returns a clear error for I2I.
- I2I does not select `z_image_control.json` just because an image is present.
- Dynamic LoRA support works with I2I.
- `denoise` is applied to the sampler.
- Existing text-only, LoRA, Control, and OpenPose extract modes remain unchanged.
- No live paid RunPod job is launched without explicit approval.

## Reference
See Engui plan: `/home/engui/Engui_Studio/docs/z-image-i2i-create-image-implementation-plan.md`.

## Implementation Notes

<!-- SECTION:IMPLEMENTATION-NOTES:BEGIN -->
Implemented in the current Z-Image I2I change set. Verified with endpoint Python compile/workflow structural check, Engui targeted lint, production build, and Engui service restart.
<!-- SECTION:IMPLEMENTATION-NOTES:END -->
