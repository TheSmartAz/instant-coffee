# Instant Coffee - 技术规格说明书 (Spec v0.8.2)

**项目名称**: Instant Coffee (速溶咖啡)  
**版本**: v0.8.2 - Run-Centric Backend Refactor + 可恢复执行 + 事件模型升级 + 工具策略钩子 + Verify Gate + App Data Layer  
**日期**: 2026-02-06  
**文档类型**: Technical Specification Document (Backend First)

---

## 文档变更历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v0.8.2 | 2026-02-06 | 统一版本与 API 前缀；明确 Run 状态机/并发语义；补全 Run API 错误码与幂等；补全事件必填契约与 seq 语义；增强 App Data 安全与模型演进策略 | Planning |
| v0.8.1 | 2026-02-06 | 新增 App Data Layer：PG Schema 隔离动态建表、CRUD API、Data Tab 前端改造 | Planning |
| v0.8 | 2026-02-06 | 基于 v0.7.1 规划后端改造：Run 一等对象、事件 run 维度、Run API、可恢复与中断、工具策略钩子、Verify Gate | Planning |
| v0.7.1 | 2026-02-05 | LangGraph 编排 + React SSG 多文件产物 + 场景旅程能力 + 组件一致性 + Mobile Shell 自动修复 | Planning |

---

## 目录

1. [版本概述](#1-版本概述)
2. [范围与非目标](#2-范围与非目标)
3. [设计决策记录](#3-设计决策记录)
4. [现状对齐（基于 v0.7.1）](#4-现状对齐基于-v071)
5. [目标架构（Run-Centric）](#5-目标架构run-centric)
6. [数据模型与迁移](#6-数据模型与迁移)
7. [事件模型升级](#7-事件模型升级)
8. [API 设计（新增 Run API）](#8-api-设计新增-run-api)
9. [编排改造（LangGraph + Verify Gate）](#9-编排改造langgraph--verify-gate)
10. [工具策略钩子（Tool Policy Hooks）](#10-工具策略钩子tool-policy-hooks)
11. [兼容策略（保持 /api/chat 不破坏）](#11-兼容策略保持-apichat-不破坏)
12. [实施拆分（Backend 优先）](#12-实施拆分backend-优先)
13. [文件变更清单](#13-文件变更清单)
14. [验收标准](#14-验收标准)
15. [风险与回滚](#15-风险与回滚)
16. [App Data Layer](#16-app-data-layer)

---

## 1. 版本概述

### 1.1 版本定位

Spec v0.8.2 是 **后端基础设施升级版本**，目标是把当前“会话内一次聊天生成”升级为“可治理的运行单元（Run）”。

核心目标：
1. **Run 一等对象化**：每次执行都有 run_id、状态机、可查询生命周期。
2. **可恢复执行标准化**：统一中断/恢复与 checkpoint 语义。
3. **事件可审计**：事件按 `session_id + run_id + seq` 组织与回放。
4. **安全与治理前置**：工具调用增加策略钩子（pre/post），支持拦截与审计。
5. **生成质量门禁**：在 render 前增加 Verify Gate（lint/build/mobile guardrails）。

### 1.2 与 v0.7.1 的关系

| 维度 | v0.7.1 | v0.8.2 |
|------|--------|------|
| 编排主体 | LangGraph 工作流 | 保持 LangGraph，新增 Run 生命周期层 |
| 恢复能力 | 已有 `resume` + checkpointer | 统一为 Run API + 标准状态机 |
| 事件粒度 | session 级为主 | run 级主导（session 级兼容） |
| 工具调用 | 已有 tool_call/tool_result | 增加策略拦截与审计事件 |
| 生成出口 | 直接 render | generate/refine 后先过 Verify Gate |

---

## 2. 范围与非目标

### 2.1 本期包含（Backend）

- Run 数据模型与状态机
- Run API（create/query/resume/cancel/events）
- `session_events` 增强（run_id 维度）
- 编排接入 Run（LangGraph 执行与 checkpoint 对齐）
- 工具策略钩子（命令、路径、敏感信息）
- Verify Gate 节点与事件
- `/api/chat` 与 `/api/chat/stream` 兼容适配
- App Data Layer：PG Schema 隔离动态建表、CRUD API、前端 Data Tab 改造

### 2.2 本期不包含

- 前端大改版（仅做最小类型对齐与订阅切换）
- 新场景能力扩展（电商/旅行/看板等沿用 v0.7.1）
- 权限系统（RBAC）与多租户
- 云端分布式任务队列（保留后续演进空间）

---

## 3. 设计决策记录

| 问题 | 决策 | 说明 |
|------|------|------|
| 执行主键 | 引入 `run_id` | session 下可有多次执行，run 是最小可审计单元 |
| 状态管理 | 显式 Run 状态机 | queued/running/waiting_input/completed/failed/cancelled |
| 事件组织 | run 维度优先 | 新产生的结构化事件必须带 run_id；旧事件兼容 |
| 恢复入口 | 统一 Run Resume API | `Command(resume=...)` 由 run 服务层封装 |
| 工具安全 | BaseAgent 外挂策略钩子 | 不改业务工具实现，统一在调用包裹层治理 |
| 质量保障 | Verify Gate 前置 | 未通过不进入 render/build 完成态 |

---

## 4. 现状对齐（基于 v0.7.1）

当前基础（已具备）：
- LangGraph 编排与状态：`packages/backend/app/graph/graph.py`
- Graph 运行态已有 `run_id` 字段：`packages/backend/app/graph/state.py`
- Checkpointer 支持 memory/sqlite/postgres：`packages/backend/app/graph/checkpointer.py`
- MCP 工具加载节点：`packages/backend/app/graph/nodes/mcp_setup.py`
- 事件持久化与 seq 回放：`packages/backend/app/services/event_store.py`、`packages/backend/app/api/events.py`
- Chat 请求已有 `resume` 字段：`packages/backend/app/schemas/chat.py`

当前痛点：
1. 执行生命周期缺少 Run 一等资源（状态和控制面分散在 chat 流程内）。
2. 事件虽可回放，但 run 维度缺失，跨次执行分析与回放成本高。
3. 工具调用安全控制点不足，难以统一执行策略与审计。
4. render/build 前缺少强验证门禁，失败暴露偏后置。

---

## 5. 目标架构（Run-Centric）

### 5.1 架构总览

```
Client
  ├─ POST /api/runs
  ├─ POST /api/runs/{run_id}/resume
  ├─ POST /api/runs/{run_id}/cancel
  └─ GET  /api/runs/{run_id}/events (SSE/poll)

Run Service
  ├─ create_run()
  ├─ start_run()
  ├─ resume_run()
  ├─ cancel_run()
  └─ persist_run_state()

LangGraph Orchestrator
  ├─ brief/style/registry/generate
  ├─ refine_gate/refine
  ├─ verify (new)
  └─ render

Event Store
  └─ session_events(session_id, run_id, seq, type, payload, source)
```

### 5.2 Run 状态机

```
queued
  ↓
running
  ├─→ waiting_input ─→ running
  ├─→ failed
  ├─→ cancelled
  └─→ completed
```

状态语义：
- `queued`: 已创建，待执行。
- `running`: 图执行中。
- `waiting_input`: 命中 interrupt，等待用户反馈。
- `completed`: 通过 verify 并完成 render。
- `failed`: 不可恢复异常或验证失败且无重试路径。
- `cancelled`: 用户主动终止。

补充语义：
- `resumed` 是事件（`run_resumed`），不是持久化状态。
- 从 `waiting_input` 恢复后必须回到 `running`，且沿用同一个 `run_id`。
- 每个 run 只能有一个活跃执行实例；并发恢复请求按幂等策略拒绝或合并。

---

## 6. 数据模型与迁移

### 6.1 新增表：`session_runs`

```sql
session_runs (
  id                VARCHAR PRIMARY KEY,     -- run_id (uuid hex)
  session_id        VARCHAR NOT NULL,
  parent_run_id     VARCHAR NULL,
  trigger_source    VARCHAR(20) NOT NULL,    -- chat | resume | retry | system
  status            VARCHAR(20) NOT NULL,    -- queued/running/waiting_input/completed/failed/cancelled
  input_message     TEXT NULL,
  resume_payload    JSON NULL,
  checkpoint_thread VARCHAR NULL,            -- 默认 session_id:run_id，避免并发 run 冲突
  checkpoint_ns     VARCHAR NULL,
  latest_error      JSON NULL,
  metrics           JSON NULL,               -- token/cost/duration
  started_at        DATETIME NULL,
  finished_at       DATETIME NULL,
  created_at        DATETIME NOT NULL,
  updated_at        DATETIME NOT NULL
)
```

索引：
- `idx_session_runs_session_created(session_id, created_at)`
- `idx_session_runs_status(status)`
- `idx_session_runs_parent(parent_run_id)`

### 6.2 扩展表：`session_events`

在现有字段上新增：
- `run_id VARCHAR NULL`
- `event_id VARCHAR NULL`（可选，幂等去重备用）

新增索引：
- `idx_session_event_run_seq(session_id, run_id, seq)`

兼容策略：
- 历史数据 `run_id = NULL` 保留。
- 新事件默认写入 run_id。

### 6.3 迁移入口

在 `packages/backend/app/db/migrations.py` 增加 v0.8 迁移函数：
- `migrate_v08_run_model()`
- `migrate_v08_event_run_columns()`

---

## 7. 事件模型升级

### 7.1 新增事件类型

在 `packages/backend/app/events/types.py` 增加：

```text
run_created
run_started
run_waiting_input
run_resumed
run_completed
run_failed
run_cancelled
verify_start
verify_pass
verify_fail
tool_policy_blocked
tool_policy_warn
```

### 7.2 统一事件信封

所有结构化事件采用统一信封，字段要求如下：

- 必填：`type`、`timestamp`、`session_id`、`seq`、`source`。
- run 范围事件必填：`run_id`（即 run 生命周期事件、verify 事件、tool policy 事件）。
- 建议：`event_id`（用于跨系统幂等去重/追踪）。
- `payload` 保持对象结构，避免混合字符串与对象格式。

示例：

```json
{
  "type": "run_started",
  "timestamp": "2026-02-06T10:00:00Z",
  "session_id": "...",
  "run_id": "...",
  "seq": 101,
  "source": "session",
  "payload": {"phase": "langgraph"}
}
```

### 7.3 事件回放规范

- 默认按 `seq ASC` 回放。
- 新增 run 维度过滤：`GET /api/runs/{run_id}/events?since_seq=`。
- `GET /api/sessions/{session_id}/events` 保持可用，作为聚合视图。

`seq` 语义约定：
- `seq` 是 **session 级单调递增序号**（全局有序）。
- run 维度查询依然返回原始 `seq`，不单独重编 run 内序号。
- run 内顺序通过 `ORDER BY seq ASC` 获取。

---

## 8. API 设计（新增 Run API）

### 8.1 创建 Run

`POST /api/runs`

请求体：
```json
{
  "session_id": "...",
  "message": "...",
  "generate_now": false,
  "style_reference": {},
  "target_pages": []
}
```

响应：
```json
{
  "run_id": "...",
  "session_id": "...",
  "status": "queued"
}
```

### 8.2 查询 Run

`GET /api/runs/{run_id}`

返回：状态、开始结束时间、错误、token 统计、最新 checkpoint 信息。

建议补充返回字段：
- `status`, `started_at`, `finished_at`, `latest_error`, `metrics`
- `checkpoint_thread`, `checkpoint_ns`
- `waiting_reason`（当 `status=waiting_input` 时）

### 8.3 恢复 Run

`POST /api/runs/{run_id}/resume`

请求体：
```json
{
  "resume": {
    "user_feedback": "请把主按钮改成深色"
  }
}
```

### 8.4 取消 Run

`POST /api/runs/{run_id}/cancel`

行为：置 `cancelled`，并向图执行发协作取消信号。

幂等约束：
- `completed/failed/cancelled` 再次 cancel 返回 200（幂等），状态不变。
- `waiting_input/running/queued` cancel 返回 202（接受请求），最终收敛 `cancelled`。

### 8.5 Run 事件流

`GET /api/runs/{run_id}/events?since_seq=123&limit=1000`

支持：
- SSE 流式
- JSON 轮询

协商规则：
- `Accept: text/event-stream` 返回 SSE。
- `Accept: application/json`（或无 Accept）返回 JSON。

错误码约定（Run API）：
- `400`：参数非法（如 `limit` 越界、resume payload 非法）。
- `404`：run 不存在或 run 与 session 不匹配。
- `409`：状态冲突（如非 waiting_input 状态执行 resume）。
- `422`：验证失败（schema 通过但语义不满足）。
- `500`：服务内部错误。

幂等键建议：
- `POST /api/runs`、`POST /api/runs/{run_id}/resume` 支持 `Idempotency-Key`。
- 相同键在幂等窗口（建议 24h）内返回同一语义结果。

---

## 9. 编排改造（LangGraph + Verify Gate）

### 9.1 GraphState 扩展

在 `packages/backend/app/graph/state.py` 增加：
- `run_status: str`
- `verify_report: Optional[dict]`
- `verify_blocked: Optional[bool]`
- `current_node: Optional[str]`

### 9.2 节点拓扑调整

当前：
`... -> generate -> (aesthetic) -> refine_gate -> refine -> render`

改造后：
`... -> generate -> (aesthetic) -> refine_gate -> refine -> verify -> render`

规则：
- verify pass 才允许进入 render。
- verify fail 触发 `verify_fail`，并进入：
  - 自动修复分支（可选）或
  - `waiting_input` 请求人工反馈。

Verify Gate 最小检查集（v0.8.2）：
1. 构建检查：React SSG 构建可完成（无致命构建错误）。
2. 结构检查：关键页面存在（至少 index），关键入口节点存在（`#app` 等）。
3. 移动端检查：viewport/meta 与 mobile shell 约束满足。
4. 安全检查：禁止明显敏感信息泄露（token/key/secret 模式）。

失败策略：
- 第一次 fail：写入 `verify_report`，触发 `verify_fail` 事件。
- 若启用自动修复：最多重试 1 次 verify。
- 重试后仍 fail：run 进入 `waiting_input`（可恢复）或 `failed`（不可恢复错误）。

### 9.3 中断与恢复

- 保持 `interrupt()` + `Command(resume=...)` 模式。
- RunService 负责把 resume payload 注入图恢复命令，并更新 run 状态。

---

## 10. 工具策略钩子（Tool Policy Hooks）

### 10.1 接入点

在 `packages/backend/app/agents/base.py` 的 `_wrap_tool_handler()` 前后插入：
- `pre_tool_use(policy_context)`
- `post_tool_use(policy_context, result)`

### 10.2 默认策略（v0.8.2）

1. 命令白名单（shell 类工具）
2. 路径边界限制（禁止越界到项目外）
3. 敏感内容检测（token/key/secret）
4. 大输出截断与审计摘要

### 10.3 策略模式

- `off`: 不启用
- `log_only`: 仅记录风险（默认）
- `enforce`: 阻断高风险调用并发出 `tool_policy_blocked`

配置建议（`packages/backend/app/config.py`）：
- `tool_policy_enabled: bool = True`
- `tool_policy_mode: str = "log_only"`
- `tool_policy_allowed_cmd_prefixes: list[str]`

---

## 11. 兼容策略（保持 /api/chat 不破坏）

### 11.1 兼容原则

- 现有前端默认继续调用 `/api/chat` 与 `/api/chat/stream`。
- Chat API 内部改为调用 RunService：
  - 创建 run
  - 订阅 run 事件
  - 聚合兼容响应字段（message/action/preview）

### 11.2 渐进迁移

1. Phase 1：新增 Run API，Chat 仍走旧路径。
2. Phase 2：Chat 内部切 Run Adapter（外部无感）。
3. Phase 3：前端逐步切换到 Run API（可选）。

---

## 12. 实施拆分（Backend 优先）

| 阶段 | 名称 | 目标 | 依赖 |
|------|------|------|------|
| B8-R1 | Run 数据层 | `session_runs` + `session_events.run_id` + 迁移 | 无 |
| B8-R2 | Run 服务层 | RunService + 状态机 + CRUD API | B8-R1 |
| B8-R3 | 事件层升级 | run 事件类型 + run 维度查询 | B8-R1 |
| B8-R4 | 编排接入 Run | LangGraph 执行路径改造 | B8-R2 |
| B8-R5 | Tool Policy Hooks | pre/post 钩子 + 审计事件 | B8-R4 |
| B8-R6 | Verify Gate | 节点接入 + fail 路径定义 | B8-R4 |
| B8-R7 | Chat 兼容适配 | `/api/chat*` 内部走 Run Adapter | B8-R2,B8-R3 |
| B8-D1 | App Data Store | `AppDataStore` 服务 + PG Schema 动态建表 | 无 |
| B8-D2 | App Data API | CRUD API `/api/sessions/{id}/data/*` | B8-D1 |
| B8-D3 | Generation 集成 | GenerationAgent 后调 `create_tables()` | B8-D1 |
| F8-D1 | Data Tab 前端 | Data Tab 提升为顶级 tab + Table/Dashboard 视图 + `useAppData` hook | B8-D2 |

并行建议：
- R1/R2 与 R5 可并行。
- R6 在 R4 基础上实施。
- R7 最后合并，降低回归风险。

---

## 13. 文件变更清单

### 13.1 Backend（新增）

- `packages/backend/app/api/runs.py`
- `packages/backend/app/services/run.py`
- `packages/backend/app/schemas/run.py`
- `packages/backend/app/services/tool_policy.py`
- `packages/backend/app/graph/nodes/verify.py`
- `packages/backend/app/services/app_data_store.py`
- `packages/backend/app/api/data.py`

### 13.2 Backend（修改）

- `packages/backend/app/db/models.py`
- `packages/backend/app/db/migrations.py`
- `packages/backend/app/events/types.py`
- `packages/backend/app/events/models.py`
- `packages/backend/app/events/emitter.py`
- `packages/backend/app/services/event_store.py`
- `packages/backend/app/api/events.py`
- `packages/backend/app/api/chat.py`
- `packages/backend/app/graph/state.py`
- `packages/backend/app/graph/graph.py`
- `packages/backend/app/graph/orchestrator.py`
- `packages/backend/app/agents/base.py`
- `packages/backend/app/config.py`
- `packages/backend/app/main.py`（注册新路由）

### 13.3 Web（最小同步）

- `packages/web/src/types/events.ts`（新增 run/verify/policy 事件）
- `packages/web/src/hooks/useSSE.ts`（去重键优先 run_id + seq）
- `packages/web/src/components/custom/WorkbenchPanel.tsx`（新增 Data tab）
- `packages/web/src/components/custom/DataTab.tsx`（重写为 Table/Dashboard 视图）
- `packages/web/src/components/custom/PreviewPanel.tsx`（移除内部 Data toggle）
- `packages/web/src/hooks/useAppData.ts`（新增）

---

## 14. 验收标准

### 14.1 功能验收

1. 可创建 Run 并查询完整生命周期。
2. `interrupt -> resume` 可在同一 run 上恢复成功。
3. 取消 run 后状态最终为 `cancelled`，不再继续产出生成事件。
4. verify fail 时不会进入 render 完成态。
5. tool policy 在 enforce 模式可阻断高风险调用。

### 14.2 兼容验收

1. 现有 `/api/chat` 与 `/api/chat/stream` 保持可用。
2. 老会话事件（无 run_id）仍可通过 `/api/sessions/{session_id}/events` 查询。
3. 前端在未升级 Run API 前不出现核心交互中断。

### 14.3 质量指标

- Run 相关结构化事件 `run_id` 覆盖率 ≥ 99%。
- `resume` 平均恢复耗时 ≤ 2s（本地 SQLite 环境）。
- 关键路径接口错误率（5xx）不高于 v0.7.1 基线。

---

## 15. 风险与回滚

### 15.1 主要风险

1. 迁移期间事件写入竞争导致 seq 间歇冲突。
2. Chat 适配层切换引发旧前端行为回归。
3. Tool policy 过严导致可用性下降。
4. Verify Gate 误判导致“可渲染结果被拦截”。

### 15.2 回滚策略

- Feature Flag：
  - `run_api_enabled`
  - `chat_use_run_adapter`
  - `tool_policy_mode`
  - `verify_gate_enabled`
- 出现回归时：
  1) 先关闭 `chat_use_run_adapter` 回退旧路径；
  2) 保留 run 数据写入（只写不读）；
  3) 逐步恢复开关并按阶段复测。

---

**结论**：Spec v0.8.2 先完成后端"运行态基础设施"改造，再逐步放开前端对 Run API 的直接依赖。这是对 v0.7.1 的低风险增量演进路径。

---

## 16. App Data Layer

### 16.1 背景

用户通过 Chat 创建 app 时，Generation Agent 会根据场景自动定义数据模型（如电商 app 的 Order/MenuItem/Customer）。用户在 Preview 中交互时，操作会写入对应的数据表。Data Tab 提供表格视图和看板视图来展示这些数据。

### 16.2 现状分析

**已有：**

- `schemas/scenario.py` — Entity-Relationship 数据模型定义（per 产品类型）
- `services/data_protocol.py` — 注入 iframe JS 运行时
- `services/skills/contracts/*.json` — 按产品类型的 state contract
- `utils/product_doc.py` — 生成 `data-store.js` / `data-client.js`
- 前端 `usePreviewBridge` + `DataTab` — 通过 postMessage 读取 iframe 数据

**缺失：**

- 服务端数据持久化（目前全部在 browser localStorage）
- 动态建表（data_model 定义了 Entity/Field 但未物化）
- CRUD API
- data_model 与 state_contract 未关联

### 16.3 存储方案：PostgreSQL Schema 隔离

**部署环境：** Railway PostgreSQL 插件，系统表和 app 数据共用同一个 PG 实例。

```
PostgreSQL (Railway)
  ├── public schema (系统表)
  │     ├── sessions
  │     ├── messages
  │     ├── versions
  │     ├── pages
  │     ├── product_docs
  │     └── ...
  │
  ├── app_<session_id> schema (餐厅 app)
  │     ├── "Order"
  │     ├── "MenuItem"
  │     └── "Customer"
  │
  └── app_<session_id> schema (看板 app)
        ├── "Board"
        ├── "Column"
        └── "Task"
```

**方案对比：**

| 维度 | Per-session SQLite | PG Schema 隔离 | 单表 JSONB |
|---|---|---|---|
| 动态建表 | 可以，但多文件管理 | `CREATE TABLE` 在 schema 内，干净 | 不需要建表，但查询弱 |
| 查询能力 | 基础 SQL | 窗口函数/CTE/JSONB 索引，Dashboard 聚合直接受益 | 需要应用层聚合 |
| 隔离 | 天然文件隔离 | `DROP SCHEMA CASCADE` 一键清理 | 需要 WHERE session_id = ... |
| 并发 | 写锁问题 | 无问题 | 无问题 |
| 部署 | Railway 不适合文件存储 | Railway PG 插件原生支持 | 同左 |
| 连接管理 | 每 session 一个连接 | 一个连接池，`SET search_path` 切换 | 同一个表 |

### 16.4 类型映射

```python
# data_model Entity field.type → PostgreSQL column type
TYPE_MAP = {
    "string": "TEXT",
    "number": "NUMERIC",
    "boolean": "BOOLEAN",
    "array": "JSONB",
    "object": "JSONB",
}
```

### 16.5 后端新增

#### 16.5.1 `app/services/app_data_store.py` — 核心服务

```python
class AppDataStore:
    """管理 per-session 的 app 数据表"""

    async def create_schema(self, session_id: str) -> str:
        """创建 session 专属 schema"""

    async def create_tables(self, session_id: str, data_model: DataModel):
        """根据 data_model.entities 动态建表"""

    async def drop_schema(self, session_id: str):
        """删除 session 时清理 schema"""

    async def insert_record(self, session_id: str, table: str, data: dict) -> dict:
        """写入一条记录"""

    async def query_table(self, session_id: str, table: str,
                          limit: int = 50, offset: int = 0,
                          order_by: str = None) -> dict:
        """查询表数据（分页）"""

    async def get_table_stats(self, session_id: str, table: str) -> dict:
        """聚合统计（count, sum, group by 等）"""

    async def list_tables(self, session_id: str) -> list:
        """列出 schema 内所有表及其列定义"""
```

#### 16.5.2 `app/api/data.py` — CRUD API

```
GET    /api/sessions/{id}/data/tables           列出所有表 + 列定义
GET    /api/sessions/{id}/data/{table}          查询表记录（分页）
POST   /api/sessions/{id}/data/{table}          写入记录
DELETE /api/sessions/{id}/data/{table}/{row_id} 删除记录
GET    /api/sessions/{id}/data/{table}/stats    聚合统计
```

接口约束：
- `table`、`order_by` 必须命中白名单（来自 data_model 定义），禁止直接拼接 SQL 标识符。
- 统一参数校验：`limit` 上限（建议 200），`offset >= 0`。
- 统一错误码：`400/404/409/422/500`（与 Run API 口径一致）。
- 写入接口要求请求体为对象，禁止顶层数组。

#### 16.5.3 集成点

```
Generation 流程:
  GenerationAgent 生成 HTML
    → DataProtocolGenerator 注入 JS
    → AppDataStore.create_tables() 根据 data_model 建表  ← 新增

iframe JS Runtime:
  用户交互 → window.IC.cart.add() 等
    → 改为调 POST /api/sessions/{id}/data/{table}  ← 替代 localStorage
    → 同时 postMessage 通知父窗口（保持实时性）

Session 删除:
  DELETE /api/sessions/{id}
    → AppDataStore.drop_schema()  ← 新增清理
```

### 16.6 前端改动

#### 16.6.1 Data Tab 提升为顶级 Tab

```
WorkbenchPanel (改动前):
  [Preview] [Code] [Product Doc]
      ↓
  PreviewPanel 内部 toggle: [Preview | Data]

WorkbenchPanel (改动后):
  [Preview] [Code] [Product Doc] [Data]  ← 同级
```

#### 16.6.2 Data Tab 两种视图

```
┌──────────────────────────────────────────┐
│ [Table 视图] [Dashboard 视图]  toggle     │
├──────────────────────────────────────────┤
│                                          │
│  === Table 视图 ===                       │
│  ┌─ 表选择 ─────────────────────────┐    │
│  │ [Order] [MenuItem] [Customer]    │    │
│  └──────────────────────────────────┘    │
│  ┌──┬──────────┬────────┬──────────┐    │
│  │id│ items    │ total  │ status   │    │
│  ├──┼──────────┼────────┼──────────┤    │
│  │1 │ [...]    │ 128.00 │ pending  │    │
│  │2 │ [...]    │ 45.50  │ done     │    │
│  └──┴──────────┴────────┴──────────┘    │
│  [< 1 2 3 >]  共 45 条                   │
│                                          │
│  === Dashboard 视图 ===                   │
│  ┌──────────┐ ┌──────────┐              │
│  │ Orders   │ │ Revenue  │              │
│  │   45     │ │ ¥3,280   │              │
│  └──────────┘ └──────────┘              │
│  ┌──────────────────────────────┐       │
│  │ Status 分布 (饼图/柱状图)     │       │
│  └──────────────────────────────┘       │
│                                          │
└──────────────────────────────────────────┘
```

#### 16.6.3 新增 Hook

```typescript
// hooks/useAppData.ts
function useAppData(sessionId: string) {
  return {
    tables,          // 表列表 + 列定义
    activeTable,     // 当前选中的表
    records,         // 当前表的记录（分页）
    stats,           // 当前表的聚合统计
    isLoading,
    selectTable,     // 切换表
    refreshTable,    // 刷新数据
    pagination,      // { page, pageSize, total }
  }
}
```

#### 16.6.4 数据源切换

```
改动前:
  iframe postMessage → usePreviewBridge → DataTab (raw JSON)

改动后:
  iframe JS runtime → POST API → PostgreSQL
  Data Tab → GET API → 结构化表格/看板展示
  iframe postMessage → 仅用于实时通知 Data Tab 刷新
```

### 16.7 Railway 部署注意

- Railway PostgreSQL 插件提供 `DATABASE_URL` 环境变量
- 连接数限制：Starter plan 约 20 连接，需要连接池（asyncpg pool 或 PgBouncer）
- 存储限制：Starter plan 1GB，app 数据量小，足够
- Schema 数量无硬限制，但建议定期清理已删除 session 的 schema
- Railway 无持久文件系统，确认 per-session SQLite 方案不可行，PG 是正确选择

### 16.8 Schema 命名与 SQL 安全

Schema 命名规范：
- 统一使用 `app_<session_id_slug>`，其中 `session_id_slug = lower(session_id)` 后将非 `[a-z0-9_]` 字符替换为 `_`。
- Schema 名长度上限 63（PostgreSQL identifier 限制），超长时截断并附加短 hash。
- 仅允许通过白名单映射后的 schema/table/column 标识符参与 SQL。

安全要求：
- 所有 value 参数必须参数化绑定。
- 所有 identifier（schema/table/column）必须通过严格校验 + 安全引用（quote identifier）。
- 拒绝跨 schema 访问（禁止用户输入中出现 `.` 作为 schema 前缀）。

### 16.9 data_model 演进策略

当 generation/refine 产生新的 data_model 时，执行增量迁移：
1. 新增实体：`CREATE TABLE IF NOT EXISTS`。
2. 新增字段：`ALTER TABLE ADD COLUMN IF NOT EXISTS`。
3. 字段删改：默认不自动 drop/rename，先标记为 deprecated，并在后续离线迁移处理。
4. 迁移记录：将 data_model 版本与迁移摘要写入 run 事件（建议 `data_model_migrated` 扩展事件，若本期不加事件类型则写入 `run_completed.payload`）。

兼容原则：
- 历史数据优先保留，不因模型轻微调整导致数据丢失。
- Dashboard 统计默认仅基于当前模型可见字段，deprecated 字段可配置是否展示。
