# Live/Build Preview Mode Plan

## Summary

This plan adds a clearer split between the preview workbench's two modes:

- **Live mode** becomes a multi-page map. Every generated page is rendered in its own iframe, interactions inside those iframes are blocked, and each page frame has a centered page-name label below it.
- **Build mode** remains the complete app preview. It uses one iframe for the generated build output, so routing, buttons, forms, and app state behave like the final app.
- In **Live mode**, clicking a page-name label inserts that page into the chat input as a page reference using the existing `@slug ` mention format.
- In **Live mode**, internal navigation links get thick colored dashed connector lines from the link/button location to the destination page iframe.

The first implementation should stay frontend-only. Existing backend page preview and build preview endpoints already provide the URLs needed for both modes.

## Current State

The preview surface is centered around `packages/web/src/components/custom/PreviewPanel.tsx`.

- `ProjectPage` owns `previewMode`, currently `'live' | 'build'`.
- `PreviewPanel` currently renders a single `PhoneFrame` and a single iframe.
- Live mode injects `appModeRuntime` into the selected page preview. That runtime intercepts internal links and posts navigation events to the parent, where `PreviewPanel` switches the selected page.
- Build mode uses `buildPreviewUrl`, which points at `/preview/{sessionId}/...`, and renders the compiled app output in one iframe.
- Page mentions already exist in chat input through `@slug` parsing and `useMentionState`, but insertion is currently driven by typing or selecting from the mention popover.

The new behavior should preserve build mode and replace live mode's single selected-page preview only when multiple pages exist.

## Desired Behavior

### Live Mode

When the project has multiple pages:

- Render all pages at once.
- Each page appears in its own phone-sized iframe.
- The iframe content is visible but non-interactive.
- A page-name button is centered below each iframe frame.
- Clicking the page-name button inserts `@{page.slug} ` into the chat input.
- Internal navigation links are visually connected to their target page by dashed lines.
- Dashed lines should be thick, visually legible, and color-distinct per link.
- Clicking buttons or links inside any iframe should not trigger navigation, form submission, or state changes.

When the project has zero or one page:

- Preserve the current single-frame live preview behavior unless the implementation can safely use the same multi-page renderer for one page without regressing existing tests.

### Build Mode

- Render exactly one iframe for the whole generated app.
- Use the existing build preview URL.
- Keep app interactions intact.
- Do not render the live mode page grid.
- Do not render the live mode dashed connector overlay.
- Do not block iframe interactions.

### Chat Reference Insertion

- Clicking a live page label inserts a page mention into the chat input.
- If the textarea is focused, insert at the current cursor or replace the active selection.
- If the textarea is not focused, append the mention to the end of the current draft with sensible spacing, then focus the textarea.
- Use the existing mention syntax: `@slug `.
- Do not send the message automatically.
- Do not open the mention popover after insertion.

## Implementation Plan

### 1. Add a Live Multi-Page Preview Renderer

Add a dedicated live-mode rendering path under `PreviewPanel`.

Recommended structure:

- Keep the existing single iframe rendering path for build mode and fallback cases.
- Add a small internal component such as `LivePageMap` inside `PreviewPanel.tsx`, or split it into a new file if the component becomes large.
- Pass `pages`, `buildPagePreviewUrl`-equivalent page preview URLs, and page mention callbacks into this renderer.

Rendering details:

- Use the existing `PhoneFrame` component for each page so scale and visual language stay consistent.
- Render the page grid in a scrollable area inside the preview panel.
- Use stable `data-testid` values for tests:
  - `live-page-map`
  - `live-page-frame`
  - `live-page-iframe`
  - `live-page-label`
  - `live-link-overlay`
  - `live-link-connector`
- Each iframe should load from the page preview endpoint:
  - `api.pages.previewUrl(page.id)`
  - add a cache-busting query only for explicit refresh flows.

Interaction blocking:

- Place an absolute transparent layer above each live iframe.
- The layer should cover the iframe content but not cover the page label below the frame.
- This makes iframe content visible while ensuring internal buttons and links cannot be clicked.

Layout:

- Prefer a responsive grid:
  - one column on narrow viewports;
  - two or more columns as space allows;
  - stable frame widths so connector measurement is predictable.
- The live map container must be `position: relative` so the connector SVG can be absolutely positioned over the grid.

### 2. Draw Dashed Link Connectors

Add an overlay SVG above the live page map.

Data model:

```ts
interface LiveLinkConnector {
  id: string
  sourcePageId: string
  targetPageId: string
  color: string
  x1: number
  y1: number
  x2: number
  y2: number
}
```

Measurement flow:

- Store refs for each page card and iframe.
- On each iframe `load`, inspect its same-origin document.
- Query internal links with `document.querySelectorAll('a[href]')`.
- Resolve each link target to a page slug using the same normalization rules as `appModeRuntime`:
  - ignore external URLs;
  - ignore hash-only links;
  - strip query/hash;
  - normalize `index`, `index.html`, `/index.html` to `index`;
  - normalize `pages/{slug}/index.html` and `{slug}.html` to `{slug}`;
  - ignore unsupported nested paths unless they map directly to a known page slug.
- Match the normalized slug to `pages`.
- Compute source coordinates from the link element's bounding rect inside the iframe and translate them into live map coordinates:
  - iframe viewport rect in parent page;
  - link rect inside iframe document;
  - account for iframe scroll position.
- Compute target coordinates from the destination page card/frame rect, preferably the top or center of the destination frame.
- Save connector lines in state.

Update triggers:

- iframe load;
- page list changes;
- preview mode changes back to live;
- container resize via `ResizeObserver`;
- live map scroll;
- window resize.

Styling:

- `strokeWidth`: around `5` or `6`.
- `strokeDasharray`: e.g. `10 8`.
- `strokeLinecap`: `round`.
- Use a fixed palette with enough contrast on light muted backgrounds.
- Assign colors stably from `sourcePageId + href + index`.
- Put the SVG above the iframes visually but set `pointer-events: none`.

Failure handling:

- If iframe content cannot be read, skip connectors for that iframe.
- If a link target cannot be matched to a known page, skip it.
- If a link element is hidden or has a zero-size rect, skip it.
- If two links overlap, drawing both is acceptable for v1.

### 3. Keep Build Mode Single-Iframe and Fully Interactive

Build mode should continue to use the existing branch:

- `previewMode === 'build'`
- `currentUrl = buildPreviewUrl`
- one iframe with `data-testid="preview-iframe"`
- no live overlay
- no page grid
- no interaction blocker

Do not inject live connector logic into build mode.

The current build placeholder behavior should stay:

- show build progress while build is active;
- show "Build output not available" when build preview is missing and no build is active.

### 4. Wire Page Labels to Chat Input

Add an imperative insertion API to `ChatInput`.

Recommended approach:

- Convert `ChatInput` to `React.forwardRef`.
- Expose a handle:

```ts
export interface ChatInputHandle {
  insertPageMention: (page: Page) => void
}
```

- Implement insertion inside `ChatInput` so it can use local `message`, `textareaRef`, and `closeMention`.
- Insert `@${page.slug} ` at the active selection/cursor when possible.
- If there is no active cursor, append to the current message with a leading space only when needed.
- Focus the textarea after insertion.

Prop flow:

- `ChatPanel` owns `const chatInputRef = React.useRef<ChatInputHandle>(null)`.
- `ChatPanel` exposes an `onMentionPage` callback or registers itself upward through `ProjectPage`.
- `ProjectPage` passes a single `handleMentionPage(page)` down to `WorkbenchPanel`.
- `WorkbenchPanel` passes it to `PreviewPanel`.
- `PreviewPanel` passes it to the live page map page-label buttons.

Keep this frontend-only:

- Sending still uses existing `parsePageMentions`.
- No backend schema changes are required.
- No changes are needed in chat streaming or run APIs.

### 5. Refresh and Selection Behavior

Live mode:

- Page grid should not require a selected page.
- Existing selected page state can still be updated when the user clicks a page frame/label if that is useful, but mention insertion must be the primary label action.
- The existing `PageSelector` can be hidden in multi-page live mode because all pages are visible.

Build mode:

- Continue using `selectedBuildPage` and build page selection behavior.
- The current build page path selection should not be affected by the live page grid.

Refresh:

- In live mode, the global refresh button should refresh all live iframes, or at minimum reload the visible live map by changing a cache-busting stamp used by all page preview URLs.
- In build mode, keep the existing build preview refresh behavior.

## Public Interfaces and Types

Expected frontend additions:

```ts
export interface ChatInputHandle {
  insertPageMention: (page: Page) => void
}
```

Expected prop additions:

```ts
interface ChatPanelProps {
  inputRef?: React.Ref<ChatInputHandle>
}

interface WorkbenchPanelProps {
  onMentionPage?: (page: PageInfo) => void
}

interface PreviewPanelProps {
  onMentionPage?: (page: PageInfo) => void
}
```

If `PageInfo` does not include everything needed for chat mention insertion, expand it minimally to include `id`, `title`, and `slug`. Avoid introducing a new page reference type unless it materially reduces duplication.

No backend API, database, or SSE event type changes are required.

## Test Plan

Run these checks after implementation:

```bash
cd packages/web
npm run lint
npm run build
npx playwright test src/e2e/PreviewBridge.spec.ts src/e2e/ImageUpload.spec.ts src/e2e/RunStatus.spec.ts
```

Add or update Playwright tests for the new behavior:

- Live multi-page render:
  - mock at least three pages;
  - assert `live-page-map` is visible;
  - assert one `live-page-iframe` per page;
  - assert page labels are visible.
- Live iframe click blocking:
  - mock a page with a button or link that would mutate visible content;
  - click at the button coordinates through the page;
  - assert the mutation/navigation does not happen.
- Page label mention insertion:
  - click the label for a page with slug `about`;
  - assert `chat-textarea` contains `@about `;
  - verify insertion at cursor in an existing draft.
- Connector overlay:
  - mock a home page containing links to `about` and `cart`;
  - assert `live-link-overlay` is visible;
  - assert at least two `live-link-connector` paths render;
  - assert connector paths have dashed stroke styling and non-empty color values.
- Build mode regression:
  - switch to Build;
  - assert there is one `preview-iframe`;
  - assert its `src` matches `/preview/{sessionId}/...`;
  - assert live-only test IDs are absent.

## Edge Cases

- Pages with duplicate titles should still work because mention insertion and target matching use slug/id.
- Links to unknown pages should not render connectors.
- External links should not render connectors.
- Hash-only links should not render connectors.
- Hidden links should not render connectors.
- Iframes that fail to load should still show their frame and label, but no connectors.
- Very small workbench widths should stack frames in one column and keep labels readable.
- Connector overlay should not capture pointer events or block scrolling.

## Implementation Notes

- Keep `appModeRuntime` unchanged for build/single-page compatibility unless connector slug normalization needs to be extracted into a shared helper.
- Prefer extracting slug normalization into a frontend utility only if duplication becomes risky.
- Avoid backend changes for v1.
- Avoid changing the generated page HTML.
- Keep the live map renderer scoped to `PreviewPanel` unless file size or testability argues for a separate component.
- Preserve existing `preview-iframe` test ID for build mode and current single-frame fallback behavior.

## Assumptions

- "页面以引用的形式加入 chat input" means inserting the existing page mention syntax: `@slug `.
- "粗的虚线" means a visible cross-frame connector from each internal navigation link/button to its target page iframe.
- Link buttons are represented in generated HTML as anchors or elements wrapped by anchors. V1 connector detection will inspect `a[href]`.
- Live mode is a visual overview and navigation map, not the final interactive app.
- Build mode is the source of truth for complete app interactions.
