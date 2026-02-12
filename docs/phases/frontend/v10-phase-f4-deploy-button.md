# Phase v10-F4: Deploy Button UI

## Metadata

- **Category**: Frontend
- **Priority**: P0
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v10-F2 (Split ProjectPage), v10-B10 (Deploy Backend)
  - **Blocks**: v10-F5 (QR Code - can share URL)

## Goal

Add deploy button to WorkbenchPanel for one-click deployment.

## Detailed Tasks

### Task 1: Add Deploy button

**Description**: Add deploy dropdown/button to workbench header.

**Implementation Details**:
- [ ] Add button to WorkbenchPanel header
- [ ] Dropdown for provider selection (Netlify/Vercel)
- [ ] Loading state during deployment
- [ ] Show deployed URL on success

**Files to modify**:
- `packages/web/src/components/custom/WorkbenchPanel.tsx`

**UI**:
```
┌─────────────────────────────────┐
│  Workbench          [Deploy ▼] │
├─────────────────────────────────┤
│                                 │
└─────────────────────────────────┘
```

**Acceptance Criteria**:
- [ ] Button visible
- [ ] Deploys successfully

---

### Task 2: Call deploy API

**Description**: Connect button to backend deploy endpoint.

**Implementation Details**:
- [ ] Call POST /api/deploy
- [ ] Handle response
- [ ] Show URL to user

**Files to modify**:
- `packages/web/src/components/custom/WorkbenchPanel.tsx`

**Acceptance Criteria**:
- [ ] API called correctly
- [ ] URL displayed

---

### Task 3: Show deployment history

**Description**: Display past deployments.

**Implementation Details**:
- [ ] List previous deployments
- [ ] Allow reverting

**Files to modify**:
- `packages/web/src/components/custom/WorkbenchPanel.tsx`

**Acceptance Criteria**:
- [ ] History visible

## Technical Specifications

### API Call

```typescript
const deploy = async (sessionId: string, provider: string) => {
  const response = await fetch('/api/deploy', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, provider })
  });
  return response.json();
};
```

### Response

```json
{
  "deploy_url": "https://xxx.netlify.app",
  "status": "ready"
}
```

## Testing Requirements

- [ ] Test button renders
- [ ] Test deployment flow
- [ ] Test error handling

## Notes & Warning

- Feature flag: USE_DEPLOY
- Backend is v10-B10
- Handle network errors gracefully
