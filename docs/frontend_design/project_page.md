# ProjectPage Layout And Component Notes

Last updated: 2026-05-13

Note: the ProjectPage Run details drawer and `RunInspector` UI were removed after this layout pass. Do not reintroduce a Run details button, drawer, or sidebar above the chat input; keep run visibility lightweight in `RunStatusStrip` or route deeper diagnostics to a dedicated non-chat surface.

## Source Files

- `packages/web/src/pages/ProjectPage.tsx`
- `packages/web/src/components/custom/ChatPanel.tsx`
- `packages/web/src/components/custom/ChatMessage.tsx`
- `packages/web/src/components/custom/ChatInput.tsx`
- `packages/web/src/components/custom/WorkbenchPanel.tsx`
- `packages/web/src/components/custom/PreviewPanel.tsx`
- `packages/web/src/components/custom/VersionPanel.tsx`
- `packages/web/src/components/custom/RunStatusStrip.tsx`
- `packages/web/src/hooks/useChat.ts`
- `packages/web/src/hooks/chat/useChatStream.ts`
- `packages/web/src/hooks/chat/useStreamHandler.ts`
- `packages/web/src/hooks/usePreviewBridge.ts`

## Current Component Tree

```text
ProjectPage
├── Project header and actions
├── ChatPanel
│   ├── ChatMessage[]
│   ├── InterviewWidget
│   ├── RunStatusStrip
│   └── ChatInput
├── WorkbenchPanel
│   ├── PreviewPanel
│   ├── Code panel / file viewer
│   ├── ProductDoc panel
│   └── Data tab
└── VersionPanel
```

## Layout

`ProjectPage` is a three-column work surface:

- Left column: chat, roughly 35 percent of the layout.
- Center column: workbench, flexible width.
- Right column: version panel, collapsible.

The current ProjectPage does not use the older left-side `Chat | Events` tab model. Event visibility is now split between chat step rendering, EventFlow components where used, and run-specific UI.

## Chat Panel

Responsibilities:

- Render user/assistant messages.
- Render compact agent/tool steps under assistant messages.
- Render interview questions and answer summaries.
- Support page/file mentions and uploads.
- Trigger send/stream behavior through `useChat`.
- Surface run state through `RunStatusStrip` only.

Important behavior:

- Tool entries are summarized before display to avoid large payloads.
- Streaming assistant content and streaming steps can update independently.
- Interview answers are submitted as structured payload plus readable summary text.
- The run inspector stays compact so it does not block chat input.

## Run UI

`RunStatusStrip` provides the compact status line for:

- run status
- current phase
- build state
- review result
- policy/verify state where available

SSE events may place fields at the top level or inside `payload`; run UI should handle both shapes without adding a ProjectPage Run details drawer or Run Inspector.

## Workbench Panel

Current tabs:

- `preview`: live/build preview and preview bridge.
- `code`: generated file tree/content.
- `product-doc`: current product doc and history.
- `data`: app data tables/state/events/records view.

The Data tab is top-level in the workbench, not a nested sub-tab inside Preview.

## Preview Panel

Responsibilities:

- Display live HTML or build preview URL.
- Support mobile-framed preview.
- Integrate preview bridge messages from generated pages.
- Provide build status visibility where available.

`usePreviewBridge` listens for `instant-coffee:update`-style postMessage events from the iframe and feeds state/events/records into the Data tab.

## Version Panel

Responsibilities:

- Show legacy session versions where available.
- Show page versions for multi-page projects.
- Preview historical page versions.
- Support pin/unpin flows.
- Use project snapshot rollback for rollback behavior. The page-level rollback route currently returns `410 rollback_not_supported`.

Backend support includes:

- `GET /api/pages/{page_id}/versions`
- `GET /api/pages/{page_id}/versions/{version_id}/preview`
- `POST /api/pages/{page_id}/versions/{version_id}/pin`
- `POST /api/pages/{page_id}/versions/{version_id}/unpin`
- `POST /api/sessions/{session_id}/snapshots/{snapshot_id}/rollback`

## Data Flow

Chat:

```text
ChatInput
  -> ChatPanel.onSendMessage
  -> useChat.sendMessage
  -> /api/chat or /api/chat/stream
  -> useChatStream/useStreamHandler
  -> messages, steps, preview, run status
```

Preview:

```text
backend page/build response
  -> ProjectPage preview state
  -> WorkbenchPanel
  -> PreviewPanel iframe
  -> usePreviewBridge
  -> Data tab
```

Runs:

```text
chat stream SSE
  -> run lifecycle/build/review/verify/tool-policy events
  -> useStreamHandler
  -> ChatRunStatus
  -> RunStatusStrip
```

## Current Caveats

- `ProjectPage` still references a legacy export call through the API client.
- Some flow/task controls remain legacy and should be routed through `/api/runs` or removed.
- Keep `packages/web/src/types/events.ts` synchronized with backend event definitions.
