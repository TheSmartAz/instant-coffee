# Phase v05-B4: EventStore 服务 - 事件持久化与回放

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v05-D1
  - **Blocks**: v05-F4

## Goal

实现 EventStore 服务，持久化 SSE 结构化事件到 SessionEvent 表，支持历史事件查询和前端事件流恢复。

## Detailed Tasks

### Task 1: EventStoreService 创建

**Description**: 创建事件存储服务核心功能

**Implementation Details**:
- [ ] 创建 `app/services/event_store.py`
- [ ] 实现 `store_event(session_id, type, payload, source)` 方法
- [ ] 生成单调递增 seq (session 内)
- [ ] 仅存储结构化事件，不存储 delta
- [ ] 定义需要存储的事件类型白名单
- [ ] 处理并发写入的 seq 冲突

**Files to modify/create**:
- `packages/backend/app/services/event_store.py` (新建)

**Acceptance Criteria**:
- [ ] 事件成功写入 session_events 表
- [ ] Seq 在 session 内单调递增
- [ ] Delta 事件不被存储
- [ ] 并发写入不会导致 seq 重复

---

### Task 2: 事件类型定义与过滤

**Description**: 定义需要持久化的结构化事件类型

**Implementation Details**:
- [ ] 定义 STRUCTURED_EVENT_TYPES 白名单
- [ ] 包含: interview_question, interview_answer, agent_start, agent_complete, tool_call, tool_result
- [ ] 包含: plan_created, task_started, task_completed, task_failed
- [ ] 包含: version_created, snapshot_created
- [ ] 排除: delta, thinking (流式内容)
- [ ] 实现 `should_store_event(type)` 判断方法

**Files to modify/create**:
- `packages/backend/app/services/event_store.py`
- `packages/backend/app/events/types.py`

**Acceptance Criteria**:
- [ ] 白名单事件正确存储
- [ ] 非白名单事件不存储
- [ ] Delta 事件明确不存储

---

### Task 3: 历史事件查询

**Description**: 实现历史事件查询接口

**Implementation Details**:
- [ ] 实现 `get_events(session_id, since_seq=None)` 方法
- [ ] 按 seq 排序返回
- [ ] 支持 since_seq 过滤 (增量获取)
- [ ] 合并 session/plan/task 来源的事件
- [ ] 返回结构化事件列表

**Files to modify/create**:
- `packages/backend/app/services/event_store.py`

**Acceptance Criteria**:
- [ ] 事件按 seq 顺序返回
- [ ] Since_seq 正确过滤
- [ ] 包含所有来源的事件

---

### Task 4: Chat SSE 事件持久化集成

**Description**: 将 Chat API 的 EventEmitter 接入 EventStore

**Implementation Details**:
- [ ] 修改 `/api/chat` 端点
- [ ] EventEmitter 添加 EventStore 监听器
- [ ] SSE 发送时同步写入 EventStore
- [ ] 仅写入结构化事件
- [ ] 处理写入失败不影响 SSE 发送

**Files to modify/create**:
- `packages/backend/app/api/chat.py`

**Acceptance Criteria**:
- [ ] SSE 事件正确写入数据库
- [ ] SSE 发送不被数据库错误阻塞
- [ ] Delta 事件不被存储

---

### Task 5: 历史事件 API 端点

**Description**: 创建历史事件查询的 REST API

**Implementation Details**:
- [ ] GET /api/sessions/{session_id}/events - 获取历史事件
- [ ] 支持 since_seq 查询参数
- [ ] 返回按 seq 排序的事件列表
- [ ] 包含事件类型和完整 payload

**Files to modify/create**:
- `packages/backend/app/api/events.py` (新建)
- `packages/backend/app/api/__init__.py` - 注册路由

**Acceptance Criteria**:
- [ ] 返回正确的事件列表
- [ ] Since_seq 过滤生效
- [ ] 不包含 delta 事件

---

### Task 6: Seq 生成并发控制

**Description**: 确保(seq)在并发场景下正确递增

**Implementation Details**:
- [ ] 实现安全的 seq 获取机制
- [ ] 使用数据库事务或锁
- [ ] 考虑批量写入的 seq 预分配
- [ ] 处理 seq 间隙 (允许但不影响排序)

**Files to modify/create**:
- `packages/backend/app/services/event_store.py`

**Acceptance Criteria**:
- [ ] 并发写入不产生重复 seq
- [ ] Seq 保持单调递增
- [ ] 少量间隙不影响功能

## Technical Specifications

### API 端点定义

#### GET /api/sessions/{session_id}/events
```python
Query Parameters:
- since_seq: int (optional) - 返回 seq 大于此值的事件
- limit: int (optional, default 1000) - 最大返回数量

Response 200:
{
    "events": [
        {
            "id": 1,
            "seq": 5,
            "type": "interview_question",
            "payload": {
                "question": "What is your product about?",
                "options": [...]
            },
            "source": "session",
            "created_at": "iso8601"
        },
        ...
    ],
    "last_seq": int,
    "has_more": bool
}
```

### 服务接口

```python
class EventStoreService:
    def store_event(
        self,
        session_id: str,
        type: str,
        payload: dict,
        source: Literal["session", "plan", "task"]
    ) -> int:  # 返回 seq

    def should_store_event(self, type: str) -> bool:
        """判断事件类型是否需要存储"""

    def get_events(
        self,
        session_id: str,
        since_seq: Optional[int] = None,
        limit: int = 1000
    ) -> List[SessionEvent]

    def get_next_seq(self, session_id: str) -> int:
        """获取下一个可用的 seq，处理并发"""

    async def store_and_emit(
        self,
        session_id: str,
        type: str,
        payload: dict,
        source: Literal["session", "plan", "task"],
        emitter: EventEmitter
    ):
        """存储事件并同时发送到 SSE"""
```

### 需要持久化的事件类型

```python
STRUCTURED_EVENT_TYPES = {
    # Interview 相关
    "interview_question",
    "interview_answer",

    # Agent 生命周期
    "agent_start",
    "agent_complete",
    "agent_error",

    # Tool 调用
    "tool_call",
    "tool_result",

    # Plan/Task 状态
    "plan_created",
    "plan_updated",
    "task_started",
    "task_completed",
    "task_failed",
    "task_aborted",

    # 版本相关
    "version_created",
    "snapshot_created",
    "history_created",
}

# 不存储的事件类型
EXCLUDED_EVENT_TYPES = {
    "delta",           # 流式内容
    "thinking",        # 内部思考
    "ping",            # 心跳
}
```

## Testing Requirements

- [ ] 单元测试: seq 单调递增
- [ ] 单元测试: 事件类型过滤
- [ ] 并发测试: 多线程写入 seq 正确
- [ ] 集成测试: Chat API 正确写入事件
- [ ] API 测试: 历史事件正确排序

## Notes & Warnings

1. **Delta 不存储**: 流式 delta 仅用于实时展示，不持久化
2. **Seq 间隙**: 允许少量 seq 间隙，不影响事件排序
3. **异步写入**: EventStore 写入不应阻塞 SSE 发送
4. **数据清理**: 考虑旧 session_events 的清理策略
5. **Payload 大小**: 事件 payload 应控制大小，避免存储问题
