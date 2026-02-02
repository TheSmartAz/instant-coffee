# Phase v05-B1: ProjectSnapshot 服务 - 快照创建与回滚

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v05-D1
  - **Blocks**: v05-B4

## Goal

实现 ProjectSnapshot 核心服务，包括自动快照生成、手动快照创建、以及从快照回滚的完整流程，作为系统唯一回滚入口。

## Detailed Tasks

### Task 1: ProjectSnapshotService 基础功能

**Description**: 创建快照服务核心业务逻辑

**Implementation Details**:
- [ ] 创建 `app/services/project_snapshot.py`
- [ ] 实现 `create_snapshot(session_id, source, label=None)` 方法
- [ ] 实现 `get_snapshots(session_id)` 列表方法，包含可用性状态
- [ ] 实现 `get_snapshot(snapshot_id)` 单个查询方法
- [ ] 实现 `snapshot_number` 自增逻辑 (session 内唯一)
- [ ] 支持事务保证快照原子性

**Files to modify/create**:
- `packages/backend/app/services/project_snapshot.py` (新建)

**Acceptance Criteria**:
- [ ] 创建快照时生成唯一 snapshot_number
- [ ] 快照包含当前 ProductDoc 和所有 Pages 的冻结内容
- [ ] 快照列表正确返回可用/释放状态
- [ ] 创建失败时回滚事务

---

### Task 2: 快照自动生成触发

**Description**: 在 Plan 全部成功完成后自动生成快照

**Implementation Details**:
- [ ] 在 Orchestrator 或 TaskExecutor 中监听 Plan 完成事件
- [ ] 仅当所有页面任务成功时触发自动快照
- [ ] 设置 source=auto, label=None
- [ ] 处理并发 Plan 完成的竞态条件

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator.py`
- `packages/backend/app/executor/task_executor.py`

**Acceptance Criteria**:
- [ ] Plan 全部成功时自动生成快照
- [ ] Plan 有失败页面时不生成快照
- [ ] 并发场景下快照生成不重复

---

### Task 3: 快照回滚流程

**Description**: 实现从快照回滚的完整流程

**Implementation Details**:
- [ ] 实现 `rollback_to_snapshot(session_id, snapshot_id)` 方法
- [ ] 读取快照冻结内容 (ProductDoc + Pages)
- [ ] 创建新的 ProductDoc 版本 (content 来自快照)
- [ ] 创建新的 ProductDocHistory 记录
- [ ] 为每个页面创建新的 PageVersion (html 来自快照)
- [ ] 创建新的 ProjectSnapshot (source=rollback)
- [ ] 更新当前 ProductDoc 和 Pages 指向新版本
- [ ] 全流程事务保证

**Files to modify/create**:
- `packages/backend/app/services/project_snapshot.py`

**Acceptance Criteria**:
- [ ] 回滚后内容与快照一致
- [ ] 回滚生成新版本而非复用旧 version_id
- [ ] 回滚快照 source=rollback
- [ ] 回滚失败时部分变更不生效

---

### Task 4: Pin/Unpin 快照

**Description**: 实现快照的 Pin/Unpin 功能

**Implementation Details**:
- [ ] 实现 `pin_snapshot(snapshot_id)` 方法
- [ ] 实现 `unpin_snapshot(snapshot_id)` 方法
- [ ] Pin 时检查是否超过 2 个限制
- [ ] 超限时抛出特定异常 (PinnedLimitExceeded)
- [ ] 返回当前 pinned 列表供前端展示

**Files to modify/create**:
- `packages/backend/app/services/project_snapshot.py`

**Acceptance Criteria**:
- [ ] Pin 成功后 is_pinned=true
- [ ] 超过 2 个 pinned 时抛出异常
- [ ] Unpin 成功后 is_pinned=false
- [ ] Pinned 状态不影响自动快照生成

---

### Task 5: 保留规则计算

**Description**: 实现统一保留规则 (5 自动 + 2 pinned)

**Implementation Details**:
- [ ] 实现 `apply_retention_policy(session_id)` 方法
- [ ] 查询所有快照按 created_at 排序
- [ ] 识别最近 5 个 source=auto 的快照为可用
- [ ] 识别最多 2 个 is_pinned=true 的快照为可用
- [ ] 其余标记 is_released=true
- [ ] Released 快照清空大字段内容 (docs + pages html)
- [ ] 在快照创建后自动调用

**Files to modify/create**:
- `packages/backend/app/services/project_snapshot.py`

**Acceptance Criteria**:
- [ ] 保留 5 个最新 auto 快照
- [ ] 保留 2 个 pinned 快照 (可与 auto 重叠)
- [ ] Released 快照内容清空
- [ ] Pinned 超限时阻止新 pin

---

### Task 6: 快照 API 端点

**Description**: 创建快照相关的 REST API

**Implementation Details**:
- [ ] GET /api/sessions/{id}/snapshots - 获取快照列表
- [ ] GET /api/sessions/{id}/snapshots/{snapshot_id} - 获取单个快照详情
- [ ] POST /api/sessions/{id}/snapshots - 手动创建快照 (source=manual)
- [ ] POST /api/sessions/{id}/snapshots/{snapshot_id}/rollback - 回滚
- [ ] POST /api/sessions/{id}/snapshots/{snapshot_id}/pin - Pin
- [ ] POST /api/sessions/{id}/snapshots/{snapshot_id}/unpin - Unpin

**Files to modify/create**:
- `packages/backend/app/api/snapshots.py` (新建)
- `packages/backend/app/api/__init__.py` - 注册路由

**Acceptance Criteria**:
- [ ] 所有端点返回正确的 HTTP 状态码
- [ ] 快照列表包含可用性状态字段
- [ ] 回滚端点返回新快照信息
- [ ] Pin 超限返回 409 Conflict

## Technical Specifications

### API 端点定义

#### GET /api/sessions/{id}/snapshots
```python
Response 200:
{
    "snapshots": [
        {
            "id": "uuid",
            "snapshot_number": 1,
            "label": "string | null",
            "source": "auto | manual | rollback",
            "is_pinned": bool,
            "is_released": bool,
            "created_at": "iso8601",
            "available": bool,  // 综合状态
            "page_count": int
        }
    ]
}
```

#### POST /api/sessions/{id}/snapshots/{snapshot_id}/rollback
```python
Response 200:
{
    "message": "Rolled back successfully",
    "new_snapshot": {
        "id": "uuid",
        "snapshot_number": 2,
        "source": "rollback",
        ...
    },
    "restored_pages": ["page-id-1", "page-id-2"]
}
```

#### POST /api/sessions/{id}/snapshots/{snapshot_id}/pin
```python
Response 200:
{
    "message": "Pinned successfully",
    "snapshot": {...}
}

Response 409 (Pinned limit exceeded):
{
    "error": "pinned_limit_exceeded",
    "message": "Maximum 2 snapshots can be pinned",
    "current_pinned": ["id-1", "id-2"]
}
```

### 服务接口

```python
class ProjectSnapshotService:
    def create_snapshot(
        self,
        session_id: str,
        source: Literal["auto", "manual", "rollback"],
        label: Optional[str] = None
    ) -> ProjectSnapshot

    def get_snapshots(
        self,
        session_id: str,
        include_released: bool = False
    ) -> List[ProjectSnapshot]

    def get_snapshot(self, snapshot_id: str) -> ProjectSnapshot

    def rollback_to_snapshot(
        self,
        session_id: str,
        snapshot_id: str
    ) -> ProjectSnapshot  # 返回新创建的 rollback 快照

    def pin_snapshot(self, snapshot_id: str) -> ProjectSnapshot

    def unpin_snapshot(self, snapshot_id: str) -> ProjectSnapshot

    def apply_retention_policy(self, session_id: str) -> int  # 返回清理数量
```

## Testing Requirements

- [ ] 单元测试: create_snapshot 生成正确快照
- [ ] 单元测试: rollback_to_snapshot 完整流程
- [ ] 单元测试: 保留规则计算逻辑
- [ ] 集成测试: 快照生成触发时机
- [ ] 集成测试: Pin 超限处理
- [ ] 端到端测试: 完整回滚流程验证

## Notes & Warnings

1. **事务边界**: 快照创建和回滚必须在事务中完成
2. **并发控制**: snapshot_number 生成需要考虑并发，可能需要 SELECT FOR UPDATE
3. **内容冻结**: 快照必须深拷贝内容，不能引用
4. **Rollback 生成新版本**: 回滚不是时间倒流，而是创建新的历史记录
5. **Plan 失败不快照**: 确保只有全部成功才生成自动快照
6. **Released 清理**: 大字段清空考虑异步执行避免阻塞
