# Phase F1: Product Doc Update Card

## Metadata

- **Category**: Frontend
- **Priority**: P1 (Important)
- **Estimated Complexity**: Low
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v09-B7 (API Integration — needs `product_doc_updated` events flowing)
  - **Blocks**: None

## Goal

Display an expandable update card in the chat when the Product Doc changes, with a link to navigate to the full Product Doc tab.

## Detailed Tasks

### Task 1: Product Doc Update Card Component

**Description**: Render an expandable card in the chat stream when `product_doc_updated=True` in the orchestrator response.

**Implementation Details**:
- [ ] Detect `product_doc_updated: true` in SSE event / orchestrator response
- [ ] Render collapsed card: "Product Doc updated: {section_name} section"
- [ ] Expand on click to show updated section content
- [ ] Include "View full Product Doc →" link that navigates to Product Doc tab

**Files to modify/create**:
- `packages/web/src/components/custom/ProductDocUpdateCard.tsx`
- `packages/web/src/components/custom/ChatMessage.tsx` (add card rendering)

**Acceptance Criteria**:
- [ ] Card appears in chat when Product Doc is updated
- [ ] Card is collapsed by default, expandable on click
- [ ] "View full Product Doc" link navigates correctly

---

### Task 2: Integration with Chat Stream

**Description**: Wire the update card into the existing chat message rendering pipeline.

**Implementation Details**:
- [ ] Check for `product_doc_updated` field in `OrchestratorResponse`
- [ ] Render `ProductDocUpdateCard` inline in the chat message list
- [ ] No changes to SSE parsing or event types (uses existing fields)

**Files to modify/create**:
- `packages/web/src/components/custom/ChatMessage.tsx`
- `packages/web/src/hooks/useChat.ts` (if needed for state)

**Acceptance Criteria**:
- [ ] Existing chat messages render unchanged
- [ ] Product Doc update cards appear at correct position in chat

## Technical Specifications

### Component Props

```typescript
interface ProductDocUpdateCardProps {
  sectionName: string;
  sectionContent: string;
  onNavigateToDoc: () => void;
}
```

### Data Source

The `OrchestratorResponse` already has `product_doc_updated: Optional[bool]`. The section details come from the message content or a new field in the SSE payload.

## Testing Requirements

- [ ] Component renders collapsed state correctly
- [ ] Expand/collapse toggle works
- [ ] Navigation link triggers correct callback

## Notes & Warnings

- This is a low-priority enhancement — the system works without it (Product Doc updates still happen, just without visual feedback in chat)
- The existing `InterviewWidget` component requires **no changes** — it already handles `radio`, `checkbox`, `text` question types from the `ask_user` tool
- Keep the card styling consistent with existing chat message components
