# Phase F6: Chat & Event Integration

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B9 (Chat API Update)
  - **Blocks**: None

## Goal

Update the chat integration to handle new response fields, action types, and coordinate with the workbench tabs for a seamless user experience.

## Detailed Tasks

### Task 1: Update useChat Hook for New Response Fields

**Description**: Handle new fields in chat response.

**Implementation Details**:
- [ ] Parse `product_doc_updated` field
- [ ] Parse `affected_pages` array
- [ ] Parse `action` field
- [ ] Parse `active_page_slug` field
- [ ] Update state based on new fields
- [ ] Trigger appropriate side effects

**Files to modify/create**:
- `packages/web/src/hooks/useChat.ts`

**Acceptance Criteria**:
- [ ] New fields parsed correctly
- [ ] State updated appropriately
- [ ] No breaking changes to existing behavior

---

### Task 2: Add generate_now Support

**Description**: Support Generate Now mode in chat requests.

**Implementation Details**:
- [ ] Add `generateNow` parameter to sendMessage function
- [ ] Pass `generate_now: true` in request body when enabled
- [ ] Expose UI control for Generate Now (button or option)
- [ ] Handle Generate Now response flow

**Files to modify/create**:
- `packages/web/src/hooks/useChat.ts`
- `packages/web/src/components/custom/ChatInput.tsx`

**Acceptance Criteria**:
- [ ] Generate Now parameter sent correctly
- [ ] UI control available
- [ ] Response handled properly

---

### Task 3: Handle New SSE Event Types

**Description**: Add handlers for new ProductDoc and page events.

**Implementation Details**:
- [ ] Add handler for `product_doc_generated`
- [ ] Add handler for `product_doc_updated`
- [ ] Add handler for `product_doc_confirmed`
- [ ] Add handler for `product_doc_outdated`
- [ ] Add handler for `multipage_decision_made`
- [ ] Add handler for `sitemap_proposed`
- [ ] Update event types definition

**Files to modify/create**:
- `packages/web/src/hooks/useChat.ts`
- `packages/web/src/types/events.ts`

**Acceptance Criteria**:
- [ ] All new event types handled
- [ ] Events trigger appropriate updates
- [ ] Type definitions complete

---

### Task 4: Coordinate Tab Switching with Actions

**Description**: Auto-switch workbench tabs based on chat action.

**Implementation Details**:
- [ ] When action is `product_doc_generated` → switch to Product Doc tab
- [ ] When action is `product_doc_updated` → switch to Product Doc tab (optional)
- [ ] When action is `pages_generated` → switch to Preview tab
- [ ] When action is `page_refined` → switch to Preview tab + select affected page
- [ ] Expose callback for tab switching coordination
- [ ] Track auto-switch state to avoid repeated switches

**Files to modify/create**:
- `packages/web/src/hooks/useChat.ts`
- `packages/web/src/pages/ProjectPage.tsx`

**Acceptance Criteria**:
- [ ] Tabs switch appropriately
- [ ] User can override
- [ ] Not annoyingly repetitive

---

### Task 5: Update ChatMessage for ProductDoc Actions

**Description**: Display appropriate messages for ProductDoc actions.

**Implementation Details**:
- [ ] Show "查看 Product Doc 标签页" link when ProductDoc generated/updated
- [ ] Show affected pages list when relevant
- [ ] Style ProductDoc-related messages appropriately
- [ ] Add clickable link to switch tabs

**Files to modify/create**:
- `packages/web/src/components/custom/ChatMessage.tsx`

**Acceptance Criteria**:
- [ ] ProductDoc messages informative
- [ ] Tab link works
- [ ] Affected pages shown clearly

---

### Task 6: Update Event Display for New Events

**Description**: Show new event types in Events panel.

**Implementation Details**:
- [ ] Display `product_doc_generated` events
- [ ] Display `product_doc_confirmed` events
- [ ] Display `multipage_decision_made` with confidence
- [ ] Display `sitemap_proposed` with page count
- [ ] Display `page_version_created` with page info
- [ ] Format events nicely with icons

**Files to modify/create**:
- `packages/web/src/components/EventFlow/EventList.tsx`

**Acceptance Criteria**:
- [ ] New events displayed
- [ ] Events formatted nicely
- [ ] Relevant details shown

---

### Task 7: Handle Disambiguation Response

**Description**: Handle when chat needs user to choose a page.

**Implementation Details**:
- [ ] Detect disambiguation in response (multiple page options)
- [ ] Display page options as clickable chips
- [ ] Allow user to select and send follow-up
- [ ] Or allow user to type their own response

**Files to modify/create**:
- `packages/web/src/components/custom/ChatMessage.tsx`
- `packages/web/src/components/custom/ChatPanel.tsx`

**Acceptance Criteria**:
- [ ] Disambiguation options displayed
- [ ] Clicking option sends response
- [ ] User can also type manually

---

## Technical Specifications

### Updated Chat Response Type

```typescript
interface ChatResponse {
  sessionId: string
  message: string

  // Preview
  previewUrl: string | null
  previewHtml: string | null
  activePageSlug: string | null

  // ProductDoc state
  productDocUpdated: boolean
  affectedPages: string[]

  // Action
  action: ChatAction

  // Token usage
  tokensUsed: number
}

type ChatAction =
  | 'product_doc_generated'
  | 'product_doc_updated'
  | 'product_doc_confirmed'
  | 'pages_generated'
  | 'page_refined'
  | 'direct_reply'
```

### Updated useChat Hook

```typescript
interface UseChatOptions {
  onTabChange?: (tab: 'preview' | 'code' | 'product-doc') => void
  onPageSelect?: (slug: string) => void
}

function useChat(sessionId: string | null, options?: UseChatOptions) {
  const sendMessage = async (
    message: string,
    generateNow?: boolean
  ) => {
    const response = await api.chat({
      sessionId,
      message,
      generate_now: generateNow
    })

    // Handle action-based tab switching
    if (response.action === 'product_doc_generated') {
      options?.onTabChange?.('product-doc')
    } else if (
      response.action === 'pages_generated' ||
      response.action === 'page_refined'
    ) {
      options?.onTabChange?.('preview')
      if (response.activePageSlug) {
        options?.onPageSelect?.(response.activePageSlug)
      }
    }

    return response
  }

  // ... rest of hook
}
```

### New Event Types

```typescript
// Add to events.ts
interface ProductDocGeneratedEvent {
  type: 'product_doc_generated'
  sessionId: string
  docId: string
}

interface ProductDocUpdatedEvent {
  type: 'product_doc_updated'
  sessionId: string
  docId: string
  changeSummary?: string
}

interface ProductDocConfirmedEvent {
  type: 'product_doc_confirmed'
  sessionId: string
  docId: string
}

interface MultipageDecisionEvent {
  type: 'multipage_decision_made'
  sessionId: string
  decision: 'single_page' | 'multi_page' | 'suggest_multi_page'
  confidence: number
  reasons: string[]
}

interface SitemapProposedEvent {
  type: 'sitemap_proposed'
  sessionId: string
  pagesCount: number
}
```

### Chat Message with ProductDoc Link

```tsx
function ChatMessage({ message, action, onTabChange }: ChatMessageProps) {
  const showProductDocLink =
    action === 'product_doc_generated' ||
    action === 'product_doc_updated'

  return (
    <div className="chat-message">
      <div className="message-content">
        {message}
      </div>

      {showProductDocLink && (
        <button
          className="tab-link"
          onClick={() => onTabChange('product-doc')}
        >
          查看 Product Doc 标签页 →
        </button>
      )}
    </div>
  )
}
```

### Event Display Formatting

```tsx
function formatEvent(event: SSEEvent) {
  switch (event.type) {
    case 'product_doc_generated':
      return { icon: '📄', text: 'Product Doc 已生成' }
    case 'product_doc_confirmed':
      return { icon: '✅', text: 'Product Doc 已确认' }
    case 'multipage_decision_made':
      return {
        icon: '🔀',
        text: `决策: ${event.decision} (置信度: ${Math.round(event.confidence * 100)}%)`
      }
    case 'sitemap_proposed':
      return { icon: '🗺️', text: `Sitemap 已生成 (${event.pagesCount} 页)` }
    case 'page_version_created':
      return { icon: '📝', text: `页面 ${event.slug} v${event.version}` }
    // ... other cases
  }
}
```

## Testing Requirements

- [ ] Unit tests for new response field handling
- [ ] Unit tests for generate_now support
- [ ] Unit tests for new event handlers
- [ ] Test tab switching coordination
- [ ] Test disambiguation UI
- [ ] Test event display formatting

## Notes & Warnings

- **Tab Switching UX**: Be careful not to switch tabs too aggressively
- **Event Ordering**: Handle events arriving out of order
- **Error Handling**: Show clear messages when operations fail
- **Disambiguation**: Make it easy for user to choose or type
- **State Sync**: Ensure chat state and workbench state stay in sync
