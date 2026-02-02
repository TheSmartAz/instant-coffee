# Phase F2: PreviewPanel Multi-Page Enhancement

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B2 (Page Service)
  - **Blocks**: F4

## Goal

Enhance the PreviewPanel to support multi-page preview with page selector, maintain page state, and coordinate with VersionPanel.

## Detailed Tasks

### Task 1: Create PageSelector Component

**Description**: Build component for switching between pages.

**Implementation Details**:
- [ ] Create PageSelector component with pages and selectedPageId props
- [ ] Render as horizontal tab bar
- [ ] Display page title as tab label
- [ ] Highlight active page
- [ ] Handle click to select page
- [ ] Hide when only one page exists

**Files to modify/create**:
- `packages/web/src/components/custom/PageSelector.tsx` (new)

**Acceptance Criteria**:
- [ ] Tabs render for all pages
- [ ] Active page highlighted
- [ ] Click changes selection
- [ ] Hidden for single page

---

### Task 2: Create usePages Hook

**Description**: Implement hook for fetching and managing pages state.

**Implementation Details**:
- [ ] Implement `usePages(sessionId)` hook
- [ ] Fetch from `GET /api/sessions/{id}/pages`
- [ ] Track selected page ID
- [ ] Implement `selectPage(pageId)` function
- [ ] Listen for page-related SSE events
- [ ] Auto-select first page on initial load

**Files to modify/create**:
- `packages/web/src/hooks/usePages.ts` (new)

**Acceptance Criteria**:
- [ ] Pages fetched correctly
- [ ] Selection state maintained
- [ ] Events trigger updates
- [ ] First page auto-selected

---

### Task 3: Add Page Types

**Description**: Define TypeScript types for Page and PageVersion.

**Implementation Details**:
- [ ] Create Page interface
- [ ] Create PageVersion interface
- [ ] Export types from index.ts

**Files to modify/create**:
- `packages/web/src/types/index.ts`

**Acceptance Criteria**:
- [ ] Types match backend schema
- [ ] Types properly exported

---

### Task 4: Update PreviewPanel for Multi-Page

**Description**: Modify PreviewPanel to support multi-page preview.

**Implementation Details**:
- [ ] Add pages and selectedPageId props
- [ ] Integrate PageSelector at top
- [ ] Load HTML for selected page
- [ ] Update PhoneFrame with new HTML on page change
- [ ] Maintain existing refresh and export functionality
- [ ] Pass page-specific version info to parent

**Files to modify/create**:
- `packages/web/src/components/custom/PreviewPanel.tsx`

**Acceptance Criteria**:
- [ ] Page selector shows at top
- [ ] PhoneFrame loads correct page
- [ ] Page switching works smoothly
- [ ] Export still works

---

### Task 5: Add API Client Methods for Pages

**Description**: Add methods for page-related API calls.

**Implementation Details**:
- [ ] Add `getPages(sessionId): Promise<Page[]>`
- [ ] Add `getPagePreview(pageId): Promise<{html: string}>`
- [ ] Add `getPageVersions(pageId): Promise<PageVersion[]>`
- [ ] Add `rollbackPage(pageId, versionId): Promise<void>`

**Files to modify/create**:
- `packages/web/src/api/client.ts`

**Acceptance Criteria**:
- [ ] All API methods work
- [ ] Types match responses
- [ ] Error handling included

---

### Task 6: Handle Page Events

**Description**: Listen for page-related SSE events.

**Implementation Details**:
- [ ] Listen for `page_created` → refresh pages list
- [ ] Listen for `page_version_created` → refresh if current page
- [ ] Listen for `page_preview_ready` → refresh preview if current page
- [ ] Update usePages hook for event handling

**Files to modify/create**:
- `packages/web/src/hooks/usePages.ts`
- `packages/web/src/types/events.ts`

**Acceptance Criteria**:
- [ ] Events trigger appropriate updates
- [ ] Only affected pages refresh
- [ ] No unnecessary re-renders

---

### Task 7: Coordinate with VersionPanel

**Description**: Notify VersionPanel of selected page changes.

**Implementation Details**:
- [ ] When page changes, notify parent
- [ ] Parent passes current page to VersionPanel
- [ ] VersionPanel fetches versions for current page
- [ ] Preview and VersionPanel stay in sync

**Files to modify/create**:
- `packages/web/src/components/custom/PreviewPanel.tsx`
- `packages/web/src/pages/ProjectPage.tsx`

**Acceptance Criteria**:
- [ ] Page change updates VersionPanel
- [ ] Versions match selected page
- [ ] No race conditions

---

## Technical Specifications

### PageSelector Props

```typescript
interface PageSelectorProps {
  pages: Page[]
  selectedPageId: string | null
  onSelectPage: (pageId: string) => void
}
```

### usePages Hook

```typescript
function usePages(sessionId: string) {
  return {
    pages: Page[]
    selectedPage: Page | null
    selectPage: (pageId: string) => void
    isLoading: boolean
    refresh: () => Promise<void>
  }
}
```

### Page Types

```typescript
interface Page {
  id: string
  sessionId: string
  title: string
  slug: string
  description: string
  orderIndex: number
  currentVersionId: string | null
  createdAt: Date
  updatedAt: Date
}

interface PageVersion {
  id: number
  pageId: string
  version: number
  description: string | null
  createdAt: Date
}
```

### Updated PreviewPanel Props

```typescript
interface PreviewPanelProps {
  sessionId: string
  pages: Page[]
  selectedPageId: string | null
  onSelectPage: (pageId: string) => void
  previewHtml: string | null
  onExport: () => void
  onRefresh: () => void
}
```

### PageSelector Component

```tsx
function PageSelector({ pages, selectedPageId, onSelectPage }: PageSelectorProps) {
  if (pages.length <= 1) {
    return null
  }

  return (
    <div className="page-selector">
      {pages.map(page => (
        <button
          key={page.id}
          className={`page-tab ${page.id === selectedPageId ? 'active' : ''}`}
          onClick={() => onSelectPage(page.id)}
        >
          {page.title}
        </button>
      ))}
    </div>
  )
}
```

### PageSelector Styles

```css
.page-selector {
  display: flex;
  gap: 4px;
  padding: 8px;
  background: #f5f5f5;
  overflow-x: auto;
  border-bottom: 1px solid #e0e0e0;
}

.page-selector::-webkit-scrollbar {
  display: none;
}

.page-tab {
  padding: 6px 12px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
  font-size: 14px;
  color: #666;
  transition: all 0.2s;
}

.page-tab:hover {
  background: #e0e0e0;
}

.page-tab.active {
  background: #1976d2;
  color: white;
}
```

## Testing Requirements

- [ ] Unit tests for PageSelector
- [ ] Unit tests for usePages hook
- [ ] Test page switching
- [ ] Test single page (selector hidden)
- [ ] Test multi-page (selector visible)
- [ ] Test event handling
- [ ] Test version panel coordination

## Notes & Warnings

- **Scroll Position**: Reset scroll position when switching pages
- **Loading State**: Show loading indicator during page switch
- **Cache Strategy**: Consider caching page HTML for faster switching
- **Event Race**: Handle case where page is deleted while selected
- **Mobile**: Ensure page tabs are scrollable on mobile
