# ZIMG-05 - Import `re` for secure result filename builder

## Summary

`handler.py` uses `re.sub(...)` inside `build_secure_result_filename()` but does not import `re`, causing secure Z-Image jobs to fail with `NameError: name 're' is not defined` during result finalization.

## Scope

- Add the missing `import re` to `handler.py`
- Keep the fix minimal and regression-safe
- Validate with `python3 -m py_compile handler.py`

## Acceptance Criteria

- `handler.py` imports `re`
- `python3 -m py_compile handler.py` passes
- Secure Z-Image jobs no longer fail with `NameError: name 're' is not defined`
