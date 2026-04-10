# ZImage secure migration contract

This document describes the migration-era contract between Engui Studio and `ZImage_runpod-zimage`.

It is intentionally focused on the current secure RunPod migration, not on a generic future platform.

## Goal

Make ZImage compatible with the new Engui secure supervisor flow:
- Engui sends a structured secure payload instead of plaintext sensitive fields
- Engui may send secure media through `media_inputs`
- the worker writes the final encrypted artifact into the shared secure transport namespace
- the worker returns `transport_result`
- Engui finalizes the local plaintext result on the server side

## Current migration status

Implemented in `handler.py`:
- accepts new structured `_secure` envelope
- still accepts legacy `_secure` envelope for compatibility during migration
- accepts `media_inputs` for secure condition image delivery
- accepts `transport_request.output_dir`
- returns `transport_result` for the new secure path
- preserves legacy plaintext/fallback request paths for now

Not yet removed:
- legacy `condition_image`, `condition_image_path`, `condition_image_url`, `condition_image_base64`
- legacy endpoint-specific result path `image_encrypted`

## Request contract

### Plaintext fields that may remain outside `_secure`

These are routing or low-risk generation controls:
- `seed`
- `steps`
- `cfg`
- `width`
- `height`
- optional control fields like `canny_low_threshold`, `canny_high_threshold`, `controlnet_strength`
- `return_url`
- `transport_request`
- `media_inputs`

### Structured secure payload

Sensitive text-like fields should arrive inside `_secure`.

Expected shape:

```json
{
  "_secure": {
    "v": 1,
    "wrapped_key": "v1:<base64>",
    "nonce": "<base64>",
    "ciphertext": "<base64>",
    "binding": {
      "job_id": "job_123",
      "model_id": "z-image",
      "attempt_id": "attempt_123",
      "direction": "engui_to_endpoint"
    }
  }
}
```

Expected decrypted plaintext fields currently supported by the worker:
- `prompt`
- `positive_prompt`
- `negative_prompt`
- `negativePrompt`
- `lora`
- legacy compatibility: `lora_names`

### Secure media input contract

Condition image may be sent through `media_inputs`.

Expected descriptor shape:

```json
{
  "role": "condition_image",
  "kind": "image",
  "mime": "image/png",
  "storage_path": "/runpod-volume/secure-jobs/job_123/attempt_123/inputs/condition_image.bin",
  "envelope": {
    "v": 1,
    "wrapped_key": "v1:<base64>",
    "nonce": "<base64>",
    "binding": {
      "job_id": "job_123",
      "model_id": "z-image",
      "attempt_id": "attempt_123",
      "direction": "engui_to_endpoint",
      "role": "condition_image",
      "kind": "image"
    }
  }
}
```

Currently accepted roles for condition-image handling:
- `condition_image`
- `source_image`

### Secure transport request contract

Engui may request endpoint-side secure output materialization by sending:

```json
{
  "transport_request": {
    "output_dir": "/runpod-volume/secure-jobs/job_123/attempt_123/outputs/"
  }
}
```

Rules:
- `output_dir` must be under `/runpod-volume/`
- endpoint writes encrypted result artifact inside this directory
- current worker writes `result.bin`

## Response contract

### Success on secure path

The preferred secure response is:

```json
{
  "transport_result": {
    "status": "completed",
    "result_media": {
      "kind": "image",
      "mime": "image/png",
      "storage_path": "/runpod-volume/secure-jobs/job_123/attempt_123/outputs/result.bin",
      "envelope": {
        "v": 1,
        "wrapped_key": "v1:<base64>",
        "nonce": "<base64>",
        "binding": {
          "job_id": "job_123",
          "model_id": "z-image",
          "attempt_id": "attempt_123",
          "direction": "endpoint_to_engui",
          "role": "result",
          "kind": "image"
        }
      }
    }
  }
}
```

Optional companion field still allowed during migration:
- `image_url`

### Failed secure transport path

If the endpoint cannot materialize the encrypted transport result, it should return:

```json
{
  "transport_result": {
    "status": "failed",
    "error": {
      "code": "TRANSPORT_RESULT_WRITE_FAILED",
      "message": "..."
    }
  }
}
```

### Legacy compatibility response

During migration, the worker may still return:

```json
{
  "image_encrypted": {
    "v": 1,
    "alg": "AES-256-GCM",
    "kid": "zimage-k1",
    "nonce": "<base64>",
    "ciphertext": "<base64>",
    "mime": "image/png"
  }
}
```

This is a compatibility fallback, not the target final contract.

## Legacy fallback scope

Still supported temporarily:
- legacy `_secure` AES-GCM payload without wrapped DEK binding structure
- plaintext condition-image fields
- legacy `image_encrypted` result path

Should be removable after Engui and deployed endpoint are both fully on the supervisor-driven secure flow.

## Smoke-check focus before real integration run

Before a real end-to-end run, verify:
- structured `_secure` shape matches what Engui now sends
- `media_inputs` descriptor shape matches Engui secure transport helpers
- `transport_request.output_dir` is accepted and validated
- successful secure response returns `transport_result.status = "completed"`
- transport failure returns normalized `transport_result.status = "failed"`
- legacy fallback behavior remains explicit and temporary
