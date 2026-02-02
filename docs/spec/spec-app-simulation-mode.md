# Spec: App Simulation Mode (Preview)

## Summary
Introduce an "App Simulation Mode" in the Preview panel so users can:
- Navigate across pages inside a project (multi-page flows).
- Carry UI state across pages (e.g., cart items, form values, task inputs).

This mode targets "feel the app flow" without building a real backend.

## Goals
- Internal navigation works within the preview iframe.
- State persists across page switches in the same session.
- Minimal developer effort; no changes to generated HTML required.
- Safe in a sandboxed iframe.

## Non-Goals
- Full SPA routing or real backend data.
- Perfect semantic state (we only capture generic inputs).
- Persist state across devices or users.

## User Experience
- Add a toggle in the Preview header: **App Mode**.
- When enabled:
  - Clicking internal links switches pages inside the project.
  - Input values persist as the user moves across pages.
  - A simple global API is available in the page runtime:
    - `window.IC_APP.getState()`
    - `window.IC_APP.setState(key, value | object)`
    - `window.IC_APP.navigate(slug)`
- When disabled, preview behaves as it does today.

## State Model
- State is a flat key-value object.
- Keys are derived in this order:
  1) `data-ic-key`
  2) `name`
  3) `id`
- Tracked fields:
  - `input`, `select`, `textarea`
  - `checkbox` stores boolean
  - `radio` stores selected value
  - `select[multiple]` stores array of values
- Stored per session in localStorage:
  - `instant-coffee:app-state:{sessionId}`

## Navigation Behavior
- The runtime intercepts internal anchors:
  - `index.html`, `pages/{slug}.html`
  - Relative paths without scheme
- It posts a navigation event to the parent.
- Parent resolves slug -> pageId and switches preview.

## Technical Design
### Frontend (Preview)
- Preview iframe receives an injected runtime script when App Mode is on.
- Runtime posts and receives messages using `postMessage`.
- Parent maintains `appState` in React and persists to localStorage.
- Parent pushes state to the iframe on load or when App Mode is enabled.

### Message Protocol (postMessage)
- From iframe to parent:
  - `{ source: 'ic-app-mode', type: 'ic_ready' }`
  - `{ source: 'ic-app-mode', type: 'ic_nav', slug }`
  - `{ source: 'ic-app-mode', type: 'ic_state', state }`
- From parent to iframe:
  - `{ source: 'ic-app-mode', type: 'ic_state_init', state }`

## Open Questions
- Should App Mode be enabled by default for multi-page projects?
- Should there be a "Reset State" button in the Preview panel?
- Do we need to persist state on the backend instead of localStorage?

## Risks / Limitations
- Some UI state (custom JS widgets) may not map to simple input values.
- If a page dynamically renders inputs after load, the state sync relies on change events.
- If HTML uses unsupported navigation patterns, the runtime may not intercept.
