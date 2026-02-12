# Phase v10-F1: Zustand State Management

## Metadata

- **Category**: Frontend
- **Priority**: P0
- **Estimated Complexity**: High
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: v10-F2 (Split ProjectPage)

## Goal

Replace props drilling with Zustand global state management.

## Detailed Tasks

### Task 1: Install Zustand

**Description**: Add Zustand to web dependencies.

**Implementation Details**:
- [ ] Run `npm install zustand`
- [ ] Verify installation

**Files to modify**:
- `packages/web/package.json`

**Acceptance Criteria**:
- [ ] Zustand installed

---

### Task 2: Create Store Slices

**Description**: Create Zustand stores for each domain.

**Implementation Details**:
- [ ] Create sessionStore
- [ ] Create chatStore
- [ ] Create previewStore
- [ ] Create pagesStore
- [ ] Create productDocStore
- [ ] Create buildStore
- [ ] Create versionStore

**Files to create**:
- `packages/web/src/store/sessionStore.ts`
- `packages/web/src/store/chatStore.ts`
- `packages/web/src/store/previewStore.ts`
- `packages/web/src/store/pagesStore.ts`
- `packages/web/src/store/productDocStore.ts`
- `packages/web/src/store/buildStore.ts`
- `packages/web/src/store/versionStore.ts`
- `packages/web/src/store/index.ts`

**Acceptance Criteria**:
- [ ] All stores created
- [ ] Types defined

---

### Task 3: Create index export

**Description**: Unified store exports.

**Implementation Details**:
- [ ] Create index.ts with all exports
- [ ] Export store hooks

**Files to create**:
- `packages/web/src/store/index.ts`

**Acceptance Criteria**:
- [ ] Easy importing

---

### Task 4: Convert existing hooks

**Description**: Make existing hooks use Zustand.

**Implementation Details**:
- [ ] Convert useSession
- [ ] Convert usePages
- [ ] Convert useChat
- [ ] Convert other hooks

**Files to modify**:
- `packages/web/src/hooks/useSession.ts`
- `packages/web/src/hooks/usePages.ts`
- `packages/web/src/hooks/useChat.ts`
- Other hooks

**Implementation**:
```typescript
// Before
export function useSession() {
  const [session, setSession] = useState(null);
  // ...
}

// After
export const useSession = () => useSessionStore((state) => state.session);
export const useSetSession = () => useSessionStore((state) => state.setSession);
```

**Acceptance Criteria**:
- [ ] Hooks become thin wrappers

## Technical Specifications

### Store Structure Example

```typescript
interface SessionStore {
  session: Session | null;
  loading: boolean;
  error: string | null;
  setSession: (session: Session) => void;
  updateSession: (updates: Partial<Session>) => void;
  clearSession: () => void;
}
```

### Store Organization

| Store | State |
|-------|-------|
| sessionStore | currentSession, loading, error |
| chatStore | messages, pending, input |
| previewStore | html, loading, error |
| pagesStore | pages, currentPage |
| productDocStore | doc, loading |
| buildStore | status, progress |
| versionStore | versions, current |

## Testing Requirements

- [ ] Test store creation
- [ ] Test state updates
- [ ] Test selectors

## Notes & Warnings

- Feature flag: USE_ZUSTAND (default off during transition)
- Keep backward compatibility
- Don't over-split stores
