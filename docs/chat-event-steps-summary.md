# Chat Event Steps Summary

Last updated: 2026-05-13

## Goal

Agent, tool, and run execution visibility should appear in the chat stream without overwhelming the user. The chat view should show compact sub-steps under the assistant response, while run-specific status is handled by `RunStatusStrip`. The former ProjectPage Run details drawer and Run Inspector are intentionally removed and should not be reintroduced.

## Current Behavior

- Agent and tool SSE events render as compact steps under streaming assistant messages.
- Tool steps summarize important fields such as path, URL, query, command, and status.
- Large or sensitive fields are omitted from chat display.
- Assistant content can stream while steps update.
- Interview questions render as chat widgets.
- Run lifecycle/build/review/verify/tool-policy events update run status UI.
- EventFlow views should avoid duplicating agent-only noise when the same information is already visible in chat.

## Current Files

- `packages/web/src/types/index.ts`
  - chat message and step types
- `packages/web/src/types/events.ts`
  - frontend SSE event contract
- `packages/web/src/components/custom/ChatMessage.tsx`
  - assistant message and step rendering
- `packages/web/src/components/custom/ChatPanel.tsx`
  - chat composition and run UI placement
- `packages/web/src/components/custom/InterviewWidget.tsx`
  - structured question UI
- `packages/web/src/components/custom/RunStatusStrip.tsx`
  - compact run status
- `packages/web/src/hooks/useChat.ts`
  - high-level chat state
- `packages/web/src/hooks/chat/useChatStream.ts`
  - stream setup
- `packages/web/src/hooks/chat/useStreamHandler.ts`
  - event-to-state conversion
- `packages/web/src/components/EventFlow/EventList.tsx`
  - event filtering/list rendering
- `packages/web/src/components/EventFlow/EventItem.tsx`
  - event item rendering
- `packages/backend/app/events/types.py`
  - backend event constants
- `packages/backend/app/api/chat.py`
  - chat streaming event source
- `packages/backend/app/engine/orchestrator.py`
  - embedded engine adapter
- `packages/backend/app/engine/run_coordinator.py`
  - run phase/lifecycle emission

## Display Model

```text
[User]  Build a mobile landing page
[Asst]  Working on it...
        - agent_start: engine started
        - tool_call: write_file path=/pages/index.html
        - tool_result: write_file ok
        - run_phase: build started
        - verify: review passed
[Asst]  Done. Preview is ready.
```

## Interview Payload

The frontend submits interview answers in mixed mode:

- structured JSON inside `<INTERVIEW_ANSWERS>...</INTERVIEW_ANSWERS>`
- readable answer summary text
- current user message for conflict resolution and context

The backend can use structured answers while still preserving the latest natural-language instruction.

## Notes

- Tool call/result pairing is still best-effort when no unique call id is available.
- Run events may carry fields at top level or under `payload`; UI handlers should normalize both.
- Keep backend event types and frontend event types synchronized.
