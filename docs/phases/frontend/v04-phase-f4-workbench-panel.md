# Phase F4: WorkbenchPanel (Three-Tab Container)

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: F1 (ProductDocPanel), F2 (PreviewPanel), F3 (CodePanel)
  - **Blocks**: F5

## Goal

Implement the WorkbenchPanel component that serves as a three-tab container for Preview, Code, and Product Doc tabs, with proper state management and tab switching logic.

## Detailed Tasks

### Task 1: Create WorkbenchPanel Container

**Description**: Build the main container component with tab navigation.

**Implementation Details**:
- [ ] Create WorkbenchPanel component
- [ ] Implement tab bar with three tabs (Preview, Code, Product Doc)
- [ ] Manage active tab state
- [ ] Render appropriate panel based on active tab
- [ ] Support controlled and uncontrolled mode for activeTab
- [ ] Notify parent of tab changes via callback

**Files to modify/create**:
- `packages/web/src/components/custom/WorkbenchPanel.tsx` (new)

**Acceptance Criteria**:
- [ ] Three tabs rendered
- [ ] Tab switching works
- [ ] Correct panel displayed for each tab
- [ ] Parent notified of changes

---

### Task 2: Integrate PreviewPanel

**Description**: Embed PreviewPanel in Preview tab.

**Implementation Details**:
- [ ] Import and render PreviewPanel
- [ ] Pass through required props (pages, selectedPageId, etc.)
- [ ] Maintain page selection state in WorkbenchPanel or lift to parent
- [ ] Handle preview refresh and export actions

**Files to modify/create**:
- `packages/web/src/components/custom/WorkbenchPanel.tsx`

**Acceptance Criteria**:
- [ ] Preview tab shows PreviewPanel
- [ ] Page selection works
- [ ] Export and refresh work

---

### Task 3: Integrate CodePanel

**Description**: Embed CodePanel in Code tab.

**Implementation Details**:
- [ ] Import and render CodePanel
- [ ] Pass sessionId prop
- [ ] Preserve file tree state when switching away and back
- [ ] Consider lazy loading for performance

**Files to modify/create**:
- `packages/web/src/components/custom/WorkbenchPanel.tsx`

**Acceptance Criteria**:
- [ ] Code tab shows CodePanel
- [ ] File tree state preserved
- [ ] Performance acceptable

---

### Task 4: Integrate ProductDocPanel

**Description**: Embed ProductDocPanel in Product Doc tab.

**Implementation Details**:
- [ ] Import and render ProductDocPanel
- [ ] Pass sessionId prop
- [ ] ProductDoc content refreshes via SSE events
- [ ] Consider lazy loading

**Files to modify/create**:
- `packages/web/src/components/custom/WorkbenchPanel.tsx`

**Acceptance Criteria**:
- [ ] Product Doc tab shows ProductDocPanel
- [ ] Content updates in real-time
- [ ] Performance acceptable

---

### Task 5: Implement Auto Tab Switching

**Description**: Automatically switch tabs based on chat events.

**Implementation Details**:
- [ ] When `product_doc_generated` or `product_doc_updated` → switch to Product Doc tab (once)
- [ ] When `pages_generated` or `page_refined` → switch to Preview tab
- [ ] Track if auto-switch has occurred to avoid repeated switches
- [ ] Allow user to override and stay on preferred tab

**Files to modify/create**:
- `packages/web/src/components/custom/WorkbenchPanel.tsx`
- `packages/web/src/pages/ProjectPage.tsx`

**Acceptance Criteria**:
- [ ] Auto-switch works on relevant events
- [ ] Auto-switch is not annoying (once per event type)
- [ ] User can manually switch tabs

---

### Task 6: Style Tab Bar

**Description**: Apply proper styling to tab navigation.

**Implementation Details**:
- [ ] Style tab bar at top of panel
- [ ] Active tab visually distinct
- [ ] Hover states for tabs
- [ ] Responsive sizing
- [ ] Match overall design system

**Files to modify/create**:
- `packages/web/src/components/custom/WorkbenchPanel.tsx`

**Acceptance Criteria**:
- [ ] Tabs look polished
- [ ] Active state clear
- [ ] Consistent with design

---

### Task 7: Handle VersionPanel Coordination

**Description**: Coordinate with VersionPanel based on active tab.

**Implementation Details**:
- [ ] Notify parent of active tab changes
- [ ] When Preview tab active, VersionPanel shows page versions
- [ ] When Code/Product Doc tab active, VersionPanel shows empty state
- [ ] Pass selected page info for VersionPanel when in Preview tab

**Files to modify/create**:
- `packages/web/src/components/custom/WorkbenchPanel.tsx`
- `packages/web/src/pages/ProjectPage.tsx`

**Acceptance Criteria**:
- [ ] VersionPanel content matches active tab
- [ ] Smooth coordination between components
- [ ] No race conditions

---

## Technical Specifications

### WorkbenchPanel Props

```typescript
interface WorkbenchPanelProps {
  sessionId: string

  // Active tab management
  activeTab: 'preview' | 'code' | 'product-doc'
  onTabChange: (tab: 'preview' | 'code' | 'product-doc') => void

  // Preview tab props
  pages: Page[]
  selectedPageId: string | null
  onSelectPage: (pageId: string) => void
  previewHtml: string | null
  onExport: () => void
  onRefresh: () => void

  // Product Doc props (passed down)
  productDoc: ProductDoc | null
}
```

### Tab Definition

```typescript
const TABS = [
  { id: 'preview', label: 'Preview' },
  { id: 'code', label: 'Code' },
  { id: 'product-doc', label: 'Product Doc' }
] as const

type TabId = typeof TABS[number]['id']
```

### WorkbenchPanel Component

```tsx
function WorkbenchPanel({
  sessionId,
  activeTab,
  onTabChange,
  pages,
  selectedPageId,
  onSelectPage,
  previewHtml,
  onExport,
  onRefresh,
  productDoc
}: WorkbenchPanelProps) {
  return (
    <div className="workbench-panel">
      <TabBar
        tabs={TABS}
        activeTab={activeTab}
        onTabChange={onTabChange}
      />

      <div className="workbench-content">
        {activeTab === 'preview' && (
          <PreviewPanel
            sessionId={sessionId}
            pages={pages}
            selectedPageId={selectedPageId}
            onSelectPage={onSelectPage}
            previewHtml={previewHtml}
            onExport={onExport}
            onRefresh={onRefresh}
          />
        )}

        {activeTab === 'code' && (
          <CodePanel sessionId={sessionId} />
        )}

        {activeTab === 'product-doc' && (
          <ProductDocPanel sessionId={sessionId} />
        )}
      </div>
    </div>
  )
}
```

### TabBar Component

```tsx
interface TabBarProps {
  tabs: readonly { id: string; label: string }[]
  activeTab: string
  onTabChange: (tab: string) => void
}

function TabBar({ tabs, activeTab, onTabChange }: TabBarProps) {
  return (
    <div className="tab-bar">
      {tabs.map(tab => (
        <button
          key={tab.id}
          className={`tab ${tab.id === activeTab ? 'active' : ''}`}
          onClick={() => onTabChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
```

### Styles

```css
.workbench-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.tab-bar {
  display: flex;
  border-bottom: 1px solid #e0e0e0;
  background: #fafafa;
  padding: 0 8px;
}

.tab {
  padding: 12px 16px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  color: #666;
  position: relative;
  transition: color 0.2s;
}

.tab:hover {
  color: #333;
}

.tab.active {
  color: #1976d2;
  font-weight: 500;
}

.tab.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: #1976d2;
}

.workbench-content {
  flex: 1;
  overflow: hidden;
}
```

### Auto Tab Switching Logic

```typescript
// In ProjectPage or useChat
const [autoSwitchedForProductDoc, setAutoSwitchedForProductDoc] = useState(false)

useEffect(() => {
  // Listen for product_doc_generated event
  const handleProductDocGenerated = () => {
    if (!autoSwitchedForProductDoc) {
      setActiveTab('product-doc')
      setAutoSwitchedForProductDoc(true)
    }
  }

  // Listen for pages_generated event
  const handlePagesGenerated = () => {
    setActiveTab('preview')
  }

  // Subscribe to events
  // ...
}, [autoSwitchedForProductDoc])
```

## Testing Requirements

- [ ] Unit tests for WorkbenchPanel
- [ ] Unit tests for TabBar
- [ ] Test tab switching
- [ ] Test auto tab switching on events
- [ ] Test panel state preservation
- [ ] Test VersionPanel coordination

## Notes & Warnings

- **Performance**: Consider lazy loading Code and ProductDoc tabs
- **State Preservation**: Panels should preserve state when hidden
- **Auto-Switch UX**: Don't auto-switch too aggressively; let user control
- **Memory**: Consider unmounting inactive panels for very large content
- **Responsive**: Ensure tabs work on narrow screens
