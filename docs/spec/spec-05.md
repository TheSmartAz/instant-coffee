# Instant Coffee - 技术规格说明书 (Spec v0.5)

**项目名称**: Instant Coffee (速溶咖啡)
**版本**: v0.5 - 统一版本管理 + Responses API + 稳定性修复
**日期**: 2026-02-02
**文档类型**: Technical Specification Document (TSD)

---

## 文档变更历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v0.5 | 2026-02-02 | 整合版本管理扩展（快照回滚/统一保留/产品文档历史）、DMXAPI Responses 全量切换、已知问题修复方案 | Planning |

---

## 设计决策记录

### 核心决策

| 问题 | 决策 | 说明 |
|------|------|------|
| 回滚入口 | 仅 ProjectSnapshot | PageVersion/ProductDocHistory 只用于预览/对比，不回滚 |
| 版本保留规则 | 统一 5 自动 + 2 pinned | 超出窗口标记 released，仅保留 metadata（Product Doc 例外可查看内容） |
| Product Doc 历史 | 允许查看与 Markdown diff | released 仍可查看，但不可回滚 |
| LLM 调用协议 | 全量切换 Responses API | 流式解析 `response.output_text.delta`，SSE 对前端保持 `delta` |
| Tool calling | Responses 原生事件驱动 | 收到 tool-call 事件即触发工具，再续接 responses.create |
| 事件持久化 | 增加 session_events | chat SSE 事件入库，刷新后可恢复 Interview 与事件流 |
| 任务稳定性 | 请求取消即 abort | 运行中任务标记 aborted，提供超时清理策略 |
| HTML 回退 | 失败前强制重试 | 提升完整 HTML 命中率，并记录 fallback_used |

---

## 目录

1. [版本概述](#1-版本概述)
2. [范围与原则](#2-范围与原则)
3. [架构设计](#3-架构设计)
4. [数据模型](#4-数据模型)
5. [版本与回滚语义](#5-版本与回滚语义)
6. [LLM Responses 迁移](#6-llm-responses-迁移)
7. [API 设计](#7-api-设计)
8. [前端设计](#8-前端设计)
9. [稳定性修复与已知问题](#9-稳定性修复与已知问题)
10. [迁移与实施拆分](#10-迁移与实施拆分)
11. [文件变更清单](#11-文件变更清单)
12. [验收标准](#12-验收标准)

---

## 1. 版本概述

### 1.1 版本定位

**Spec v0.5** 在 v0.4 的多页面生成基础上，重点引入三类增强能力：

1. **统一版本管理体系** — 快照为唯一回滚入口；PageVersion/ProductDocHistory 仅用于预览/对比
2. **Responses API 统一调用** — 后端全量切换到 DMXAPI Responses（流式 + 非流式 + tool calling）
3. **稳定性修复** — HTML 回退、任务中断、事件持久化、历史版本预览等问题系统化修复

### 1.2 与 v0.4 的关系

| v0.4 (现有) | v0.5 (本版本) |
|-------------|--------------|
| 仅 PageVersion 版本管理 | PageVersion + ProjectSnapshot + ProductDocHistory |
| PageVersion 支持回滚 | 回滚仅限 ProjectSnapshot |
| 无 Product Doc 历史 | Product Doc 历史 + diff |
| LLM 调用基于 chat.completions | 全量改为 Responses API |
| SSE 事件不持久化 | 事件入库 + 刷新恢复 |
| 页面历史仅回滚 | PageVersion 可预览且不可回滚 |

### 1.3 设计原则

1. **回滚单一入口**：回滚只发生在 ProjectSnapshot。
2. **版本不可变**：历史内容只新增，不修改。
3. **统一窗口**：所有版本类型统一遵循 5 自动 + 2 pinned。
4. **前端兼容**：SSE 事件格式保持，UI 改动最小。
5. **稳定可诊断**：异常必须可追踪（fallback_used、任务状态、事件可回放）。

---

## 2. 范围与原则

### 2.1 范围

**包含**:
- ProjectSnapshot（项目级快照，唯一回滚入口）
- PageVersion（页面版本，仅预览）
- ProductDocHistory（产品文档历史，可查看与对比）
- 统一保留规则（5 自动 + 2 pinned）
- DMXAPI Responses 全量切换（stream + non-stream + tool calling）
- Chat/SSE 事件持久化与历史回放
- 任务中断与 HTML 回退的稳定性修复

**不包含**:
- Session 级旧 `Version` 的扩展（仅作为兼容层）
- SSE 协议格式变更
- UI 大规模重构（仅增量补齐）

### 2.2 核心原则

1. **回滚只发生在 ProjectSnapshot**。
2. **版本内容不可变**，只允许新增历史。
3. **统一保留规则**应用于全部版本类型。
4. **released 仅保留 metadata**（Product Doc 例外仍保留内容）。
5. **Responses API 为唯一 LLM 通道**，前端消费协议保持不变。

---

## 3. 架构设计

### 3.1 版本与回滚流程

```
页面/文档生成
    ↓
Plan 执行（多页并行）
    ↓
Plan 全部成功完成
    ↓
生成 ProjectSnapshot (auto)
    ↓
统一保留规则计算
    ↓
如需回滚 → 从 ProjectSnapshot 读取冻结内容
    ↓
生成新的 ProductDoc + PageVersion (source=auto)
    ↓
生成新的 ProjectSnapshot (source=rollback)
```

**说明**
- 仅当 Plan 全部成功完成时自动生成快照；存在失败页时允许重试，不生成快照。

### 3.2 LLM 调用流程（Responses）

```
Agent
  ↓
OpenAIClient.responses_create / responses_stream
  ↓
解析 Responses 事件:
  - response.output_text.delta → SSE: delta
  - tool_call events → ToolCall/ToolResult
  ↓
前端 SSE 按既有逻辑拼接/展示
```

### 3.3 事件持久化与回放

- `/api/chat` 的 EventEmitter 接入 EventStoreService。
- **仅持久化结构化事件**（不存 `delta`）。
- 结构化事件包括：Interview 问答、Agent/Tool 生命周期、Plan/Task 状态变更、版本创建/确认等。
- 无 `task_id` / `plan_id` 的事件写入 `session_events`。
- 前端启动时拉取历史事件，合并实时 SSE（`delta` 仅用于实时展示）。

### 3.4 任务中断处理

- 请求取消时显式调用 executor.abort。
- 运行中任务标记 `aborted` 并写入 `completed_at`。
- 后台清理：`in_progress` 超时任务可重试或标记失败。

---

## 4. 数据模型

### 4.1 ProductDoc（扩展）

```
ProductDoc
├── id            (UUID, PK)
├── session_id    (FK → Session.id, Unique)
├── version       (int, 自增)
├── content       (TEXT, Markdown)
├── structured    (JSON)
├── status        (enum: draft / confirmed / outdated)
├── created_at    (datetime)
└── updated_at    (datetime)
```

### 4.2 ProductDocHistory（新增）

```
ProductDocHistory
├── id             (int, PK, auto)
├── product_doc_id (FK → ProductDoc.id)
├── version        (int)
├── content        (TEXT, Markdown)
├── structured     (JSON)
├── change_summary (TEXT)
├── source         (enum: auto / manual / rollback)
├── is_pinned      (bool)
├── is_released    (bool)
├── released_at    (datetime, nullable)
├── created_at     (datetime)
```

### 4.3 PageVersion（扩展）

```
PageVersion
├── id                (int, PK, auto)
├── page_id           (FK → Page.id)
├── version           (int)
├── html              (TEXT, 可为空; released 时可清空)
├── description       (string)
├── source            (enum: auto / manual / rollback)
├── is_pinned         (bool)
├── is_released       (bool)
├── released_at       (datetime, nullable)
├── payload_pruned_at (datetime, nullable)
├── fallback_used     (bool)
├── fallback_excerpt  (TEXT, nullable)
├── created_at        (datetime)
```

### 4.4 ProjectSnapshot（新增）

```
ProjectSnapshot
├── id               (UUID, PK)
├── session_id       (FK → Session.id)
├── snapshot_number  (int, 自增, session 内唯一)
├── label            (string, 可选)
├── source           (enum: auto / manual / rollback)
├── is_pinned        (bool)
├── is_released      (bool)
├── released_at      (datetime, nullable)
├── created_at       (datetime)
```

```
ProjectSnapshotDoc
├── snapshot_id         (FK → ProjectSnapshot.id)
├── content             (TEXT, Markdown)
├── structured          (JSON)
├── global_style        (JSON)
├── design_direction    (JSON)
├── product_doc_version (int)
```

```
ProjectSnapshotPage
├── snapshot_id   (FK → ProjectSnapshot.id)
├── page_id       (FK → Page.id)
├── slug          (string)
├── title         (string)
├── order_index   (int)
├── rendered_html (TEXT)
```

**规则**
- 快照内容为冻结内容，不依赖 PageVersion 是否可用。

### 4.5 SessionEvent（新增）

```
SessionEvent
├── id         (int, PK, auto)
├── session_id (FK → Session.id)
├── seq        (int, 单调递增)
├── type       (string)
├── payload    (JSON)
├── source     (enum: session / plan / task)
├── created_at (datetime)
```

**建议约束 / 索引**
- `product_doc_histories`: Unique(`product_doc_id`, `version`)
- `project_snapshots`: Unique(`session_id`, `snapshot_number`)
- `project_snapshot_pages`: Index(`snapshot_id`, `page_id`)
- `session_events`: Index(`session_id`, `seq`)

---

## 5. 版本与回滚语义

### 5.1 统一保留规则（5 自动 + 2 pinned）

对 **ProductDocHistory / PageVersion / ProjectSnapshot** 统一处理：

1) 最近 5 个 `source=auto` 为可用窗口
2) 最多 2 个 `is_pinned=true` 为可用窗口（无论新旧）
3) 其余标记为 `is_released=true`（历史不可用）

**计数规则**
- pinned 永远独立计数，可与最近 5 auto 重叠，但不减少 auto 名额。

**Pinned 超限处理**
- 当已存在 2 个 pinned，再 pin 新版本时返回冲突信息。
- 前端弹窗要求用户释放一个已 pinned 版本；释放成功后，再执行新的 pin。

### 5.2 ProjectSnapshot 回滚（唯一入口）

回滚到快照时：
1. 读取快照冻结内容（Product Doc + Pages HTML）
2. 创建新的 ProductDoc 版本 + ProductDocHistory
3. 为每个页面创建新的 PageVersion（html 来自快照）
4. 创建新的 ProjectSnapshot（source=rollback）

**说明**
- 回滚不会复用旧 version_id，而是生成新版本。
- 回滚生成的新版本 `source=auto`，计入 5 自动窗口。

### 5.3 PageVersion 行为

- PageVersion **仅用于预览**，不提供回滚入口。
- released 版本不可预览，仅显示 metadata。
- 预览入口为 `GET /api/pages/{page_id}/versions/{version_id}/preview`。
- 不再提供 `/api/pages/{page_id}/rollback`，内部测试阶段不考虑兼容策略。

### 5.4 Product Doc 历史查看与对比

- 支持查看任意历史版本内容（包括 released）。
- 支持 **任意两版本 Markdown 内容对比**（前端 diff）。
- 不提供回滚入口。

### 5.5 Released 数据清理策略

- PageVersion：清空 `html`，设置 `payload_pruned_at`。
- ProjectSnapshot：删除 `project_snapshot_pages.rendered_html` 与 `project_snapshot_docs` 内容。
- ProductDocHistory：released 仍保留 `content`（可查看/对比），但不可回滚。

---

## 6. LLM Responses 迁移

### 6.1 配置与兼容

- 新增 API 模式开关：`OPENAI_API_MODE=responses`（默认直接设为 responses）。
- 兼容 DMXAPI 的 `base_url` / `api_key` 读取逻辑。
- 允许传入 Responses 专用参数（`reasoning.effort`、`max_output_tokens` 等）。

### 6.2 OpenAIClient 通道

- 新增 `responses_create()`（非流式），返回统一 `LLMResponse`。
- 新增 `responses_stream()`（流式），解析事件并 yield 文本 delta。
- 新增 `responses_with_tools()`：解析 tool-call output items，执行本地工具后续接。
- 保留 `chat_completion(_stream)` 入口，仅作兼容，不再用于主流程。

### 6.3 流式与 tool calling 事件

- `response.output_text.delta` → 继续向前端输出 `delta`。
- tool-call 事件触发 ToolCall/ToolResult SSE（形态保持）。
- 支持并行多工具调用，需合并输出并保证事件顺序可追踪。

### 6.4 Token usage 迁移

- Responses usage 字段映射到 `TokenUsage`：`input_tokens` → `prompt_tokens`，`output_tokens` → `completion_tokens`。
- 原始 usage 写入 `TokenUsage.raw`（JSON），用于诊断与对齐。
- 保持计费统计口径一致，新增测试覆盖。

---

## 7. API 设计

### 7.1 Product Doc 历史与对比

| 端点 | 方法 | 功能 |
|------|------|------|
| `GET /api/sessions/{id}/product-doc/history` | GET | 列表（metadata + 可用性） |
| `GET /api/sessions/{id}/product-doc/history/{history_id}` | GET | 获取单个历史内容（Markdown） |
| `POST /api/sessions/{id}/product-doc/history/{history_id}/pin` | POST | Pin 历史版本 |
| `POST /api/sessions/{id}/product-doc/history/{history_id}/unpin` | POST | Unpin 历史版本 |

**说明**
- diff 在前端完成：选择两个 history_id 后拉取 Markdown 进行对比。

### 7.2 快照接口（唯一回滚入口）

| 端点 | 方法 | 功能 |
|------|------|------|
| `GET /api/sessions/{id}/snapshots` | GET | 获取快照列表（含可用性） |
| `POST /api/sessions/{id}/snapshots/{snapshot_id}/rollback` | POST | 回滚到快照 |
| `POST /api/sessions/{id}/snapshots/{snapshot_id}/pin` | POST | Pin 快照 |
| `POST /api/sessions/{id}/snapshots/{snapshot_id}/unpin` | POST | Unpin 快照 |

### 7.3 PageVersion 接口（仅预览）

| 端点 | 方法 | 功能 |
|------|------|------|
| `GET /api/pages/{page_id}/versions` | GET | 列表（含可用性） |
| `GET /api/pages/{page_id}/versions/{version_id}/preview` | GET | 预览指定版本（仅非 released） |
| `POST /api/pages/{page_id}/versions/{version_id}/pin` | POST | Pin 版本 |
| `POST /api/pages/{page_id}/versions/{version_id}/unpin` | POST | Unpin 版本 |

**说明**
- 不提供 `/api/pages/{page_id}/rollback`，当前阶段不考虑兼容策略。

### 7.4 历史事件接口

| 端点 | 方法 | 功能 |
|------|------|------|
| `GET /api/sessions/{session_id}/events` | GET | 合并 session_events / plan_events / task_events |

**说明**
- 返回按 `seq` 排序的**结构化事件**列表，前端用于初始化事件流与 Interview 组件。
- 不包含 `delta`；完整输出由消息/任务结果表提供。

### 7.5 兼容字段补充

- 旧 API 返回值补充：`is_released` / `is_pinned` / `source`。
- SSE 格式不变，前端仍消费 `delta` / ToolCall / ToolResult。

---

## 8. 前端设计

### 8.1 VersionPanel（统一三类版本）

- **Preview Tab**: PageVersion timeline（仅预览，不回滚）
- **Code Tab**: ProjectSnapshot timeline（可回滚）
- **Product Doc Tab**: ProductDocHistory timeline（查看 + diff）

**统一状态标识**
- released：置灰 + “历史不可用”，隐藏预览/回滚按钮
- pinned：高亮标记

### 8.2 Product Doc Diff

- 两个下拉选择框（左/右版本）
- Diff 仅对 Markdown content
- released 的 Product Doc 仍可查看与 diff

### 8.3 事件恢复

- 页面加载时先调用 `/api/sessions/{id}/events`。
- 事件列表与 SSE 实时流合并，恢复 Interview 组件与事件列表（`delta` 仅实时显示）。

### 8.4 Pin 冲突交互

- 当 pinned 超过 2 个：弹窗让用户选择释放哪一个 pinned。
- 确认释放并完成 unpin 后，再执行新的 pin。

---

## 9. 稳定性修复与已知问题

### 9.1 HTML 回退模板过度触发

**症状**
- 生成页面落回最小 HTML 模板，内容高度相似且体积较小。

**修复**
- HTML 抽取失败时先执行 **严格重试**（更严格提示或低温度）。
- 记录 `fallback_used` 与原始输出摘要（`fallback_excerpt`），便于诊断。

### 9.2 任务中断导致 in_progress 卡死

**症状**
- 任务长期 `in_progress`，后续任务被阻塞。

**修复**
- 请求取消时显式 abort 执行器并标记任务为 `aborted`。
- 增加超时清理策略：过期 `in_progress` 任务自动重试或失败。

### 9.3 事件刷新后消失

**症状**
- Interview 组件与 Agent/Tool 事件刷新后消失。

**修复**
- 增加 `session_events` 表，持久化 chat 事件。
- 新增历史事件 API，前端启动时恢复事件流。
- 仅持久化结构化事件（不存 `delta`）。
- 按 `seq` 合并排序，保证跨来源事件顺序稳定。

### 9.4 历史页面版本无法预览

**症状**
- 版本面板仅支持回滚，无法预览历史版本。

**修复**
- 增加 `/versions/{version_id}/preview` 端点。
- UI 增加“View”动作加载指定版本预览。

---

## 10. 迁移与实施拆分

### M1: 版本管理与数据迁移

1) 新增字段与表结构：ProductDoc.version、ProductDocHistory、ProjectSnapshot。
2) 回填 ProductDoc 版本与历史（version=1）。
3) 回填 PageVersion 新字段：`source=auto`，`is_pinned=false`，`is_released=false`，`fallback_used=false`。
4) 为每个 session 生成初始 ProjectSnapshot（推荐）。
5) 快照自动生成触发点调整为：Plan 全部成功完成后。
6) 执行首次保留规则计算并清理 payload（按 5.5）。

### M2: Responses API 切换

- OpenAIClient 新增 Responses 通道。
- Agent 调用全面切换到 responses。
- 覆盖流式与 tool calling 解析测试。

### M3: 事件与任务稳定性

- EventEmitter 接入 EventStoreService。
- 新增 `session_events` 表与历史事件 API。
- EventStore 为所有事件写入单调递增 `seq`，用于合并排序。
- executor abort + 任务超时清理策略。

### M4: 前端 UI 更新

- VersionPanel 三类 timeline。
- Product Doc Diff UI。
- 事件恢复逻辑与历史预览按钮。

---

## 11. 文件变更清单

### Backend

| 文件 | 变更 |
|------|------|
| `app/db/models.py` | 新增 ProductDocHistory / ProjectSnapshot / SessionEvent 字段与模型；PageVersion fallback 字段 |
| `app/db/migrations/*` | 新增/更新迁移脚本 |
| `app/services/product_doc.py` | 写入历史版本与 pinned/released 逻辑 |
| `app/services/page_version.py` | 预览指定版本 + released 清理 |
| `app/services/project_snapshot.py` | **新增** 快照服务 |
| `app/services/event_store.py` | 存储 session_events |
| `app/api/events.py` | **新增** 历史事件 API |
| `app/api/product_doc.py` | 新增 history endpoints |
| `app/api/pages.py` | 新增 versions/{id}/preview |
| `app/api/snapshots.py` | **新增** 快照 endpoints |
| `app/api/chat.py` | SSE 事件持久化接入 |
| `app/llm/openai_client.py` | Responses API 通道 |
| `app/agents/base.py` | 调用 Responses 接口 |
| `app/config.py` | 新增 OPENAI_API_MODE 等配置 |
| `app/executor/parallel.py` | abort 与状态修复 |
| `app/agents/generation.py` | HTML fallback 重试与记录 |

### Web

| 文件 | 变更 |
|------|------|
| `src/components/custom/VersionPanel.tsx` | 三类版本展示 + Preview/View/Pin |
| `src/components/custom/ProductDocPanel.tsx` | Diff 入口与历史列表 |
| `src/hooks/useSSE.ts` | 初始化历史事件 + SSE 合并 |
| `src/hooks/useChat.ts` | 事件恢复与 Interview 重建 |
| `src/api/client.ts` | 新增 snapshots / history / events API |
| `src/types/events.ts` | 补充事件类型与 `seq` / `source` 字段 |

---

## 12. 验收标准

### 版本与回滚

1. 回滚仅能在 ProjectSnapshot 层完成。
2. PageVersion 仅预览不回滚；released 不可预览。
3. Product Doc 支持历史查看与任意两版本 diff。
4. 统一 5 自动 + 2 pinned 生效，超出窗口标记 released。
5. Plan 全部成功完成后才自动生成 ProjectSnapshot。

### Responses API

6. 所有 LLM 调用统一走 Responses（流式 + 非流式 + tool calling）。
7. SSE 对前端仍输出 `delta`，前端无须改协议即可显示。
8. ToolCall / ToolResult 事件在 Responses 模式下稳定可用。
9. Token usage 统计正确。

### 稳定性

10. HTML 抽取失败会先重试，fallback 使用可追踪。
11. 请求取消不会留下 `in_progress` 任务。
12. 刷新后 Interview 与事件列表可恢复。
13. 历史页面版本可预览且不改变当前版本。
14. `delta` 不入库，事件恢复仅依赖结构化事件。
