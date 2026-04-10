---
id: ZIMG-01
title: Adopt secure media_inputs and transport_request contract in ZImage worker
status: In Progress
assignee: []
created_date: '2026-04-10 19:30'
labels:
  - security
  - backend
  - runpod
  - migration
dependencies: []
documentation:
  - /var/lib/openclaw/.openclaw/workspace/projects/engui-endpoints/zimage-security-and-runtime-pattern.md
priority: high
---

## Description

Migrate `handler.py` from the legacy mixed input contract toward the Engui secure transport contract used by the new RunPod flow.

Primary goals:
- accept `media_inputs` descriptors for secure condition image delivery
- accept `transport_request.output_dir`
- keep legacy plaintext input fields only as compatibility fallback during migration
- avoid leaking secure payload details in logs

## Acceptance Criteria

- `condition_image` can be sourced from `media_inputs` when present
- secure media ciphertext is decrypted locally before workflow execution
- `transport_request.output_dir` is parsed and validated
- legacy `condition_image_*` fields still work as fallback
- logs remain redacted
