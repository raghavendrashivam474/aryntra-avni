# ADR 0007: Post-V0 Review Hygiene and Logging Fixes

## Context
The V0 senior review identified three Must-Do items:
1. `__pycache__` directories committed to git.
2. No dependency manifest (`pyproject.toml` / `requirements.txt`).
3. No logging infrastructure in core synthesis paths.

Additionally, the async event loop handling in `EdgeTTSAdapter` was flagged as
over-engineered for V0's synchronous caller model.

## Decision
1. Updated `.gitignore` to exclude `__pycache__/`, `*.pyc`, virtual environments,
   build artifacts, and generated evaluation outputs.
2. Removed all `__pycache__` directories from git tracking via `git rm --cached`.
3. Created `pyproject.toml` (package definition) and `requirements.txt`
   (reproducible dev installs) with `edge-tts` pinned to the installed version.
4. Added Python `logging` to `VoiceCapability.synthesize()` (INFO on start/complete,
   ERROR on failure) and `EdgeTTSAdapter.render()` (DEBUG on entry/exit, ERROR on failure).
5. Simplified `EdgeTTSAdapter` async handling to a single `asyncio.run()` call,
   removing the `ThreadPoolExecutor` fallback path. Documented that the adapter
   is designed for synchronous callers.

## Consequences
- **Positive:** Clean git history, reproducible environments, basic observability.
- **Trade-off:** The simplified async path will raise `RuntimeError` if called from
  within an already-running event loop. This is acceptable for V0/V0.5. The
  multi-loop handling can be reintroduced when an async consumer requirement emerges.

## Status
Accepted