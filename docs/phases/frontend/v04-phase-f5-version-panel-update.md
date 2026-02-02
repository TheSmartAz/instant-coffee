# Phase F5: VersionPanel Update for Page Mode

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Low
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: F2 (Preview Panel Multi-Page), F4 (WorkbenchPanel)
  - **Blocks**: None

## Goal

Update the VersionPanel to work in page-specific mode, showing PageVersion history only for the currently selected page in Preview tab, and showing empty state for other tabs.

## Detailed Tasks

### Task 1: Update VersionPanel Props

**Description**: Add new props for page-mode version display.

**Implementation Details**:
- [ ] Add `pageVersions: PageVersion[]` prop for page version history
- [ ] Add `currentPageVersionId: string | null` prop
- [ ] Add `onRevertPageVersion: (versionId: string) => void` prop
- [ ] Add `selectedPageTitle: string | null` prop for display
- [ ] Add `activeTab: string` prop to know which workbench tab is active
- [ ] Keep existing collapse/expand functionality

**Files to modify/create**:
- `packages/web/src/components/custom/VersionPanel.tsx`

**Acceptance Criteria**:
- [ ] New props accepted
- [ ] Existing collapse functionality preserved
- [ ] Type safety enforced

---

### Task 2: Show Page Versions in Preview Tab

**Description**: Display PageVersion history when Preview tab is active.

**Implementation Details**:
- [ ] When activeTab === 'preview', show version list
- [ ] Display page title at top ("当前页面: 首页")
- [ ] List versions with version number, time, and description
- [ ] Mark current version with indicator
- [ ] Show rollback button for non-current versions

**Files to modify/create**:
- `packages/web/src/components/custom/VersionPanel.tsx`

**Acceptance Criteria**:
- [ ] Versions list renders correctly
- [ ] Current version highlighted
- [ ] Rollback buttons visible
- [ ] Page title displayed

---

### Task 3: Show Empty State for Other Tabs

**Description**: Display appropriate empty state when Code or Product Doc tab is active.

**Implementation Details**:
- [ ] When activeTab !== 'preview', show empty state
- [ ] Display message: "本版本仅页面有历史"
- [ ] Keep panel header visible
- [ ] Maintain collapse/expand ability

**Files to modify/create**:
- `packages/web/src/components/custom/VersionPanel.tsx`

**Acceptance Criteria**:
- [ ] Empty state shows for Code tab
- [ ] Empty state shows for Product Doc tab
- [ ] Message is clear
- [ ] Panel still collapsible

---

### Task 4: Implement Rollback Functionality

**Description**: Handle page version rollback action.

**Implementation Details**:
- [ ] When rollback clicked, call `onRevertPageVersion(versionId)`
- [ ] Show confirmation dialog before rollback
- [ ] Show loading state during rollback
- [ ] Refresh version list after rollback
- [ ] Emit success message

**Files to modify/create**:
- `packages/web/src/components/custom/VersionPanel.tsx`
- `packages/web/src/pages/ProjectPage.tsx`

**Acceptance Criteria**:
- [ ] Rollback triggers API call
- [ ] Confirmation prevents accidental rollback
- [ ] UI updates after success
- [ ] Error handling works

---

### Task 5: Connect to Pages Hook

**Description**: Wire VersionPanel to usePages hook for version data.

**Implementation Details**:
- [ ] Create `usePageVersions(pageId)` hook or extend usePages
- [ ] Fetch versions from `GET /api/pages/{pageId}/versions`
- [ ] Call `POST /api/pages/{pageId}/rollback` for rollback
- [ ] Listen for `page_version_created` event to refresh
- [ ] Pass data to VersionPanel

**Files to modify/create**:
- `packages/web/src/hooks/usePageVersions.ts` (new) or `usePages.ts`
- `packages/web/src/pages/ProjectPage.tsx`

**Acceptance Criteria**:
- [ ] Versions fetched for selected page
- [ ] Rollback API call works
- [ ] Events trigger refresh
- [ ] Data flows to VersionPanel

---

### Task 6: Style Updates

**Description**: Update styling for page version display.

**Implementation Details**:
- [ ] Style version list items
- [ ] Add visual indicator for current version (●)
- [ ] Add non-current version indicator (○)
- [ ] Style rollback button
- [ ] Style empty state
- [ ] Style page title header

**Files to modify/create**:
- `packages/web/src/components/custom/VersionPanel.tsx`

**Acceptance Criteria**:
- [ ] Version list visually clean
- [ ] Current version clearly marked
- [ ] Rollback button appropriately styled
- [ ] Consistent with overall design

---

## Technical Specifications

### Updated VersionPanel Props

```typescript
interface VersionPanelProps {
  // Collapse state
  isCollapsed: boolean
  onToggleCollapse: () => void

  // Page version data
  pageVersions: PageVersion[]
  currentPageVersionId: string | null
  onRevertPageVersion: (versionId: string) => void
  selectedPageTitle: string | null

  // Tab state
  activeTab: 'preview' | 'code' | 'product-doc'
}
```

### usePageVersions Hook

```typescript
function usePageVersions(pageId: string | null) {
  return {
    versions: PageVersion[]
    isLoading: boolean
    error: string | null
    revert: (versionId: string) => Promise<void>
    refresh: () => Promise<void>
  }
}
```

### VersionPanel Component

```tsx
function VersionPanel({
  isCollapsed,
  onToggleCollapse,
  pageVersions,
  currentPageVersionId,
  onRevertPageVersion,
  selectedPageTitle,
  activeTab
}: VersionPanelProps) {
  const [revertingId, setRevertingId] = useState<string | null>(null)

  const handleRevert = async (versionId: string) => {
    if (!confirm('确定要回滚到这个版本吗？')) return

    setRevertingId(versionId)
    try {
      await onRevertPageVersion(versionId)
    } finally {
      setRevertingId(null)
    }
  }

  return (
    <div className={`version-panel ${isCollapsed ? 'collapsed' : ''}`}>
      <header className="version-header">
        <span>Versions</span>
        <button onClick={onToggleCollapse}>
          {isCollapsed ? '◀' : '▶'}
        </button>
      </header>

      {!isCollapsed && (
        <div className="version-content">
          {activeTab === 'preview' ? (
            <>
              {selectedPageTitle && (
                <div className="current-page-label">
                  当前页面: {selectedPageTitle}
                </div>
              )}
              <div className="version-list">
                {pageVersions.map(version => (
                  <div
                    key={version.id}
                    className={`version-item ${
                      version.id === currentPageVersionId ? 'current' : ''
                    }`}
                  >
                    <span className="version-indicator">
                      {version.id === currentPageVersionId ? '●' : '○'}
                    </span>
                    <span className="version-number">v{version.version}</span>
                    <span className="version-time">
                      {formatRelativeTime(version.createdAt)}
                    </span>
                    {version.id !== currentPageVersionId && (
                      <button
                        className="rollback-btn"
                        onClick={() => handleRevert(version.id)}
                        disabled={revertingId === version.id}
                      >
                        {revertingId === version.id ? '...' : '回滚'}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="version-empty">
              本版本仅页面有历史
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

### Styles

```css
.version-panel {
  width: 256px;
  border-left: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  transition: width 0.2s;
}

.version-panel.collapsed {
  width: 48px;
}

.version-header {
  padding: 12px;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 500;
}

.version-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.current-page-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e0e0e0;
}

.version-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.version-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 4px;
  font-size: 13px;
}

.version-item.current {
  background: #e3f2fd;
}

.version-indicator {
  color: #1976d2;
}

.version-number {
  font-weight: 500;
}

.version-time {
  color: #666;
  flex: 1;
}

.rollback-btn {
  padding: 4px 8px;
  border: 1px solid #ddd;
  background: white;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.rollback-btn:hover {
  background: #f5f5f5;
}

.version-empty {
  color: #999;
  text-align: center;
  padding: 24px;
  font-size: 14px;
}
```

## Testing Requirements

- [ ] Unit tests for VersionPanel with page versions
- [ ] Unit tests for empty state display
- [ ] Test rollback functionality
- [ ] Test collapse/expand
- [ ] Test current version highlighting
- [ ] Test loading state during rollback

## Notes & Warnings

- **Rollback Confirmation**: Always confirm before destructive action
- **Current Version**: Clear visual distinction is important
- **Performance**: Only fetch versions when Preview tab is active
- **Event Refresh**: Ensure new versions appear after generation
- **Collapsed State**: Maintain collapsed preference across tab switches
