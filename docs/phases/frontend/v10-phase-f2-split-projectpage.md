# Phase v10-F2: Split ProjectPage

## Metadata

- **Category**: Frontend
- **Priority**: P0
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v10-F1 (Zustand State)
  - **Blocks**: v10-F4 (Deploy Button), v10-B10 (Deploy Backend - needs UI)

## Goal

Refactor ProjectPage from 573 lines to under 100 lines using container components.

## Detailed Tasks

### Task 1: Create Container Components

**Description**: Create reusable container components.

**Implementation Details**:
- [ ] Create ProjectLayout
- [ ] Create ChatContainer
- [ ] Create WorkbenchContainer
- [ ] Create VersionSidebar

**Files to create**:
- `packages/web/src/components/layout/ProjectLayout.tsx`
- `packages/web/src/components/container/ChatContainer.tsx`
- `packages/web/src/components/container/WorkbenchContainer.tsx`
- `packages/web/src/components/container/VersionSidebar.tsx`

**Acceptance Criteria**:
- [ ] All containers created

---

### Task 2: Refactor ProjectPage

**Description**: Simplify ProjectPage to use containers.

**Implementation Details**:
- [ ] Import containers
- [ ] Remove inline logic
- [ ] Use Zustand stores

**Files to modify**:
- `packages/web/src/pages/ProjectPage.tsx`

**Implementation**:
```typescript
// Target: < 100 lines
export default function ProjectPage() {
  const session = useSession();

  return (
    <ProjectLayout>
      <div className="flex-1 flex">
        <ChatContainer />
        <WorkbenchContainer />
      </div>
      <VersionSidebar />
    </ProjectLayout>
  );
}
```

**Acceptance Criteria**:
- [ ] ProjectPage < 100 lines
- [ ] Each container works independently
- [ ] State from Zustand

---

### Task 3: Split WorkbenchContainer

**Description**: Split workbench into tab panels.

**Implementation Details**:
- [ ] PreviewPanel
- [ ] CodePanel
- [ ] ProductDocPanel
- [ ] DataTab

**Files to create/modify**:
- `packages/web/src/components/container/WorkbenchContainer.tsx`

**Acceptance Criteria**:
- [ ] Tabs work correctly

## Technical Specifications

### Component Hierarchy

```
ProjectPage (< 100 lines)
├── ProjectLayout
│   └── Navigation
├── ChatContainer
│   ├── ChatPanel
│   └── InterviewWidget
├── WorkbenchContainer
│   ├── PreviewPanel
│   ├── CodePanel
│   ├── ProductDocPanel
│   └── DataTab
└── VersionSidebar
```

### Props Flow

- All data from Zustand stores
- No props drilling
- Containers subscribe to relevant store

## Testing Requirements

- [ ] Test ProjectPage renders
- [ ] Test containers work independently
- [ ] Test line count < 100

## Notes & Warning

- Must complete v10-F1 first
- Keep backward compatibility during transition
- Test thoroughly - this is a major refactor
