# Phase v05-B6: 稳定性修复 - HTML 回退与任务中断

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: None

## Goal

修复已知稳定性问题：HTML 回退模板过度触发、任务中断导致 in_progress 卡死，提升系统可靠性。

## Detailed Tasks

### Task 1: HTML 回退重试机制

**Description**: 在 HTML 抽取失败时实现严格重试

**Implementation Details**:
- [ ] 修改 GenerationAgent 的 HTML 抽取逻辑
- [ ] 抽取失败时执行严格重试 (更严格提示)
- [ ] 考虑降低温度参数重试
- [ ] 最多重试 3 次
- [ ] 记录 fallback_used 标志
- [ ] 记录 fallback_excerpt (原始输出摘要)

**Files to modify/create**:
- `packages/backend/app/agents/generation.py`
- `packages/backend/app/generators/mobile_html.py`

**Acceptance Criteria**:
- [ ] HTML 抽取失败时自动重试
- [ ] 重试使用更严格的提示
- [ ] fallback_used 正确记录
- [ ] fallback_excerpt 记录原始内容片段

---

### Task 2: HTML 回退诊断

**Description**: 增强 HTML 回退可诊断性

**Implementation Details**:
- [ ] PageVersion 新增 fallback_used 和 fallback_excerpt 字段 (v05-D1)
- [ ] 创建版本时设置 fallback_used
- [ ] 失败时保存原始输出摘要
- [ ] 添加日志记录回退原因
- [ ] 提供诊断 API 查看 fallback 统计

**Files to modify/create**:
- `packages/backend/app/agents/generation.py`
- `packages/backend/app/services/page_version.py`

**Acceptance Criteria**:
- [ ] Fallback 使用可追踪
- [ ] 原始输出片段可查看
- [ ] 日志包含足够诊断信息

---

### Task 3: 任务中断处理

**Description**: 实现请求取消时的任务中断逻辑

**Implementation Details**:
- [ ] ParallelExecutor 添加 abort() 方法
- [ ] 监听请求取消事件
- [ ] 取消时调用 executor.abort()
- [ ] 标记运行中任务为 aborted
- [ ] 写入 completed_at 时间戳
- [ ] 取消子任务执行

**Files to modify/create**:
- `packages/backend/app/executor/parallel.py`
- `packages/backend/app/executor/task_executor.py`

**Acceptance Criteria**:
- [ ] 请求取消触发 abort
- [ ] 任务标记为 aborted
- [ ] 子任务正确取消
- [ ] 不留下 in_progress 任务

---

### Task 4: 超时清理策略

**Description**: 实现超时任务的清理机制

**Description**: 实现 in_progress 超时任务的清理

**Implementation Details**:
- [ ] 定义任务超时阈值 (如 30 分钟)
- [ ] 实现超时任务扫描
- [ ] 超时任务标记为 failed 或 aborted
- [ ] 记录超时原因
- [ ] 提供手动重试入口

**Files to modify/create**:
- `packages/backend/app/executor/task_executor.py`
- `packages/backend/app/services/task.py` (新建)

**Acceptance Criteria**:
- [ ] 超时任务自动标记失败
- [ ] 超时原因可追溯
- [ ] 支持手动重试

---

### Task 5: 错误处理增强

**Description**: 统一错误处理和日志记录

**Implementation Details**:
- [ ] 定义明确的错误类型
- [ ] HTML 抽取失败错误
- [ ] 任务超时错误
- [ ] 任务中断错误
- [ ] 统一日志格式
- [ ] 添加错误追踪 ID

**Files to modify/create**:
- `packages/backend/app/exceptions.py` (新建或扩展)
- `packages/backend/app/executor/task_executor.py`

**Acceptance Criteria**:
- [ ] 错误类型清晰
- [ ] 日志包含足够信息
- [ ] 支持错误追踪

## Technical Specifications

### 任务状态扩展

```python
class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"  # 新增
    TIMEOUT = "timeout"  # 新增
```

### Executor 接口

```python
class ParallelExecutor:
    def abort(self):
        """中断所有运行中的任务"""

    def cleanup_timeout_tasks(self, timeout_minutes: int = 30):
        """清理超时任务"""
```

### HTML 抽取重试逻辑

```python
def extract_html_with_retry(response: str, max_retries: int = 3) -> dict:
    """
    重试 HTML 抽取，每次使用更严格的提示
    返回: {
        "html": str | None,
        "fallback_used": bool,
        "fallback_excerpt": str | None
    }
    """
```

## Testing Requirements

- [ ] 单元测试: HTML 重试逻辑
- [ ] 单元测试: 任务 abort 功能
- [ ] 单元测试: 超时清理
- [ ] 集成测试: 请求取消流程
- [ ] 集成测试: 超时任务清理

## Notes & Warnings

1. **重试次数**: 不要过度重试，避免浪费 token
2. **超时阈值**: 根据实际任务时长调整
3. **级联取消**: 父任务取消时应取消所有子任务
4. **状态一致**: 确保 aborted 任务有 completed_at
5. **回降诊断**: fallback_excerpt 限制长度避免存储问题
