# Phase F7: ProjectPage Layout Update

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: F4 (WorkbenchPanel), F5 (VersionPanel Update), F6 (Chat Integration)
  - **Blocks**: None

## Goal

Update the ProjectPage to integrate all new components, manage state across WorkbenchPanel and VersionPanel, and coordinate data flow between chat, preview, and product doc.

## Detailed Tasks

### Task 1: Replace PreviewPanel with WorkbenchPanel

**Description**: Update center panel to use new WorkbenchPanel.

**Implementation Details**:
- [ ] Remove direct PreviewPanel usage
- [ ] Add WorkbenchPanel with all three tabs
- [ ] Pass required props for each tab
- [ ] Manage activeTab state in ProjectPage
- [ ] Handle tab change callbacks

**Files to modify/create**:
- `packages/web/src/pages/ProjectPage.tsx`

**Acceptance Criteria**:
- [ ] WorkbenchPanel replaces PreviewPanel
- [ ] All three tabs functional
- [ ] State properly managed

---

### Task 2: Integrate useProductDoc Hook

**Description**: Add ProductDoc state management.

**Implementation Details**:
- [ ] Call useProductDoc with sessionId
- [ ] Pass productDoc to WorkbenchPanel
- [ ] Handle loading and error states
- [ ] Set up refresh on relevant events

**Files to modify/create**:
- `packages/web/src/pages/ProjectPage.tsx`

**Acceptance Criteria**:
- [ ] ProductDoc fetched correctly
- [ ] Data flows to ProductDocPanel
- [ ] Real-time updates work

---

### Task 3: Integrate usePages Hook

**Description**: Add pages state management.

**Implementation Details**:
- [ ] Call usePages with sessionId
- [ ] Pass pages and selectedPageId to WorkbenchPanel
- [ ] Handle page selection changes
- [ ] Set up refresh on relevant events

**Files to modify/create**:
- `packages/web/src/pages/ProjectPage.tsx`

**Acceptance Criteria**:
- [ ] Pages fetched correctly
- [ ] Page selection works
- [ ] Data flows to PreviewPanel

---

### Task 4: Connect VersionPanel to Page State

**Description**: Wire VersionPanel to show selected page versions.

**Implementation Details**:
- [ ] Call usePageVersions with selectedPageId
- [ ] Pass versions to VersionPanel
- [ ] Handle rollback action
- [ ] Pass activeTab to VersionPanel
- [ ] Update on page selection change

**Files to modify/create**:
- `packages/web/src/pages/ProjectPage.tsx`

**Acceptance Criteria**:
- [ ] VersionPanel shows correct versions
- [ ] Rollback works
- [ ] Empty state for non-preview tabs

---

### Task 5: Coordinate Tab Switching from Chat

**Description**: Handle tab switching based on chat actions.

**Implementation Details**:
- [ ] Pass onTabChange callback to useChat
- [ ] Pass onPageSelect callback to useChat
- [ ] Handle auto-switching logic
- [ ] Maintain user's manual tab selection preference

**Files to modify/create**:
- `packages/web/src/pages/ProjectPage.tsx`

**Acceptance Criteria**:
- [ ] Chat actions trigger tab switches
- [ ] Page selection works from chat
- [ ] User can override

---

### Task 6: Update Page Preview Loading

**Description**: Load preview HTML for selected page.

**Implementation Details**:
- [ ] When page selection changes, fetch preview HTML
- [ ] Use getPagePreview API
- [ ] Pass previewHtml to WorkbenchPanel
- [ ] Handle loading state in PhoneFrame

**Files to modify/create**:
- `packages/web/src/pages/ProjectPage.tsx`

**Acceptance Criteria**:
- [ ] Preview loads for selected page
- [ ] Loading state shown
- [ ] Error handling works

---

### Task 7: Handle Export Action

**Description**: Connect export button to export functionality.

**Implementation Details**:
- [ ] Implement onExport handler
- [ ] Call export API
- [ ] Show success/error notification
- [ ] Consider download or open exported files

**Files to modify/create**:
- `packages/web/src/pages/ProjectPage.tsx`

**Acceptance Criteria**:
- [ ] Export triggers correctly
- [ ] User gets feedback
- [ ] Error handling works

---

### Task 8: Maintain Three-Column Layout

**Description**: Ensure layout matches spec with three columns.

**Implementation Details**:
- [ ] Left: ChatPanel (35%)
- [ ] Center: WorkbenchPanel (flex-1)
- [ ] Right: VersionPanel (48px/256px collapsible)
- [ ] Ensure proper responsive behavior
- [ ] Handle overflow correctly

**Files to modify/create**:
- `packages/web/src/pages/ProjectPage.tsx`

**Acceptance Criteria**:
- [ ] Layout matches spec
- [ ] Columns resize correctly
- [ ] No overflow issues

---

## Technical Specifications

### Updated ProjectPage Component

```tsx
function ProjectPage() {
  const { sessionId } = useParams()

  // State
  const [activeTab, setActiveTab] = useState<'preview' | 'code' | 'product-doc'>('preview')
  const [isVersionPanelCollapsed, setIsVersionPanelCollapsed] = useState(false)

  // Hooks
  const { productDoc, refresh: refreshProductDoc } = useProductDoc(sessionId)
  const { pages, selectedPage, selectPage, refresh: refreshPages } = usePages(sessionId)
  const { versions: pageVersions, revert: revertVersion } = usePageVersions(selectedPage?.id)
  const [previewHtml, setPreviewHtml] = useState<string | null>(null)

  // Chat integration
  const { messages, sendMessage, isLoading } = useChat(sessionId, {
    onTabChange: setActiveTab,
    onPageSelect: (slug) => {
      const page = pages.find(p => p.slug === slug)
      if (page) selectPage(page.id)
    }
  })

  // Load preview HTML when page changes
  useEffect(() => {
    if (selectedPage?.id) {
      api.getPagePreview(selectedPage.id).then(data => {
        setPreviewHtml(data.html)
      })
    }
  }, [selectedPage?.id])

  // Export handler
  const handleExport = async () => {
    try {
      await api.exportSession(sessionId)
      toast.success('导出成功')
    } catch (error) {
      toast.error('导出失败')
    }
  }

  // Refresh preview
  const handleRefresh = async () => {
    if (selectedPage?.id) {
      const data = await api.getPagePreview(selectedPage.id)
      setPreviewHtml(data.html)
    }
  }

  return (
    <div className="project-page">
      <Header />

      <div className="project-content">
        {/* Left Panel - Chat */}
        <div className="left-panel">
          <ChatPanel
            messages={messages}
            onSendMessage={sendMessage}
            isLoading={isLoading}
          />
        </div>

        {/* Center Panel - Workbench */}
        <div className="center-panel">
          <WorkbenchPanel
            sessionId={sessionId}
            activeTab={activeTab}
            onTabChange={setActiveTab}
            pages={pages}
            selectedPageId={selectedPage?.id}
            onSelectPage={selectPage}
            previewHtml={previewHtml}
            onExport={handleExport}
            onRefresh={handleRefresh}
            productDoc={productDoc}
          />
        </div>

        {/* Right Panel - Version */}
        <VersionPanel
          isCollapsed={isVersionPanelCollapsed}
          onToggleCollapse={() => setIsVersionPanelCollapsed(!isVersionPanelCollapsed)}
          pageVersions={pageVersions}
          currentPageVersionId={selectedPage?.currentVersionId}
          onRevertPageVersion={revertVersion}
          selectedPageTitle={selectedPage?.title}
          activeTab={activeTab}
        />
      </div>
    </div>
  )
}
```

### Layout Styles

```css
.project-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.project-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.left-panel {
  width: 35%;
  min-width: 320px;
  max-width: 480px;
  border-right: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
}

.center-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

/* VersionPanel handles its own width */
```

### Data Flow Diagram

```
ProjectPage
├── useProductDoc(sessionId) → productDoc
├── usePages(sessionId) → pages, selectedPage, selectPage
├── usePageVersions(selectedPage.id) → pageVersions
├── useChat(sessionId, callbacks) → messages, sendMessage
│
├── ChatPanel ← messages, onSendMessage
│   └── triggers → onTabChange, onPageSelect
│
├── WorkbenchPanel ← activeTab, pages, selectedPageId, previewHtml, productDoc
│   ├── PreviewPanel ← pages, selectedPageId, previewHtml
│   │   └── PageSelector
│   │   └── PhoneFrame
│   ├── CodePanel ← sessionId
│   │   └── useFileTree internally
│   └── ProductDocPanel ← sessionId
│       └── useProductDoc internally (or receive productDoc prop)
│
└── VersionPanel ← activeTab, pageVersions, currentPageVersionId
    └── shows versions only when activeTab === 'preview'
```

## Testing Requirements

- [ ] Integration test for full page functionality
- [ ] Test state flow between components
- [ ] Test tab switching from chat
- [ ] Test page selection updates
- [ ] Test version panel coordination
- [ ] Test export functionality
- [ ] Test responsive layout

## Notes & Warnings

- **State Lifting**: Keep minimal state in ProjectPage; use hooks for data fetching
- **Performance**: Consider memoization for expensive computations
- **Error Boundaries**: Add error boundaries around major sections
- **Loading States**: Coordinate loading states to avoid jarring UX
- **URL State**: Consider syncing active tab to URL for shareable links
