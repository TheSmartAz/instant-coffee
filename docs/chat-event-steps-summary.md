# Chat Event Steps Summary

## Goal
Move agent and tool execution visibility from the Events panel into the chat stream, using a compact step list under the assistant response (Option C). Tool entries should be summarized; agent entries should be visible in chat but hidden from the Events tab.

## What Changed

### Behavior
- Chat now renders agent and tool execution events as sub-steps under the streaming assistant message.
- Tool steps show a short summary (path/url/query/etc.) and avoid large content fields.
- Events tab no longer shows agent events; tool/task/plan events remain.

### Files Touched
- `packages/web/src/types/index.ts`
  - Added `ChatStep` and `ChatStepStatus` types.
  - Extended `Message` with optional `steps` field.

- `packages/web/src/components/custom/ChatMessage.tsx`
  - Renders `steps` under assistant messages as a compact list.
  - Shows streaming dots even when content is empty but steps are updating.

- `packages/web/src/hooks/useChat.ts`
  - Accepts `agent_*` and `tool_*` SSE events.
  - Converts those events into `ChatStep` entries.
  - Summarizes tool inputs/outputs (path/url/query/etc.) and avoids large/sensitive fields.
  - Keeps assistant content streaming behavior unchanged.

- `packages/web/src/components/EventFlow/EventList.tsx`
  - Filters out `agent_*` events in both streaming and phase modes.

## Step Display (Option C)
```
[User]  生成一个落地页
[Asst]  正在生成...
        ↳ agent_start: generation agent started
        ↳ tool_call: Calling filesystem_write (path=.../index.html)
        ↳ tool_result: Result filesystem_write (written_bytes=12345)
[Asst]  已完成页面生成，给你预览。
```

## Notes
- Tool call/result pairing is implicit; there is no call_id in events. If pairing is needed, add a unique tool_call_id to event payloads.
- This change only affects UI display; backend event emission is unchanged.

## Interview Widget (Chat)

### Behavior
- Interview questions render inside the chat as a widget instead of plain text.
- Supports single choice, multi choice, and short text inputs.
- Shows 1 question at a time with Previous/Next; final question shows Submit.
- Includes Skip questions and Generate now actions.
- After submission, the widget collapses and only the answer summary remains (assistant bubble).
- Question numbering is cumulative across batches (e.g., 4/7).

### Payload
- Frontend submits answers in mixed mode:
  - Structured JSON inside `<INTERVIEW_ANSWERS>...</INTERVIEW_ANSWERS>`
  - Plus a readable summary line
- Backend parses structured answers and uses latest values when updated by user text.
- Even when interview toggle is off, the latest chat message is sent alongside the collected answers for context.
- Generation prioritizes the latest user message when conflicts exist.

### Interview Toggle
- Toggle is always visible in the chat input.
- First user message defaults to interview ON, but the user can turn it off.
- Later messages only trigger interview if the toggle is enabled.
- Toggle resets to OFF after sending a message (user must opt in each time).
- Frontend passes `interview=true/false` to the chat API; backend only uses the default-first-message rule when this param is absent.
- When toggle is off, messages behave as normal chat (no interview questions), but still pass collected answers as context.

### Files Touched
- `packages/web/src/components/custom/InterviewWidget.tsx`
- `packages/web/src/components/custom/ChatMessage.tsx`
- `packages/web/src/hooks/useChat.ts`
- `packages/backend/app/agents/interview.py`
- `packages/backend/app/agents/orchestrator.py`
- `packages/backend/app/agents/prompts.py`
