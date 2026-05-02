---
id: ZIMG-07
title: Remove z-image LoRA count cap outside UI
status: done
priority: high
labels: [z-image, lora, endpoint, comfyui]
created_at: 2026-05-02
updated_at: 2026-05-02
completed_at: 2026-05-02
assignee: openclaw
---

## Summary

Remove the remaining endpoint-side z-image LoRA count cap so the handler accepts and chains any number of incoming LoRA entries, while UI slot limits remain a separate concern in Engui.

## Desired outcome
- The endpoint no longer truncates incoming `lora` arrays to 4 entries.
- Dynamic LoRA chaining continues to work for arbitrary-length lists.
- Documentation reflects the removal of the hard cap.

## Acceptance criteria
- [x] `normalize_lora_entries(...)` no longer truncates to 4 entries
- [x] Dynamic workflow chaining iterates over the full validated list
- [x] README no longer claims a 3-entry cap
- [x] Repo validation passes
