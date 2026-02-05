# Instant Coffee 项目阶段性总结

> **生成时间**: 2026-02-01
> **项目版本**: web 0.0.0 / cli 0.1.0 / backend 无独立版本标记
> **项目状态**: v0.3 能力已落地，聊天/规划/事件/前端可运行；校验器、工具完善与 CLI 源码仍有缺口

---

## 项目概述

**Instant Coffee (速溶咖啡)** 是一个通过自然对话生成移动端优化 HTML 页面 的 AI 工具。项目采用 monorepo 架构，后端为 FastAPI + SQLite，前端为 Vite + React + Tailwind + shadcn，CLI 采用 Node（Commander）并当前仅保留 `dist/` 构建产物。

---

## 技术栈

### 后端技术栈
| 技术 | 说明 |
|------|------|
| Python | 3.x |
| FastAPI | API 框架 |
| SQLAlchemy | ORM |
| Pydantic | 数据验证 |
| SQLite | 默认数据库 |
| openai | Agent LLM 调用（AsyncOpenAI） |
| httpx | Planner API 请求 |
| Server-Sent Events | 实时事件流 |
| python-dotenv | 可选环境变量加载 |

### 前端技术栈
| 技术 | 版本/说明 |
|------|----------|
| React | 19.2.0 |
| TypeScript | 5.9.3 |
| Vite | 7.2.4 |
| React Router | 7.13.0 |
| Tailwind CSS | 4.1.18 |
| Radix UI | 组件库 |
| Sonner | Toast |
| Lucide React | 图标 |
| Playwright | 1.58.1（截图/验证脚本） |

### CLI 技术栈
| 技术 | 版本/说明 |
|------|----------|
| Node.js | ESM |
| Commander | 12.0.0 |
| Inquirer | 9.2.0 |
| Chalk / Ora | 交互 UI |

---

## 项目结构

```
instant-coffee/
├── packages/
│   ├── backend/                     # FastAPI 后端
│   │   ├── app/
│   │   │   ├── agents/              # Interview / Generation / Refinement
│   │   │   ├── api/                 # REST/SSE 端点
│   │   │   ├── db/                  # 数据库层
│   │   │   ├── events/              # 事件模型/发射器
│   │   │   ├── executor/            # DAG 执行引擎
│   │   │   ├── generators/          # HTML 验证器
│   │   │   ├── llm/                 # LLM 客户端 + Tools
│   │   │   ├── planner/             # Planner（OpenAI/Anthropic）
│   │   │   ├── services/            # 业务服务
│   │   │   ├── config.py            # 配置
│   │   │   └── main.py              # 应用入口
│   │   ├── tests/                   # 后端测试
│   │   ├── instant-coffee.db        # 运行时数据库（本地）
│   │   └── instant-coffee-output/   # 运行时输出（本地）
│   ├── web/                         # Vite + React 前端
│   └── cli/                         # CLI 构建产物（dist/）
├── docs/                            # 文档与规格
├── README.md
└── CLAUDE.md
```

---

## 核心运行流程

### 1) Chat（生成/精炼）
1. `POST /api/chat` 或 `GET /api/chat/stream` 接收用户输入。
2. Orchestrator 根据历史决定：
   - 首次对话触发 Interview（可通过 `interview` 参数控制）。
   - 若已有 HTML 且用户未要求“重新生成”，则走 Refinement。
   - 否则进入 Generation。
3. 生成的 HTML 写入 `OUTPUT_DIR/{session_id}/index.html` 并保存版本。
4. SSE 通过事件与响应数据同步前端。

### 2) Plan + Task
1. `POST /api/plan` 调 Planner 生成 DAG 任务并落库。
2. `GET /api/plan/{plan_id}/status` 查询计划状态。
3. `POST /api/task/{id}/retry|skip` 管理任务。
4. `POST /api/session/{id}/abort` 中断会话内活跃计划。

---

## 后端功能

### 1. Agent 系统 (`app/agents/`)
| Agent | 功能摘要 |
|-------|----------|
| BaseAgent | 统一 LLM 调用、Token 统计、Tool 事件封装 |
| InterviewAgent | LLM 驱动问答；支持 `<INTERVIEW_ANSWERS>` 结构化输入 |
| GenerationAgent | LLM 生成 HTML（含工具写文件）；失败回退模板 |
| RefinementAgent | LLM 迭代已有 HTML（支持读写工具） |
| AgentOrchestrator | 选择 Interview / Generation / Refinement 路径 |

**关键行为**：
- Interview 输出结构化问题/信心度，支持“跳过/直接生成”动作。
- Generation/Refinement 自动抽取 HTML，写入 `index.html` 并保留版本副本。
- BaseAgent 会发出 `agent_*`、`tool_*`、`token_usage` 事件。

### 2. LLM 客户端 & Tools (`app/llm/`)
| 组件 | 说明 |
|------|------|
| OpenAIClient | AsyncOpenAI + 重试 + 费用估算 |
| tools.py | filesystem_read / filesystem_write / validate_html |
| tool_handlers.py | 安全路径、大小限制、编码校验 |
| retry.py | 指数退避重试 |

`validate_html` 调用 `generators/mobile_html.validate_mobile_html`（当前为占位实现）。

### 3. API 端点 (`app/api/`)
| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/chat` | POST | 聊天请求，支持 JSON 或 SSE |
| `/api/chat/stream` | GET | SSE 流式 |
| `/api/sessions` | GET/POST | 列出/创建会话 |
| `/api/sessions/{id}` | GET | 会话详情（含预览） |
| `/api/sessions/{id}/messages` | GET | 消息历史 |
| `/api/sessions/{id}/versions` | GET | 版本列表 |
| `/api/sessions/{id}/preview` | GET | HTML 预览 |
| `/api/sessions/{id}/rollback` | POST | 回滚版本 |
| `/api/sessions/{id}/versions/{version_id}/revert` | POST | 兼容版回滚 |
| `/api/plan` | POST | 生成计划 |
| `/api/plan/{plan_id}/status` | GET | 计划状态 |
| `/api/task/{id}/retry` | POST | 重试任务 |
| `/api/task/{id}/skip` | POST | 跳过任务 |
| `/api/session/{id}/abort` | POST | 中断会话计划 |
| `/api/settings` | GET/PUT | 运行时设置 |
| `/health` | GET | 健康检查 |

### 4. 数据库模型 (`app/db/models.py`)
| 模型 | 说明 |
|------|------|
| Session / Message / Version | 会话、消息、HTML 版本 |
| TokenUsage | Token 记录与费用 |
| Plan / Task | 计划与任务 |
| PlanEvent / TaskEvent | 事件落库 |

**状态枚举**：
- Plan: `pending` / `in_progress` / `done` / `failed` / `aborted`
- Task: `pending` / `in_progress` / `done` / `failed` / `blocked` / `skipped` / `retrying` / `aborted`

### 5. 服务层 (`app/services/`)
- Session / Message / Version / Plan / Task / EventStore / Export / Filesystem / TokenTracker

### 6. 执行引擎 (`app/executor/`)
| 组件 | 功能 |
|------|------|
| TaskScheduler | DAG 调度 + 循环依赖检测 |
| ParallelExecutor | 并行任务执行 |
| TaskExecutorFactory | Interview/Generation/Refinement/Export/Validator |
| RetryPolicy | 指数退避 |

> 执行引擎已实现，但目前未在 API 中提供“执行计划”入口（主要用于测试/后续集成）。

### 7. 规划器 (`app/planner/`)
| 组件 | 说明 |
|------|------|
| OpenAIPlanner | OpenAI JSON 规划 |
| AnthropicPlanner | Anthropic JSON 规划 |
| BasePlanner | JSON 抽取、任务标准化 |

### 8. 事件系统 (`app/events/`)
**事件类型**：
- Agent: `agent_start`, `agent_progress`, `agent_end`
- Tool: `tool_call`, `tool_result`
- Token: `token_usage`
- Plan/Task: `plan_created`, `plan_updated`, `task_*`
- System: `error`, `done`

`EventEmitter` 支持事件缓存与持久化（通过 `EventStoreService`）。

### 9. 生成器/校验
- `generators/mobile_html.validate_mobile_html` 目前为空实现（返回 `[]`）。
- Validator 任务执行器已存在，但依赖真实校验逻辑。

---

## 前端功能

### 1. API 客户端 (`src/api/client.ts`)
覆盖 sessions/chat/settings/tasks 等核心接口，并提供 SSE URL 构造。

### 2. 自定义 Hooks (`src/hooks/`)
`useChat`, `useSession`, `usePlan`, `useSSE`, `useProjects`, `useSettings`,
`useVirtualList`, `useOnlineStatus`, `use-toast`.

### 3. 页面 (`src/pages/`)
`HomePage`, `ProjectPage`, `ExecutionPage`, `SettingsPage`。

### 4. 组件 (`src/components/`)
**自定义组件**：
- ChatPanel / ChatInput / ChatMessage
- InterviewWidget（结构化问答）
- PreviewPanel / PhoneFrame
- VersionPanel / VersionTimeline
- ProjectCard
- TokenDisplay

**事件流**：
- EventList / EventItem / CollapsibleEvent / ToolCallEvent / ToolResultEvent / ProgressBar / StatusIcon

**任务视图**：
- TaskCard / TaskCardList / AgentActivity / ToolCallLog

**Todo**：
- TodoPanel / TodoItem

**shadcn/ui**：
alert-dialog, avatar, badge, button, card, collapsible, dialog, dropdown-menu,
input, label, resizable, scroll-area, select, separator, skeleton, slider,
sonner, switch, tabs, textarea, toast, toaster, tooltip.

### 5. 类型定义 (`src/types/`)
- `events.ts`: 事件类型与类型守卫
- `plan.ts`: Plan/Task 状态类型
- `index.ts`: 会话、版本、Interview 结构与 Token Summary

---

## CLI 功能（`packages/cli/dist`）

**可用命令**：
- `chat`：交互式对话（SSE 优先）
- `history`：历史会话查看
- `export`：导出内容
- `rollback`：回滚版本
- `stats`：统计信息
- `clean`：清理输出

**运行时配置**：
`BACKEND_URL`, `OUTPUT_DIR`, `VERBOSE`

> CLI 仅保留编译产物，TS 源码未在仓库中。

---

## 测试覆盖 (`packages/backend/tests/`)

- test_agent_prompts.py
- test_chat_stream_compat.py
- test_chat_stream_tool_events.py
- test_event_protocol.py
- test_event_store.py
- test_events.py
- test_generation_agent.py
- test_interview_agent.py
- test_llm_client.py
- test_llm_retry.py
- test_orchestrator_events.py
- test_parallel_executor.py
- test_plan_task_services.py
- test_planner.py
- test_refinement_agent.py
- test_retry_policy.py
- test_task_scheduler.py
- test_tool_events.py
- test_tools.py

---

## 配置管理

### 后端环境变量（`app/config.py`）
| 配置项 | 环境变量 | 默认值 |
|--------|----------|--------|
| 数据库 | `DATABASE_URL` | `sqlite:///./instant-coffee.db` |
| 输出目录 | `OUTPUT_DIR` | `instant-coffee-output` |
| 规划器提供商 | `PLANNER_PROVIDER` | `openai` |
| 规划器模型 | `PLANNER_MODEL` | `gpt-4o-mini` |
| 规划器超时 | `PLANNER_TIMEOUT_SECONDS` | `30.0` |
| OpenAI Key | `OPENAI_API_KEY` | - |
| OpenAI Base | `OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| OpenAI 超时 | `OPENAI_TIMEOUT_SECONDS` | `60.0` |
| OpenAI 最大重试 | `OPENAI_MAX_RETRIES` | `2` |
| OpenAI 基础退避 | `OPENAI_BASE_DELAY` | `1.0` |
| Anthropic Key | `ANTHROPIC_API_KEY` | - |
| Anthropic Base | `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` |
| Anthropic Version | `ANTHROPIC_API_VERSION` | `2023-06-01` |
| 默认 Base URL | `DEFAULT_BASE_URL` | - |
| 默认 Key | `DEFAULT_KEY` | - |
| 模型 | `MODEL` / `DEFAULT_MODEL` | `gpt-4o-mini` |
| 温度 | `TEMPERATURE` | `0.7` |
| 最大 Token | `MAX_TOKENS` | `8000` |
| 自动保存 | `AUTO_SAVE` | `true` |
| 最大并发 | `MAX_CONCURRENCY` | `3` |
| Interview 超时 | `INTERVIEW_TIMEOUT_SECONDS` | `60.0` |
| Product Doc 超时 | `PRODUCT_DOC_TIMEOUT_SECONDS` | `120.0` |

### 前端运行时配置
- `VITE_API_URL`（默认 `http://localhost:8000`）

---

## 当前完成度与待完善

### 已实现
- ✅ Interview / Generation / Refinement Agent（LLM 驱动）
- ✅ LLM Tools + Tool 事件（读写/校验工具）
- ✅ SSE 事件流 + Token 统计
- ✅ 会话/消息/版本管理
- ✅ Plan/Task Schema 与 Planner
- ✅ DAG 执行引擎（已实现）
- ✅ 前端三栏视图 + 事件流 + 任务视图 + Token 展示
- ✅ CLI 多命令入口

### 待完善
- ⚠️ `validate_mobile_html` 仍为空实现
- ⚠️ Validator 任务依赖真实校验逻辑
- ⚠️ CLI 仅有 `dist/`，缺少可维护源码
- ⚠️ “计划执行”尚未在 API 暴露入口
- ⚠️ E2E 与端到端验证仍缺失

---

## 文档资源

- **产品规格**: `docs/spec/spec-01.md`
- **路线与阶段**: `docs/phases/INDEX.md`
- **设计系统**: `docs/design-system.md`

---

*此文档由代码与仓库结构分析生成。*
