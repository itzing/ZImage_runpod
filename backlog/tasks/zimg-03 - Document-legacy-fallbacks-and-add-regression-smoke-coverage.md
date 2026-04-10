---
id: ZIMG-03
title: Document legacy fallbacks and add regression smoke coverage for ZImage migration
status: Planned
assignee: []
created_date: '2026-04-10 19:30'
labels:
  - docs
  - testing
  - migration
dependencies:
  - ZIMG-01
  - ZIMG-02
documentation:
  - /var/lib/openclaw/.openclaw/workspace/projects/engui-endpoints/zimage-security-and-runtime-pattern.md
priority: medium
---

## Description

Document the new secure contract in the repo itself and add at least lightweight smoke coverage or reproducible manual fixtures for:
- secure text-only generation
- secure condition-image generation
- transport_result success path
- normalized transport_result failure path
- legacy fallback behavior during migration window

## Acceptance Criteria

- repo README or dedicated doc describes the migration-era contract
- manual or scripted smoke steps exist for secure and fallback flows
- known legacy fallback scope is explicit so it can be removed later
