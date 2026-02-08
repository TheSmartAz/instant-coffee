# Phase B8: API Endpoints

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Depends on other phases
- **Dependencies**:
  - **Blocked by**: B1 (GraphState), B6 (AssetRegistry)
  - **Blocks**: F1, F2, F3, F4 (Frontend needs APIs)

## Goal

Implement all new REST API endpoints for assets, build status, schemas, and component registry, plus SSE event extensions.

## Detailed Tasks

### Task 1: Create Asset API Endpoints

**Description**: Implement asset upload, list, and delete endpoints

**Implementation Details**:
- [ ] Create `packages/backend/app/api/assets.py`
- [ ] POST /sessions/{session_id}/assets - upload single/multiple files
- [ ] GET /sessions/{session_id}/assets - list all assets
- [ ] GET /sessions/{session_id}/assets/{asset_id} - get asset details
- [ ] DELETE /sessions/{session_id}/assets/{asset_id} - remove asset
- [ ] Query param asset_type: logo/style_ref/background/product_image

**Files to create**:
- `packages/backend/app/api/assets.py`

**Acceptance Criteria**:
- [ ] File upload works with multipart/form-data
- [ ] Asset registry updated on upload
- [ ] Assets served via static file endpoint
- [ ] Proper error handling for invalid files

---

### Task 2: Create Build API Endpoints

**Description**: Implement build trigger, status, and result endpoints

**Implementation Details**:
- [ ] Add to `packages/backend/app/api/build.py` (created in B4)
- [ ] POST /sessions/{session_id}/build - trigger async build
- [ ] GET /sessions/{session_id}/build/status - poll build status
- [ ] GET /sessions/{session_id}/build/logs - get build output
- [ ] DELETE /sessions/{session_id}/build - cancel/stop build

**Files to modify**:
- `packages/backend/app/api/build.py`

**Acceptance Criteria**:
- [ ] Trigger starts async build job
- [ ] Status returns current state and progress
- [ ] Returns build artifacts on success
- [ ] Error details returned on failure

---

### Task 3: Create Schema API Endpoints

**Description**: Implement page schema and component registry retrieval

**Implementation Details**:
- [ ] Add to `packages/backend/app/api/schemas.py` (new)
- [ ] GET /sessions/{session_id}/schemas - list all page schemas
- [ ] GET /sessions/{session_id}/schemas/{page_slug} - get specific page schema
- [ ] GET /sessions/{session_id}/registry - get component registry
- [ ] GET /sessions/{session_id}/tokens - get style tokens

**Files to create**:
- `packages/backend/app/api/schemas.py`

**Acceptance Criteria**:
- [ ] Schemas returned in full
- [ ] Individual page schema accessible
- [ ] Registry includes all components
- [ ] Tokens properly formatted

---

### Task 4: Extend SSE Events

**Description**: Add new event types for LangGraph workflow and build progress

**Implementation Details**:
- [ ] Update `packages/backend/app/events/types.py`
- [ ] Add new SSEEventType values
- [ ] Implement event factory functions
- [ ] Update `packages/backend/app/api/chat.py` to emit new events

**Files to modify**:
- `packages/backend/app/events/types.py`
- `packages/backend/app/api/chat.py`

**Acceptance Criteria**:
- [ ] All workflow events emit: brief_*, style_extracted, registry_*, generate_*, build_*
- [ ] Progress events include step, percent, message
- [ ] Error events include error details and retry_count
- [ ] Frontend can handle all event types

---

### Task 5: Update Router Configuration

**Description**: Register all new API endpoints with FastAPI router

**Implementation Details**:
- [ ] Update `packages/backend/app/api/__init__.py`
- [ ] Include assets router
- [ ] Include build router
- [ ] Include schemas router
- [ ] Update prefix: /sessions/{session_id}

**Files to modify**:
- `packages/backend/app/api/__init__.py`

**Acceptance Criteria**:
- [ ] All endpoints accessible
- [ ] Proper prefix/suffix handling
- [ ] No route conflicts

## Technical Specifications

### Asset Endpoints

```python
from fastapi import APIRouter, UploadFile, File, Query

router = APIRouter(prefix="/sessions/{session_id}/assets", tags=["assets"])

@router.post("")
async def upload_asset(
    session_id: str,
    file: UploadFile = File(...),
    asset_type: str = Query(..., enum=["logo", "style_ref", "background", "product_image"])
) -> AssetRef:
    service = AssetRegistryService(session_id)
    return await service.register_asset(file, asset_type)

@router.get("")
async def list_assets(session_id: str) -> AssetRegistry:
    service = AssetRegistryService(session_id)
    return service.get_registry()
```

### Build Endpoints

```python
@router.post("/build")
async def trigger_build(session_id: str) -> dict:
    """触发异步构建"""
    # Start build in background task
    return {"status": "triggered", "message": "Build started"}

@router.get("/build/status")
async def get_build_status(session_id: str) -> BuildStatus:
    """获取构建状态"""
    # Return current build status
    pass
```

### SSE Event Types

```typescript
type SSEEventType =
  | 'brief_start' | 'brief_complete'
  | 'style_extracted'
  | 'registry_complete'
  | 'generate_start' | 'generate_progress' | 'generate_complete'
  | 'refine_start' | 'refine_complete'
  | 'build_start' | 'build_progress' | 'build_complete' | 'build_failed';

interface SSEEvent<T = any> {
  type: SSEEventType;
  session_id: string;
  timestamp: string;
  payload?: T;
}

interface ProgressPayload {
  step?: string;
  percent?: number;      // 0-100
  message?: string;
  page?: string;
}

interface ErrorPayload {
  error: string;
  retry_count?: number;
}
```

### Schema Endpoints

```python
@router.get("/schemas")
async def get_page_schemas(session_id: str) -> List[PageSchema]:
    """获取所有页面 Schema"""
    pass

@router.get("/schemas/{page_slug}")
async def get_page_schema(session_id: str, page_slug: str) -> PageSchema:
    """获取指定页面 Schema"""
    pass

@router.get("/registry")
async def get_component_registry(session_id: str) -> ComponentRegistry:
    """获取组件注册表"""
    pass
```

## Testing Requirements

- [ ] Unit test: Asset upload with various file types
- [ ] Unit test: Build status polling
- [ ] Integration test: Full asset workflow
- [ ] Integration test: Build trigger and status
- [ ] Test SSE event emission in workflow

## Notes & Warnings

- All endpoints are session-scoped
- File upload size limit: 10MB per file
- Build cancellation should stop subprocess
- SSE events must be serializable
- Rate limiting may be needed later
