# Phase B4: React SSG Build Pipeline

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Very High
- **Parallel Development**: ⚠️ Can start (independent)
- **Dependencies**:
  - **Blocked by**: O1 (React SSG Template must exist first)
  - **Blocks**: B8 (Build API needs this)

## Goal

Implement the complete React SSG build pipeline that transforms page schemas into static HTML files using Vite + React.

## Detailed Tasks

### Task 1: Create ReactSSGBuilder Class

**Description**: Implement the core build orchestrator that manages template copying, file generation, and npm build

**Implementation Details**:
- [ ] Create `packages/backend/app/renderer/builder.py`
- [ ] Implement ReactSSGBuilder class with TEMPLATE_PATH
- [ ] Add build(page_schemas, component_registry, style_tokens, assets) method
- [ ] Handle template copying and cleanup
- [ ] Execute npm install and npm run build

**Files to create**:
- `packages/backend/app/renderer/__init__.py`
- `packages/backend/app/renderer/builder.py`

**Acceptance Criteria**:
- [ ] Template copied to work_dir
- [ ] npm install succeeds
- [ ] npm run build succeeds
- [ ] dist/ moved to session dist_dir

---

### Task 2: Implement Schema File Generation

**Description**: Write page schemas, component registry, and style tokens to template project

**Implementation Details**:
- [ ] Create `packages/backend/app/renderer/file_generator.py`
- [ ] Generate `src/data/schemas.json` from page_schemas
- [ ] Generate `src/data/tokens.json` from style_tokens
- [ ] Generate `src/data/registry.json` from component_registry
- [ ] Create page components from page_schemas

**Files to create**:
- `packages/backend/app/renderer/file_generator.py`

**Acceptance Criteria**:
- [ ] All JSON files valid and parseable
- [ ] Page components generated correctly
- [ ] Assets copied to public/assets/

---

### Task 3: Implement Render Node

**Description**: Create render_node that executes build pipeline and handles build status

**Implementation Details**:
- [ ] Create `packages/backend/app/graph/nodes/render.py`
- [ ] Implement render_node(state) async function
- [ ] Read page_schemas and component_registry from state
- [ ] Call ReactSSGBuilder.build()
- [ ] Update build_status and build_artifacts in state
- [ ] Handle build errors gracefully

**Files to create**:
- `packages/backend/app/graph/nodes/render.py`

**Acceptance Criteria**:
- [ ] Build status transitions: pending -> building -> success/failed
- [ ] SSE events emitted for build progress
- [ ] Error details captured in state.error

---

### Task 4: Implement Build Status API

**Description**: Create API endpoints for build status polling and results

**Implementation Details**:
- [ ] Add to `packages/backend/app/api/chat.py` or new `packages/backend/app/api/build.py`
- [ ] GET /sessions/{session_id}/build/status
- [ ] POST /sessions/{session_id}/build (trigger build)
- [ ] Return BuildStatus response with pages list

**Files to modify/create**:
- `packages/backend/app/api/build.py` (new)

**Acceptance Criteria**:
- [ ] Build status returns correct state
- [ ] Trigger build starts async build
- [ ] Response includes pages list

## Technical Specifications

### ReactSSGBuilder Class

```python
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Optional

class ReactSSGBuilder:
    TEMPLATE_PATH = Path(__file__).parent / "templates" / "react-ssg"

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.work_dir = Path(f"~/.instant-coffee/sessions/{session_id}/build").expanduser()
        self.dist_dir = Path(f"~/.instant-coffee/sessions/{session_id}/dist").expanduser()

    async def build(
        self,
        page_schemas: List[dict],
        component_registry: dict,
        style_tokens: dict,
        assets: dict
    ) -> dict:
        """执行 React SSG 构建"""
        # 1. 复制模板
        if self.work_dir.exists():
            shutil.rmtree(self.work_dir)
        shutil.copytree(self.TEMPLATE_PATH, self.work_dir)

        # 2. 写入配置
        (self.work_dir / "src/data/schemas.json").write_text(
            json.dumps(page_schemas, ensure_ascii=False, indent=2)
        )
        (self.work_dir / "src/data/tokens.json").write_text(
            json.dumps(style_tokens, ensure_ascii=False, indent=2)
        )
        (self.work_dir / "src/data/registry.json").write_text(
            json.dumps(component_registry, ensure_ascii=False, indent=2)
        )

        # 3. 复制资产
        assets_dir = self.work_dir / "public/assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        for asset in assets.get("files", []):
            shutil.copy(asset["path"], assets_dir / asset["filename"])

        # 4. 安装依赖 & 构建
        install_cmd = ["npm", "ci"] if (self.work_dir / "package-lock.json").exists() else ["npm", "install"]
        result = subprocess.run(install_cmd, cwd=self.work_dir, capture_output=True, text=True)
        if result.returncode != 0:
            raise BuildError(f"npm install failed: {result.stderr}")

        result = subprocess.run(["npm", "run", "build"], cwd=self.work_dir, capture_output=True, text=True)
        if result.returncode != 0:
            raise BuildError(f"Build failed: {result.stderr}")

        # 5. 移动 dist
        build_dist = self.work_dir / "dist"
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
        shutil.move(build_dist, self.dist_dir)

        return {
            "status": "success",
            "dist_path": str(self.dist_dir),
            "pages": [p.name for p in self.dist_dir.rglob("*.html")]
        }
```

### Build Status Schema

```python
from typing import List, Optional
from pydantic import BaseModel

class BuildStatus(BaseModel):
    status: str  # pending / building / success / failed
    pages: Optional[List[str]] = None
    dist_path: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
```

### Storage Structure

```
~/.instant-coffee/
├── sessions/
│   └── {session_id}/
│       ├── build/              # 构建工作目录（临时）
│       ├── dist/               # 构建产物（托管）
│       │   ├── index.html
│       │   ├── pages/
│       │   └── assets/
│       ├── assets/             # 用户上传的资产
│       ├── schemas/            # 页面 Schema JSON
│       └── session.db          # 会话元数据
└── templates/
    └── react-ssg/              # 构建模板（只读）
```

## Testing Requirements

- [ ] Unit test: Template copying and cleanup
- [ ] Unit test: JSON file generation
- [ ] Integration test: Full build with simple page
- [ ] Integration test: Multi-page ecommerce scenario
- [ ] Performance test: Build time < 30 seconds

## Notes & Warnings

- **Dependency**: Requires O1 React SSG Template first
- Node.js must be available in PATH
- npm packages may take time to install (consider caching)
- Build errors should be captured for debugging
- Mobile Shell post-processing runs after build
