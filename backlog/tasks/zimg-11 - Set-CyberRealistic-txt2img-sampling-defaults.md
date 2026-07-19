# zimg-11 - Set CyberRealistic txt2img sampling defaults

## Summary
Update the text-only Z-Image workflow defaults to the recommended CyberRealistic sampling settings.

## Scope
- `workflow/z_image.json`

## Requirements
- Set the KSampler sampler to DPM++ 2S Ancestral.
- Set the KSampler scheduler to Beta.
- Set the AuraFlow sampling shift to `6`.
- Keep the default step count and CFG unchanged.
- Do not launch a live paid RunPod job without explicit approval.

## Acceptance Criteria
- Text-only generation uses `sampler_name: "dpmpp_2s_ancestral"`.
- Text-only generation uses `scheduler: "beta"`.
- Text-only generation uses `shift: 6`.
- Existing handler overrides for prompt, seed, steps, CFG, width, and height continue to work.

## Implementation Notes

<!-- SECTION:IMPLEMENTATION-NOTES:BEGIN -->
Implemented in the current Z-Image CyberRealistic sampling defaults change set. Verified with endpoint Python compile and JSON validation.
<!-- SECTION:IMPLEMENTATION-NOTES:END -->
