# Instant Coffee 项目阶段性总结

> **生成时间**: 2026-01-31
> **项目版本**: 未统一标记（web package.json 为 0.0.0）
> **项目状态**: 核心流程可跑通，Agent/生成逻辑与前端体验仍在完善

---

## 项目概述

**Instant Coffee (速溶咖啡)** 是一个通过自然对话生成移动端优化页面的 AI 工具。项目采用 monorepo 架构，后端使用 Python FastAPI，前端使用 React + TypeScript，并包含 CLI 的构建产物目录。

---

## 技术栈

### 后端技术栈
| 技术 | 版本/说明 |
|------|----------|
| Python | 3.x |
| FastAPI | Web 框架 |
| SQLAlchemy | ORM |
| Pydantic | 数据验证 |
| SQLite | 数据库 |
| Anthropic API | Claude 规划器 |
| OpenAI API | 规划器/模型调用 |
| httpx | 外部 API 请求 |
| Server-Sent Events | 实时通信 |

### 前端技术栈
| 技术 | 版本 |
|------|------|
| React | 19.2.0 |
| TypeScript | 5.9.3 |
| Vite | 7.2.4 |
| React Router | 7.13.0 |
| Tailwind CSS | 4.1.18 |
| Radix UI | 组件库 |
| Lucide React | 0.563.0 |
| Sonner | 2.0.7 |
| Playwright | 1.58.1（截图/验证脚本） |

---

## 项目结构

```
instant-coffee/
├── packages/
│   ├── backend/                    # Python FastAPI 后端
│   │   ├── app/                     # 后端应用代码
│   │   │   ├── agents/              # AI Agent 系统
│   │   │   ├── api/                 # REST/SSE API 端点
│   │   │   ├── db/                  # 数据库层
│   │   │   ├── events/              # 事件系统
│   │   │   ├── executor/            # 任务执行引擎
│   │   │   ├── generators/          # 代码生成器
│   │   │   ├── planner/             # AI 规划器
│   │   │   ├── services/            # 业务逻辑服务
│   │   │   ├── config.py            # 配置管理
│   │   │   └── main.py              # 应用入口
│   │   ├── tests/                   # 后端测试
│   │   ├── instant-coffee.db        # SQLite 数据库
│   │   ├── instant-coffee-output/   # HTML 输出目录
│   │   └── venv/.venv               # Python 虚拟环境
│   │
│   ├── web/                         # React 前端
│   │   └── src/
│   │       ├── api/                 # API 客户端
│   │       ├── components/          # React 组件
│   │       ├── hooks/               # 自定义 Hooks
│   │       ├── pages/               # 页面组件
│   │       └── types/               # TypeScript 类型
│   │
│   └── cli/                         # CLI 构建产物
│       └── dist/
│
├── docs/                            # 项目文档
├── README.md
└── CLAUDE.md
```

---

## 已实现功能

### 1. 后端功能

#### 1.1 Agent 系统 (`app/agents/`)

| Agent | 文件 | 功能描述 |
|-------|------|----------|
| BaseAgent | `base.py` | Agent 基类，仅保存上下文（db/session/settings 等） |
| InterviewAgent | `interview.py` | 占位实现：直接回显或提示补充需求 |
| GenerationAgent | `generation.py` | 生成 Agent：输出简单 HTML 模板并写入文件 |
| RefinementAgent | `refinement.py` | 精炼 Agent：用 `<p>` 追加用户输入（占位逻辑） |
| AgentOrchestrator | `orchestrator.py` | 协调器：当前只串联 GenerationAgent 产出 |

**核心方法**：
- `GenerationAgent.generate()`: 生成简单 HTML 模板并保存到输出目录
- `RefinementAgent.refine()`: 简单地在 `</body>` 前追加 `<p>`
- `AgentOrchestrator.stream()`: 仅针对 GenerationAgent 的 SSE 事件流
- `AgentOrchestrator.stream_responses()`: 生成 HTML 并写入版本历史

#### 1.2 API 端点 (`app/api/`)

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/chat` | POST | 发送消息，支持 JSON/SSE 响应 |
| `/api/chat/stream` | GET | SSE 流式响应 |
| `/api/sessions` | GET/POST | 列出/创建会话 |
| `/api/sessions/{id}` | GET | 获取会话详情 |
| `/api/sessions/{id}/messages` | GET | 获取对话消息 |
| `/api/sessions/{id}/versions` | GET | 获取版本历史 |
| `/api/sessions/{id}/preview` | GET | 获取 HTML 预览 |
| `/api/sessions/{id}/rollback` | POST | 回滚到指定版本 |
| `/api/sessions/{id}/versions/{version_id}/revert` | POST | 兼容版回滚接口 |
| `/api/plan` | POST | 创建执行计划 |
| `/api/plan/{plan_id}/status` | GET | 获取计划状态 |
| `/api/task/{id}/retry` | POST | 重试失败任务 |
| `/api/task/{id}/skip` | POST | 跳过任务 |
| `/api/session/{id}/abort` | POST | 中断会话内活动计划 |
| `/api/settings` | GET/PUT | 获取/更新设置 |
| `/health` | GET | 健康检查 |

#### 1.3 数据库模型 (`app/db/models.py`)

| 模型 | 字段 | 说明 |
|------|------|------|
| **Session** | id, title, created_at, updated_at, current_version | 会话信息 |
| **Message** | id, session_id, role, content, timestamp | 对话消息 |
| **Version** | id, session_id, version, html, description, created_at | 页面版本 |
| **TokenUsage** | id, session_id, timestamp, agent_type, model, input_tokens, output_tokens, total_tokens, cost_usd | Token 消耗记录 |
| **Plan** | id, session_id, goal, status, created_at, updated_at | 执行计划 |
| **Task** | id, plan_id, title, description, agent_type, status, progress, depends_on, can_parallel, retry_count, error_message, result, started_at, completed_at, created_at | 计划任务 |
| **PlanEvent** | id, plan_id, event_type, message, payload, timestamp | 计划事件 |
| **TaskEvent** | id, task_id, event_type, agent_id, agent_type, agent_instance, message, progress, tool_name, tool_input, tool_output, payload, timestamp | 任务事件 |

**状态枚举**：
- Plan: `pending`, `in_progress`, `done`, `failed`, `aborted`
- Task: `pending`, `in_progress`, `done`, `failed`, `blocked`, `skipped`, `retrying`, `aborted`

#### 1.4 服务层 (`app/services/`)

| 服务 | 文件 | 核心方法 |
|------|------|----------|
| SessionService | `session.py` | create_session, get_session, update_session, list_sessions |
| MessageService | `message.py` | add_message, get_messages |
| VersionService | `version.py` | create_version, get_versions, rollback |
| PlanService | `plan.py` | create_plan, get_plan, upsert_plan_from_payload, recompute_status |
| TaskService | `task.py` | update_task, set_status, retry_task, skip_task, abort_plan |
| EventStoreService | `event_store.py` | record_event |
| ExportService | `export.py` | export_session |
| FilesystemService | `filesystem.py` | create_output_directory, save_html |
| TokenTrackerService | `token_tracker.py` | Token 使用追踪 |

#### 1.5 执行引擎 (`app/executor/`)

| 组件 | 文件 | 功能 |
|------|------|------|
| ExecutorManager | `manager.py` | 单例管理器，注册/注销执行器，支持中断 |
| TaskScheduler | `scheduler.py` | DAG 任务调度，依赖管理，并行就绪检测 |
| ParallelExecutor | `parallel.py` | 并行执行器 |
| TaskExecutor | `task_executor.py` | 单任务执行器 |
| RetryPolicy | `retry.py` | 指数退避重试策略 |

**TaskScheduler 核心方法**：
- `get_ready_tasks()`: 获取可并行执行的任务
- `mark_completed()`: 标记完成并解除依赖任务
- `mark_failed()`: 标记失败并阻塞依赖任务
- `_detect_cycles()`: 循环依赖检测

#### 1.6 规划器系统 (`app/planner/`)

| 组件 | 文件 | 功能 |
|------|------|------|
| BasePlanner | `base.py` | 抽象基类，JSON 解析，重试逻辑 |
| AnthropicPlanner | `anthropic_planner.py` | Claude API 规划器 |
| OpenAIPlanner | `openai_planner.py` | OpenAI API 规划器 |
| PlannerFactory | `factory.py` | 规划器工厂 |
| Prompts | `prompts.py` | 规划提示词 |

#### 1.7 事件系统 (`app/events/`)

**事件类型**：
- `AgentStartEvent`, `AgentProgressEvent`, `AgentEndEvent`
- `ToolCallEvent`, `ToolResultEvent`
- `PlanCreatedEvent`, `PlanUpdatedEvent`
- `TaskStartedEvent`, `TaskProgressEvent`, `TaskDoneEvent`
- `TaskFailedEvent`, `TaskRetryingEvent`, `TaskSkippedEvent`, `TaskBlockedEvent`
- `ErrorEvent`, `DoneEvent`

**EventEmitter 核心方法**：
- `emit()`: 发射事件并持久化
- `stream()`: SSE 流式输出
- `events_since()`: 获取增量事件

---

### 2. 前端功能

#### 2.1 API 客户端 (`src/api/client.ts`)

完整的类型化 API 客户端：
- `sessions`: 列表、获取、创建、消息、版本、回滚（含兼容回滚）
- `chat`: 发送消息、SSE 流式 URL
- `settings`: 获取、更新
- `tasks`: 重试、跳过

#### 2.2 自定义 Hooks (`src/hooks/`)

| Hook | 功能 |
|------|------|
| `useChat` | 聊天状态、SSE 流式接收、发送消息 |
| `useSession` | 会话数据、消息历史、版本管理 |
| `usePlan` | 计划状态、任务状态更新、事件处理 |
| `useSSE` | SSE 连接管理、自动重连、事件解析 |
| `useProjects` | 项目列表管理 |
| `useSettings` | 设置管理 |
| `useVirtualList` | 虚拟滚动 |
| `useOnlineStatus` | 在线状态检测 |
| `use-toast` | Toast 快捷调用 |

#### 2.3 页面组件 (`src/pages/`)

| 页面 | 功能 |
|------|------|
| `HomePage` | 首页，创建/选择项目 |
| `ProjectPage` | 主项目视图，三栏布局（聊天/事件、预览、版本） |
| `ExecutionPage` | 执行流程可视化，任务操作（重试/跳过） |
| `SettingsPage` | 应用设置 |

#### 2.4 UI 组件 (`src/components/`)

**自定义组件**：
- `ChatPanel`, `ChatInput`, `ChatMessage`
- `PreviewPanel`, `PhoneFrame`
- `ProjectCard`
- `VersionPanel`, `VersionTimeline`

**布局组件**：
- `Header`, `MainContent`

**事件流组件**：
- `EventList`, `EventItem`, `CollapsibleEvent`, `ProgressBar`, `StatusIcon`

**任务卡片组件**：
- `TaskCard`, `TaskCardList`, `AgentActivity`, `ToolCallLog`

**Todo 组件**：
- `TodoPanel`, `TodoItem`

**Shadcn UI 组件**：
- alert-dialog, avatar, badge, button, card, collapsible, dialog, dropdown-menu, input, label, resizable, scroll-area, select, separator, skeleton, slider, sonner, switch, tabs, textarea, toast, toaster, tooltip

#### 2.5 类型定义 (`src/types/`)

- `index.ts`: Message, Version, Project, SessionDetail, Settings, ChatResponse
- `events.ts`: 事件类型与类型守卫
- `plan.ts`: Task, Plan, TaskStatus（pending/in_progress/done/failed/blocked/skipped/retrying）

---

### 3. 测试覆盖 (`packages/backend/tests/`)

| 测试文件 | 覆盖内容 |
|----------|----------|
| `test_chat_stream_compat.py` | Chat 流式兼容性 |
| `test_event_protocol.py` | 事件协议验证 |
| `test_event_store.py` | 事件存储 |
| `test_events.py` | 事件系统 |
| `test_orchestrator_events.py` | 协调器事件 |
| `test_parallel_executor.py` | 并行执行 |
| `test_plan_task_services.py` | 计划和任务服务 |
| `test_planner.py` | 规划器 |
| `test_retry_policy.py` | 重试策略 |
| `test_task_scheduler.py` | 任务调度器 |

---

## 配置管理

### 后端配置 (`app/config.py`)

| 配置项 | 环境变量 | 默认值 |
|--------|----------|--------|
| 数据库 URL | `DATABASE_URL` | `sqlite:///./instant-coffee.db` |
| 输出目录 | `OUTPUT_DIR` | `instant-coffee-output` |
| 规划器提供商 | `PLANNER_PROVIDER` | - |
| 规划器模型 | `PLANNER_MODEL` | `gpt-4o-mini` |
| 规划器超时（秒） | `PLANNER_TIMEOUT_SECONDS` | `30.0` |
| OpenAI API Key | `OPENAI_API_KEY` | - |
| OpenAI Base URL | `OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| Anthropic API Key | `ANTHROPIC_API_KEY` | - |
| Anthropic Base URL | `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` |
| Anthropic API Version | `ANTHROPIC_API_VERSION` | `2023-06-01` |
| 默认 Base URL | `DEFAULT_BASE_URL` | - |
| 默认 Key | `DEFAULT_KEY` | - |
| 模型 | `MODEL` | `gpt-4o-mini` |
| 温度 | `TEMPERATURE` | `0.7` |
| 最大 Token | `MAX_TOKENS` | `1200` |
| 自动保存 | `AUTO_SAVE` | `true` |
| 最大并发任务 | `MAX_CONCURRENCY` | `3` |

---

## 核心特性

### 已实现
- ✅ SSE 实时流式通信
- ✅ 会话管理（创建、列表、详情）
- ✅ 消息历史记录
- ✅ 版本控制（创建、历史、回滚）
- ✅ 任务规划（DAG 调度）
- ✅ 并行任务执行
- ✅ 事件系统（发射、持久化、流式传输）
- ✅ 重试机制（指数退避）
- ✅ 任务控制（重试、跳过、中断）
- ✅ 移动端 HTML 生成（基础模板）
- ✅ Token 追踪（服务层）
- ✅ 文件导出（基础）
- ✅ React 前端界面
- ✅ 虚拟滚动
- ✅ 三栏布局（聊天/预览/版本）

### 进行中/待完善
- ⚠️ Interview Agent 完整实现
- ⚠️ Generation/Refinement Agent 完整 AI 实现
- ⚠️ 移动端样式规范完整落地
- ⚠️ CLI 源码与发布流程（当前仅有 dist 构建产物）
- ⚠️ E2E 测试体系
- ⚠️ 测试覆盖率提升

---

## 架构亮点

### 1. 事件驱动架构
- 统一的事件模型 (`BaseEvent`)
- SSE 实时推送到前端
- 事件持久化到数据库
- 类型安全的事件处理

### 2. DAG 任务调度
- 基于依赖的任务编排
- 循环依赖检测
- 并行执行优化
- 状态自动传播（完成→解除阻塞，失败→阻塞依赖）

### 3. 分层架构
```
API Layer → Service Layer → Data Layer
     ↓           ↓              ↓
   Events    Executor      Database
```

### 4. 可扩展设计
- Agent 抽象基类
- Planner 工厂模式
- 多 AI 提供商支持
- 配置驱动的行为

---

## 下一步计划

### 短期
1. 完善 Agent AI 实现（Generation/Refinement/Interview）
2. 完善移动端 HTML 生成规则
3. 补齐 CLI 源码与打包流程
4. 提升测试覆盖率与 E2E 用例

### 中期
1. 添加更多导出格式
2. 支持自定义移动端比例
3. 添加模板系统
4. 性能优化

### 长期
1. 多语言支持
2. 团队协作功能
3. 云端同步选项
4. 插件系统

---

## 文档资源

- **产品规格**: `docs/spec/spec-01.md`
- **开发路线**: `docs/phases/INDEX.md`
- **设计系统**: `docs/design-system.md`
- **各阶段文档**: `docs/phases/{backend,frontend,database}/`

---

*此文档由代码自动分析生成*
