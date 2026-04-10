---
id: ZIMG-02
title: Return transport_result for secure finalization in ZImage worker
status: Planned
assignee: []
created_date: '2026-04-10 19:30'
labels:
  - security
  - backend
  - runpod
  - migration
dependencies:
  - ZIMG-01
documentation:
  - /var/lib/openclaw/.openclaw/workspace/projects/engui-endpoints/zimage-security-and-runtime-pattern.md
priority: high
---

## Description

Replace the endpoint-specific `image_encrypted` response as the primary secure result path with supervisor-friendly `transport_result` output.

Primary goals:
- encrypt generated image bytes into a transport artifact bound to job/model/attempt
- write the encrypted artifact under the secure output directory
- return a normalized `transport_result` block that Engui can finalize server-side
- keep legacy `image_encrypted` fallback only if still needed for compatibility during rollout

## Acceptance Criteria

- successful secure jobs return `transport_result.status = "completed"`
- result media includes `kind`, `mime`, `storage_path`, and `envelope`
- failed secure transport returns `transport_result.status = "failed"` with normalized error
- Engui `generate/status` can consume the result without endpoint-specific decryption logic
