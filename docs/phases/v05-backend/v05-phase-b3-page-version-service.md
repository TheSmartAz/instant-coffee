# Phase v05-B3: PageVersion 服务 - 仅预览不支持回滚

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v05-D1
  - **Blocks**: v05-F3

## Goal

扩展 PageVersion 服务，添加版本预览功能，明确不支持回滚 (回滚仅限 ProjectSnapshot)，实现保留规则和 released 数据清理。

## Detailed Tasks

### Task 1: 版本预览功能

**Description**: 实现指定版本预览功能

**Implementation Details**:
- [ ] 实现 `preview_version(page_id, version_id)` 方法
- [ ] 返回版本内容 (html + description)
- [ ] 仅非 released 版本可预览
- [ ] Released 版本返回 404 或 410 Gone
- [ ] 预览不修改当前页面内容

**Files to modify/create**:
- `packages/backend/app/services/page_version.py`

**Acceptance Criteria**:
- [ ] 预览返回完整的 HTML 内容
- [ ] Released 版本不可预览
- [ ] 预览不影响当前页面
- [ ] 不存在版本返回 404

---

### Task 2: 版本列表与可用性

**Description**: 扩展版本列表包含可用性状态

**Implementation Details**:
- [ ] 修改 `get_versions(page_id)` 方法
- [ ] 返回包含 is_released, is_pinned, source 字段
- [ ] 添加 available 综合状态字段
- [ ] 按版本号倒序排列
- [ ] 默认过滤 released 版本 (可选参数)

**Files to modify/create**:
- `packages/backend/app/services/page_version.py`

**Acceptance Criteria**:
- [ ] 版本列表包含完整状态信息
- [ ] Released 版本可选择性显示
- [ ] Available 状态正确计算

---

### Task 3: Pin/Unpin 页面版本

**Description**: 实现页面版本的 Pin/Unpin 功能

**Implementation Details**:
- [ ] 实现 `pin_version(version_id)` 方法
- [ ] 实现 `unpin_version(version_id)` 方法
- [ ] 检查 pinned 数量限制 (每页面 2 个)
- [ ] 超限时抛出 PinnedLimitExceeded 异常

**Files to modify/create**:
- `packages/backend/app/services/page_version.py`

**Acceptance Criteria**:
- [ ] Pin 成功后 is_pinned=true
- [ ] 超限时抛出特定异常
- [ ] Unpin 成功后 is_pinned=false

---

### Task 4: 保留规则应用

**Description**: 对 PageVersion 应用保留规则

**Implementation Details**:
- [ ] 实现 `apply_retention_policy(page_id)` 方法
- [ ] 识别最近 5 个 source=auto 的非 pinned 版本
- [ ] 识别最多 2 个 pinned 版本
- [ ] 其余标记 is_released=true，设置 released_at
- [ ] 清空 released 版本的 html，设置 payload_pruned_at
- [ ] 记录 fallback_excerpt (如果有)

**Files to modify/create**:
- `packages/backend/app/services/page_version.py`

**Acceptance Criteria**:
- [ ] 保留 5 个最新 auto 版本
- [ ] 保留 2 个 pinned 版本
- [ ] Released 版本 html 清空
- [ ] payload_pruned_at 正确设置

---

### Task 5: 移除回滚功能

**Description**: 明确不支持从 PageVersion 回滚

**Implementation Details**:
- [ ] 移除现有的 `rollback_page(page_id, version_id)` 方法
- [ ] 或明确标记为 deprecated 并抛出 NotImplementedError
- [ ] 更新 API 文档说明回滚仅限 ProjectSnapshot

**Files to modify/create**:
- `packages/backend/app/services/page_version.py`
- `packages/backend/app/api/pages.py`

**Acceptance Criteria**:
- [ ] 调用回滚端点返回 405 Method Not Allowed 或 410 Gone
- [ ] 错误消息引导使用 ProjectSnapshot 回滚
- [ ] 内部测试阶段不考虑兼容策略

---

### Task 6: PageVersion API 端点

**Description**: 更新页面版本相关的 REST API

**Implementation Details**:
- [ ] GET /api/pages/{page_id}/versions - 获取版本列表 (含可用性)
- [ ] GET /api/pages/{page_id}/versions/{version_id}/preview - 预览版本
- [ ] POST /api/pages/{page_id}/versions/{version_id}/pin - Pin
- [ ] POST /api/pages/{page_id}/versions/{version_id}/unpin - Unpin
- [ ] 移除或拒绝 POST /api/pages/{page_id}/rollback

**Files to modify/create**:
- `packages/backend/app/api/pages.py`

**Acceptance Criteria**:
- [ ] 版本列表包含完整状态
- [ ] 预览端点仅对非 released 有效
- [ ] Pin/Unpin 正常工作
- [ ] 旧回滚端点拒绝请求

## Technical Specifications

### API 端点定义

#### GET /api/pages/{page_id}/versions
```python
Response 200:
{
    "versions": [
        {
            "id": 1,
            "version": 3,
            "description": "Added hero section",
            "source": "auto",
            "is_pinned": false,
            "is_released": false,
            "created_at": "iso8601",
            "available": true,
            "previewable": true
        },
        ...
    ]
}
```

#### GET /api/pages/{page_id}/versions/{version_id}/preview
```python
Response 200:
{
    "id": 1,
    "version": 3,
    "html": "<DOCTYPE html>...</html>",
    "description": "Added hero section",
    "fallback_used": false,
    "created_at": "iso8601"
}

Response 410 (Released version):
{
    "error": "version_released",
    "message": "This version has been released and is no longer available for preview"
}
```

#### POST /api/pages/{page_id}/versions/{version_id}/pin
```python
Response 200:
{
    "message": "Pinned successfully",
    "version": {...}
}

Response 409:
{
    "error": "pinned_limit_exceeded",
    "message": "Maximum 2 versions can be pinned per page"
}
```

### 服务接口

```python
class PageVersionService:
    def get_versions(
        self,
        page_id: str,
        include_released: bool = False
    ) -> List[PageVersion]

    def preview_version(self, page_id: str, version_id: int) -> dict:
        """返回可预览的版本内容"""

    def pin_version(self, version_id: int) -> PageVersion

    def unpin_version(self, version_id: int) -> PageVersion

    def apply_retention_policy(self, page_id: str) -> int:
        """返回清理的版本数量"""

    def create_version(
        self,
        page_id: str,
        html: str,
        description: str = "",
        source: Literal["auto", "manual"] = "auto",
        fallback_used: bool = False,
        fallback_excerpt: Optional[str] = None
    ) -> PageVersion
```

## Testing Requirements

- [ ] 单元测试: 预览功能正确返回内容
- [ ] 单元测试: released 版本不可预览
- [ ] 单元测试: 保留规则正确清理 html
- [ ] API 测试: 旧回滚端点拒绝请求
- [ ] 集成测试: pinned 限制生效

## Notes & Warnings

1. **不可回滚**: PageVersion 明确不支持回滚，所有回滚通过 ProjectSnapshot
2. **Released 清理**: html 清空后无法恢复，确保清理前已不需要
3. **Fallback 追踪**: fallback_used 和 fallback_excerpt 用于诊断
4. **Pinned 限制**: 每个页面独立计算 pinned 限制 (2 个)
