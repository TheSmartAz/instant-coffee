# Phase v05-B2: ProductDoc 历史服务 - 历史管理与对比支持

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v05-D1
  - **Blocks**: v05-F2

## Goal

实现 ProductDoc 历史管理服务，包括历史版本创建、查询、Pin/Unpin 功能，支持前端进行任意两版本的 Markdown 对比。

## Detailed Tasks

### Task 1: ProductDoc 历史版本创建

**Description**: 在 ProductDoc 更新时自动创建历史记录

**Implementation Details**:
- [ ] 修改 ProductDocService 的更新方法
- [ ] 在 content/structured 变更时创建 ProductDocHistory 记录
- [ ] 自动递增 version
- [ ] 记录 change_summary (可选传入或自动生成)
- [ ] 设置 source=auto (默认) 或 source=manual
- [ ] 保存到 product_doc_histories 表

**Files to modify/create**:
- `packages/backend/app/services/product_doc.py`

**Acceptance Criteria**:
- [ ] ProductDoc 更新时自动创建历史记录
- [ ] Version 号正确递增
- [ ] Source 正确设置
- [ ] 历史记录内容与更新时一致

---

### Task 2: 历史列表与查询

**Description**: 实现历史版本列表和单个查询方法

**Implementation Details**:
- [ ] 实现 `get_history(product_doc_id, include_released=False)` 方法
- [ ] 实现 `get_history_version(history_id)` 方法
- [ ] 返回包含可用性状态 (is_released, is_pinned) 的元数据
- [ ] 支持按 version 倒序排列
- [ ] 过滤 released 版本 (默认)

**Files to modify/create**:
- `packages/backend/app/services/product_doc.py`

**Acceptance Criteria**:
- [ ] 历史列表按版本倒序
- [ ] 包含所有版本管理字段
- [ ] Released 版本默认过滤
- [ ] 单个查询返回完整内容

---

### Task 3: Pin/Unpin 历史版本

**Description**: 实现历史版本的 Pin/Unpin 功能

**Implementation Details**:
- [ ] 实现 `pin_history(history_id)` 方法
- [ ] 实现 `unpin_history(history_id)` 方法
- [ ] 检查 pinned 数量限制 (最多 2 个)
- [ ] 超限时抛出 PinnedLimitExceeded 异常
- [ ] 返回更新后的历史记录

**Files to modify/create**:
- `packages/backend/app/services/product_doc.py`

**Acceptance Criteria**:
- [ ] Pin 成功后 is_pinned=true
- [ ] 超过 2 个时抛出特定异常
- [ ] Unpin 成功后 is_pinned=false
- [ ] 异常包含当前 pinned 列表

---

### Task 4: 保留规则应用

**Description**: 对 ProductDocHistory 应用保留规则

**Implementation Details**:
- [ ] 实现 `apply_retention_policy(product_doc_id)` 方法
- [ ] 识别最近 5 个 source=auto 的非 pinned 版本
- [ ] 识别最多 2 个 pinned 版本
- [ ] 其余标记 is_released=true
- [ ] **注意**: ProductDocHistory released 后仍保留 content (可查看/对比)
- [ ] 在创建新历史后自动调用

**Files to modify/create**:
- `packages/backend/app/services/product_doc.py`

**Acceptance Criteria**:
- [ ] 保留 5 个最新 auto 版本
- [ ] 保留 2 个 pinned 版本
- [ ] 其余标记 released
- [ ] Released 版本仍保留 content

---

### Task 5: ProductDoc History API 端点

**Description**: 创建历史版本相关的 REST API

**Implementation Details**:
- [ ] GET /api/sessions/{id}/product-doc/history - 获取历史列表
- [ ] GET /api/sessions/{id}/product-doc/history/{history_id} - 获取单个历史
- [ ] POST /api/sessions/{id}/product-doc/history/{history_id}/pin - Pin
- [ ] POST /api/sessions/{id}/product-doc/history/{history_id}/unpin - Unpin
- [ ] 支持跨版本对比的元数据返回

**Files to modify/create**:
- `packages/backend/app/api/product_doc.py`

**Acceptance Criteria**:
- [ ] 历史列表包含所有必要字段
- [ ] 单个历史返回完整 Markdown 内容
- [ ] Pin/Unpin 返回正确状态
- [ ] 超限返回 409 Conflict

## Technical Specifications

### API 端点定义

#### GET /api/sessions/{id}/product-doc/history
```python
Response 200:
{
    "history": [
        {
            "id": 1,
            "version": 3,
            "change_summary": "Updated features section",
            "source": "auto",
            "is_pinned": false,
            "is_released": false,
            "created_at": "iso8601",
            "available": true
        },
        ...
    ],
    "total": int,
    "pinned_count": int
}
```

#### GET /api/sessions/{id}/product-doc/history/{history_id}
```python
Response 200:
{
    "id": 1,
    "version": 3,
    "content": "# Product Doc\n\nFull markdown content...",
    "structured": {...},
    "change_summary": "string",
    "source": "auto",
    "is_pinned": false,
    "is_released": false,
    "created_at": "iso8601"
}
```

### 服务接口

```python
class ProductDocService:
    def create_history(
        self,
        product_doc_id: str,
        content: str,
        structured: dict,
        source: Literal["auto", "manual"] = "auto",
        change_summary: Optional[str] = None
    ) -> ProductDocHistory

    def get_history(
        self,
        product_doc_id: str,
        include_released: bool = False
    ) -> List[ProductDocHistory]

    def get_history_version(self, history_id: int) -> ProductDocHistory

    def pin_history(self, history_id: int) -> ProductDocHistory

    def unpin_history(self, history_id: int) -> ProductDocHistory

    def apply_retention_policy(self, product_doc_id: str) -> int

    # 新增: 对比两个版本的元数据 (前端进行实际 diff)
    def get_versions_for_diff(
        self,
        product_doc_id: str,
        version_a: int,
        version_b: int
    ) -> tuple[ProductDocHistory, ProductDocHistory]
```

## Testing Requirements

- [ ] 单元测试: 历史创建时 version 递增
- [ ] 单元测试: 保留规则计算
- [ ] 单元测试: Pin 超限处理
- [ ] 集成测试: ProductDoc 更新触发历史创建
- [ ] API 测试: 历史列表正确排序和过滤

## Notes & Warnings

1. **Released 保留内容**: ProductDocHistory 与其他版本类型不同，released 后仍保留 content
2. **Version 自增**: version 必须在 ProductDoc 和 ProductDocHistory 同步
3. **Change Summary**: 考虑自动生成 diff 摘要的能力 (可选)
4. **Pinned 冲突**: 需要与 ProjectSnapshot/PageVersion 统一 pinned 限制策略
5. **Diff 在前端**: 后端只返回两个版本内容，前端进行 Markdown diff
