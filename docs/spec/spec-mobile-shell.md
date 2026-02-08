# Spec: Mobile Shell Enforcement (V1)

## Background
Today, the 9:19.5 phone aspect ratio is enforced only in the web preview (PhoneFrame). Generation relies on prompts and does not guarantee a consistent mobile shell in the produced HTML. This spec introduces an automatic, code-level mobile shell insertion and validation step while keeping the 9:19.5 ratio as a preview-only reference.

## Goals
- Ensure every generated/refined HTML has a consistent mobile shell.
- Keep 9:19.5 as a preview reference only (do not lock runtime aspect ratio).
- Automatically repair missing viewport/meta/root container and base layout rules.
- Keep current preview UI and multi-page flow unchanged.

## Non-Goals
- Enforce a hard 9:19.5 aspect ratio in runtime HTML.
- Introduce new DB schema or migrations.
- Change front-end preview layout or navigation UI.

## Requirements
### Mobile Shell Requirements (Hard)
1) meta viewport: width=device-width, initial-scale=1, viewport-fit=cover
2) Root container: <div id="app" class="page"> wrapping all body content
3) Base layout rules:
   - max-width: 430px; width: 100%; margin: 0 auto;
   - min-height: 100dvh;
   - overflow-x: hidden;

### Compatibility
- Must be idempotent: running the shell injection multiple times does not duplicate content.
- Must tolerate minimal or malformed HTML (best-effort repair, fall back to original on hard failure).

## Design
### Mobile Shell Normalizer
Add `ensure_mobile_shell(html: str) -> str` in `packages/backend/app/generators/mobile_html.py`.

Behavior:
- Ensure `<meta name="viewport" ...>` exists and includes `viewport-fit=cover`.
- Ensure a root container exists: `#app.page` wrapping the body content.
- Inject a `<style id="mobile-shell">` block if missing; update it if present.
- Preserve existing user HTML; never overwrite content, only wrap/augment.

### Validation Extension
Extend `validate_mobile_html()` to check:
- viewport meta includes `viewport-fit=cover`
- root container `#app.page` exists
- `max-width: 430px`, `min-height: 100dvh`, `overflow-x: hidden` appear in CSS

Validation failures do not block generation; auto-repair is always attempted first.

### Injection Points
- `GenerationAgent`: after component assembly and before saving HTML.
- `RefinementAgent`: before saving refined HTML.

## Files and Changes
### Backend
- Add: `packages/backend/app/generators/mobile_html.py`
  - `ensure_mobile_shell()`
  - extend `validate_mobile_html()`
- Modify: `packages/backend/app/agents/generation.py`
  - call `ensure_mobile_shell()` before save
- Modify: `packages/backend/app/agents/refinement.py`
  - call `ensure_mobile_shell()` before save
- Modify: `packages/backend/app/agents/prompts.py`
  - clarify 9:19.5 is preview-only; runtime should remain responsive

### Frontend
- No change required. `PhoneFrame` keeps the 9:19.5 aspect ratio for preview.

## Test Plan
### New Tests
- `packages/backend/tests/test_mobile_html.py`
  - injects viewport/meta/root + CSS
  - idempotent behavior
  - preserves existing HTML content

### Updated Tests
- `packages/backend/tests/test_generation_agent.py`
  - ensure `#app.page` and viewport-fit=cover are present
- `packages/backend/tests/test_refinement_agent.py`
  - same checks for refined outputs

## Acceptance Criteria
- Every generated/refined HTML includes:
  - `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">`
  - `<div id="app" class="page">` wrapping body content
  - `max-width: 430px`, `min-height: 100dvh`, `overflow-x: hidden`
- Preview remains 9:19.5 in PhoneFrame.
- No change in multi-page routing or component registry behavior.

## Rollout
1) Add mobile shell normalizer + validation extensions.
2) Integrate injection into Generation/Refinement.
3) Update prompts and tests.
4) Verify with local generation and preview.
