# Phase F1: ProductDocPanel Component

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B1 (ProductDoc Service)
  - **Blocks**: F4

## Goal

Implement the ProductDocPanel component that displays the Product Doc in a read-only Markdown-rendered view with status badge and edit guidance.

## Detailed Tasks

### Task 1: Create ProductDocPanel Component

**Description**: Build the main component for displaying Product Doc.

**Implementation Details**:
- [ ] Create ProductDocPanel component with sessionId prop
- [ ] Fetch ProductDoc using useProductDoc hook
- [ ] Render Markdown content using react-markdown or similar
- [ ] Display status badge (draft/confirmed/outdated)
- [ ] Show bottom guidance bar ("通过左侧聊天修改此文档")
- [ ] Handle loading state with skeleton
- [ ] Handle empty state ("开始对话后将自动生成产品文档")

**Files to modify/create**:
- `packages/web/src/components/custom/ProductDocPanel.tsx` (new)

**Acceptance Criteria**:
- [ ] Markdown renders correctly
- [ ] Status badge shows correct state
- [ ] Loading and empty states handled
- [ ] Scrollable for long documents

---

### Task 2: Create useProductDoc Hook

**Description**: Implement hook for fetching and managing ProductDoc state.

**Implementation Details**:
- [ ] Implement `useProductDoc(sessionId)` hook
- [ ] Fetch from `GET /api/sessions/{id}/product-doc`
- [ ] Handle loading and error states
- [ ] Implement `refresh()` function for manual refresh
- [ ] Set up SSE event listener for real-time updates

**Files to modify/create**:
- `packages/web/src/hooks/useProductDoc.ts` (new)

**Acceptance Criteria**:
- [ ] Initial fetch works
- [ ] Refresh function works
- [ ] Error handling works
- [ ] SSE updates trigger re-render

---

### Task 3: Add ProductDoc Types

**Description**: Define TypeScript types for ProductDoc.

**Implementation Details**:
- [ ] Create ProductDoc interface
- [ ] Create ProductDocStructured interface
- [ ] Create ProductDocFeature interface
- [ ] Create DesignDirection interface
- [ ] Create ProductDocPage interface
- [ ] Export all types from index.ts

**Files to modify/create**:
- `packages/web/src/types/index.ts`

**Acceptance Criteria**:
- [ ] All types match backend schema
- [ ] Types properly exported
- [ ] Type safety enforced

---

### Task 4: Add API Client Methods

**Description**: Add methods to API client for ProductDoc endpoints.

**Implementation Details**:
- [ ] Add `getProductDoc(sessionId): Promise<ProductDoc>`
- [ ] Handle 404 response (return null)
- [ ] Add proper error handling

**Files to modify/create**:
- `packages/web/src/api/client.ts`

**Acceptance Criteria**:
- [ ] API method works correctly
- [ ] 404 handled gracefully
- [ ] Types match response

---

### Task 5: Style the ProductDoc Panel

**Description**: Apply proper styling to match design system.

**Implementation Details**:
- [ ] Add header with title and status badge
- [ ] Style status badges (draft=yellow, confirmed=green, outdated=orange)
- [ ] Style Markdown content (headings, lists, code blocks)
- [ ] Add scrollable content area
- [ ] Add bottom guidance bar styling
- [ ] Ensure responsive design

**Files to modify/create**:
- `packages/web/src/components/custom/ProductDocPanel.tsx`

**Acceptance Criteria**:
- [ ] Visual design matches mockup
- [ ] Status badges visually distinct
- [ ] Markdown styled appropriately
- [ ] No horizontal overflow

---

### Task 6: Handle SSE Events for Real-time Updates

**Description**: Listen for ProductDoc events and update UI.

**Implementation Details**:
- [ ] Listen for `product_doc_generated` event → refresh
- [ ] Listen for `product_doc_updated` event → refresh
- [ ] Listen for `product_doc_confirmed` event → refresh (status change)
- [ ] Listen for `product_doc_outdated` event → refresh (status change)
- [ ] Update useProductDoc hook to handle events

**Files to modify/create**:
- `packages/web/src/hooks/useProductDoc.ts`
- `packages/web/src/types/events.ts`

**Acceptance Criteria**:
- [ ] Events trigger UI updates
- [ ] No unnecessary re-renders
- [ ] Cleanup on unmount

---

## Technical Specifications

### ProductDocPanel Props

```typescript
interface ProductDocPanelProps {
  sessionId: string
}
```

### useProductDoc Hook

```typescript
function useProductDoc(sessionId: string) {
  return {
    productDoc: ProductDoc | null
    isLoading: boolean
    error: string | null
    refresh: () => Promise<void>
  }
}
```

### ProductDoc Types

```typescript
interface ProductDoc {
  id: string
  sessionId: string
  content: string          // Markdown
  structured: ProductDocStructured
  status: 'draft' | 'confirmed' | 'outdated'
  createdAt: Date
  updatedAt: Date
}

interface ProductDocStructured {
  projectName: string
  description: string
  targetAudience: string
  goals: string[]
  features: ProductDocFeature[]
  designDirection: DesignDirection
  pages: ProductDocPage[]
  constraints: string[]
}

interface ProductDocFeature {
  name: string
  description: string
  priority: 'must' | 'should' | 'nice'
}

interface DesignDirection {
  style: string
  colorPreference: string
  tone: string
  referenceSites: string[]
}

interface ProductDocPage {
  title: string
  slug: string
  purpose: string
  sections: string[]
  required: boolean
}
```

### Component Structure

```tsx
function ProductDocPanel({ sessionId }: ProductDocPanelProps) {
  const { productDoc, isLoading, error } = useProductDoc(sessionId)

  if (isLoading) {
    return <ProductDocSkeleton />
  }

  if (!productDoc) {
    return <ProductDocEmpty />
  }

  return (
    <div className="product-doc-panel">
      <header className="product-doc-header">
        <h2>Product Doc</h2>
        <StatusBadge status={productDoc.status} />
      </header>

      <div className="product-doc-content">
        <ReactMarkdown>{productDoc.content}</ReactMarkdown>
      </div>

      <footer className="product-doc-footer">
        <span>💡 通过左侧聊天修改此文档</span>
      </footer>
    </div>
  )
}
```

### Status Badge Styles

```css
.status-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.draft {
  background: #fef3c7;
  color: #92400e;
}

.status-badge.confirmed {
  background: #d1fae5;
  color: #065f46;
}

.status-badge.outdated {
  background: #ffedd5;
  color: #9a3412;
}
```

## Testing Requirements

- [ ] Unit tests for ProductDocPanel rendering
- [ ] Unit tests for useProductDoc hook
- [ ] Test loading state
- [ ] Test empty state
- [ ] Test error state
- [ ] Test Markdown rendering
- [ ] Test status badge display
- [ ] Test SSE event handling

## Notes & Warnings

- **Markdown Security**: Sanitize Markdown to prevent XSS (react-markdown does this by default)
- **Large Documents**: Consider virtual scrolling for very long documents
- **Re-render Performance**: Memoize Markdown rendering if content doesn't change
- **Accessibility**: Ensure proper heading hierarchy in rendered Markdown
- **Mobile**: Ensure readable on mobile devices within 430px viewport
