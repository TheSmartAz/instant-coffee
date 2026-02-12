# Phase v10-B10: One-Click Deployment Service

## Metadata

- **Category**: Backend
- **Priority**: P0
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v10-F2 (Split ProjectPage - frontend must be ready)
  - **Blocks**: v10-F4 (Deploy Button UI)

## Goal

Create deployment service for one-click publish to Netlify/Vercel.

## Detailed Tasks

### Task 1: Create DeployService

**Description**: Service for deploying to Netlify/Vercel.

**Implementation Details**:
- [ ] Create packages/backend/app/services/deploy.py
- [ ] Implement deploy() method
- [ ] Support Netlify API
- [ ] Support Vercel CLI

**Files to create**:
- `packages/backend/app/services/deploy.py`

**Acceptance Criteria**:
- [ ] Successfully deploys to provider

---

### Task 2: Create deploy API endpoint

**Description**: REST API for triggering deployments.

**Implementation Details**:
- [ ] Create packages/backend/app/api/deploy.py
- [ ] POST /api/deploy endpoint
- [ ] Accept session_id and provider
- [ ] Return deploy_url

**Files to create**:
- `packages/backend/app/api/deploy.py`

**Acceptance Criteria**:
- [ ] Endpoint accepts deployment requests

---

### Task 3: Save deployment history

**Description**: Track deployment in database.

**Implementation Details**:
- [ ] Save to deployments table
- [ ] Link to session and version
- [ ] Support rollback

**Files to modify**:
- `packages/backend/app/services/deploy.py`

**Acceptance Criteria**:
- [ ] History persisted

## Technical Specifications

### API Contract

**Request**:
```json
{
  "session_id": "xxx",
  "provider": "netlify"  // or "vercel"
}
```

**Response**:
```json
{
  "deploy_url": "https://xxx.netlify.app",
  "status": "ready"
}
```

### Deploy Flow

```
1. Collect files from session
2. Call provider API
3. Save deployment record
4. Return URL
```

## Testing Requirements

- [ ] Test Netlify deployment
- [ ] Test Vercel deployment
- [ ] Test deployment history

## Notes & Warnings

- Requires API keys for providers
- Feature flag: USE_DEPLOY
- Consider rate limiting
