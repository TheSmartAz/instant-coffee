# Instant Coffee - Claude 项目指南

## 项目概述

**Instant Coffee (速溶咖啡)** 是一个通过自然对话生成移动端优化页面的 AI 工具，支持 CLI、Web UI 和独立 Agent 引擎三种交互方式。

- **核心理念**: 像速溶咖啡一样快速便捷地生成移动端页面
- **技术栈**: Python/FastAPI (Backend) + React/Vite (Web) + Node.js (CLI) + Python Agent Engine (`ic`)
- **目标**: 零技术门槛，通过自然对话生成高质量移动端页面
- **当前版本**: v0.9 — Soul Agentic Loop (LangGraph → Tool-Calling Loop 重构)

## 项目结构

```
instant-coffee/
├── packages/
│   ├── backend/           # Python FastAPI 后端
│   │   └── app/
│   │       ├── api/       # 18 个路由模块
│   │       ├── engine/    # v0.9 Engine 编排器 (替代 LangGraph)
│   │       ├── agents/    # Legacy Agent 系统
│   │       ├── db/        # SQLAlchemy 模型 + 迁移
│   │       ├── events/    # 90+ 事件类型 + SSE 发射器
│   │       ├── services/  # 30+ 业务服务
│   │       ├── schemas/   # Pydantic 请求/响应模型
│   │       ├── renderer/  # HTML→React SSG 构建管线
│   │       ├── llm/       # 模型目录 + 客户端工厂
│   │       ├── middleware/ # 速率限制
│   │       └── utils/     # HTML/CSS/日期工具
│   │
│   ├── agent/             # 独立 Agent 引擎 (ic 包)
│   │   └── src/ic/
│   │       ├── soul/      # 核心 agentic loop + 上下文管理
│   │       ├── tools/     # 8 个核心工具 (file/shell/ask/think/todo/skill/subagent/web)
│   │       ├── llm/       # LLM provider 抽象 (OpenAI/Anthropic)
│   │       └── ui/        # CLI I/O + Console
│   │
│   ├── web/               # React + Vite + Tailwind + shadcn/ui
│   │   └── src/
│   │       ├── pages/     # HomePage, ProjectPage, ExecutionPage, SettingsPage
│   │       ├── components/ # 50+ 组件 (Chat, Preview, Panel, Event)
│   │       ├── hooks/     # 30+ 自定义 hooks
│   │       ├── api/       # API 客户端 + 领域模块
│   │       ├── types/     # 事件类型定义 (须与后端同步)
│   │       └── lib/       # 工具函数
│   │
│   └── cli/               # Node.js CLI (编译后 JS in dist/)
│       └── dist/
│           ├── commands/  # chat, history, export, rollback, stats, clean, migrate
│           └── utils/     # api-client, browser, logger
│
├── docs/
│   ├── spec/              # 产品规格 (spec-01 ~ spec-09)
│   └── phases/            # 开发阶段文档 (v01 ~ v09)
│       └── INDEX.md       # 开发路线总览
│
├── render.yaml            # Render 部署配置
├── AGENTS.md              # 架构概览 + 运行时流程
└── .env.example           # 环境变量模板
```

## 架构概览

### Engine 编排器 (v0.9 — 当前架构)

v0.9 用 tool-calling loop 替代了 LangGraph 编排。核心在 `packages/backend/app/engine/`:

- **orchestrator.py** — `EngineOrchestrator`: 包装 agent Engine，管理子 agent 会话，通过 `stream_responses()` 异步生成 SSE 事件
- **db_tools.py** — DB 持久化文件工具 (`DBWriteFile`, `DBEditFile`, `DBMultiEditFile`)，将生成的 HTML 写入数据库
- **event_bridge.py** — 将 agent 事件桥接到后端 `EventEmitter`，映射 tool call/result/token 事件
- **prompts.py** — 动态构建 system prompt，注入 product doc、页面摘要、memory 上下文
- **web_user_io.py** — Web 端 ask_user 工具的实现，管理待回答问题队列
- **deferred_buffer.py** — 延迟批量写入，减少 DB 往返
- **config_bridge.py** — 将后端 Settings 转换为 agent Config

### Agent 引擎 (`packages/agent/src/ic/`)

独立的 Python 包，可 CLI 运行也可被后端嵌入:

- **soul/engine.py** (1151 行) — 核心 agentic loop: 多轮对话、工具调用、上下文截断、token 追踪、流式输出
- **soul/context.py** — 上下文构建: 文件注入、git 状态、product doc、memory
- **soul/context_injector.py** — 自动上下文发现
- **soul/skills.py** — Skill 加载系统
- **tools/** — 8 个核心工具: ReadFile, GlobFiles, GrepFiles, Shell, Think, Todo, AskUser, CreateSubAgent
- **llm/provider.py** — 统一 LLM 接口 (OpenAI/Anthropic)，重试 + 指数退避

### 事件系统

90+ 事件类型，定义在 `packages/backend/app/events/`:
- Agent 生命周期: `agent_start`, `agent_progress`, `agent_end`
- 工具执行: `tool_call`, `tool_result`, `tool_progress`
- 页面事件: `page_created`, `page_version_created`, `page_preview_ready`
- Product Doc: `product_doc_generated`, `product_doc_updated`, `product_doc_confirmed`
- 工作流: `brief_start`, `generate_start`, `build_start`, `verify_start`
- Run 生命周期: `run_created`, `run_started`, `run_completed`, `run_failed`

**重要**: `packages/web/src/types/events.ts` 必须与后端事件模型保持同步。

## 技术栈

### Backend (Python)
- **框架**: FastAPI 0.110+
- **数据库**: SQLite (默认) / PostgreSQL
- **ORM**: SQLAlchemy 2.0+
- **AI**: OpenAI / Anthropic 客户端
- **验证**: Pydantic 2.7.4+
- **LangGraph**: 1.0+ (legacy，正在移除)
- **运行**: `uvicorn app.main:app --reload`

### Agent Engine (Python `ic` 包)
- **Python**: 3.11+
- **LLM**: openai SDK (统一接口)
- **UI**: Rich (终端输出)
- **构建**: Hatch
- **入口**: `ic` CLI 命令

### Web (React)
- **框架**: React 19 + React Router 7
- **构建**: Vite 7 + TypeScript 5.9
- **样式**: Tailwind CSS 4 + shadcn/ui (Radix UI)
- **Markdown**: react-markdown + remark-gfm
- **Diff**: diff 库
- **测试**: Playwright (e2e)

### CLI (Node.js)
- **框架**: Commander.js 12
- **HTTP**: Axios
- **输出**: Chalk, Ora, Inquirer
- **状态**: 仅编译后 JS，无 TS 源码签入

## 数据库

15 张核心表，定义在 `packages/backend/app/db/models.py`:

| 表 | 用途 |
|---|------|
| `sessions` | 项目容器 (标题、版本、产品类型、复杂度、构建状态、美学评分) |
| `session_runs` | Run 生命周期 (状态机: queued→running→waiting_input→completed/failed/cancelled) |
| `threads` | 会话内的对话线程 |
| `messages` | 聊天消息 (role, content, metadata) |
| `versions` | 页面版本历史 |
| `product_docs` | 产品文档 (content, structured JSON, 状态: draft/confirmed/outdated) |
| `product_doc_histories` | 文档版本历史 (pin/release 追踪) |
| `pages` | 多页项目中的单个页面 |
| `page_versions` | 页面版本快照 |
| `project_snapshots` | 完整项目快照 |
| `token_usage` | Token 消耗追踪 (input/output/cost) |
| `project_memory` | 持久化键值存储 (会话恢复) |
| `session_events` | 事件审计日志 |

DB 在 FastAPI 启动时自动初始化，无需手动运行迁移命令。

## 主要 API 端点

| 路径 | 方法 | 用途 |
|------|------|------|
| `/api/chat` | POST | 发送消息，流式返回 |
| `/api/chat/stream` | GET | SSE 流式端点 |
| `/api/sessions` | GET/POST | 会话列表/创建 |
| `/api/sessions/{id}` | GET/PUT/DELETE | 会话详情/更新/删除 |
| `/api/sessions/{id}/rollback` | POST | 版本回滚 |
| `/api/sessions/{id}/preview` | GET | HTML 预览 |
| `/api/pages` | GET/POST | 页面管理 |
| `/api/product-doc` | GET/POST/PUT | 产品文档管理 |
| `/api/runs` | GET/POST | Run 生命周期 |
| `/api/runs/{id}/resume` | POST | 恢复中断的 Run |
| `/api/build` | POST | 触发构建 (React SSG) |
| `/api/assets/upload` | POST | 资源上传 |
| `/api/snapshots` | GET/POST | 项目快照 |
| `/api/data` | GET/POST | App 数据层 |
| `/api/settings` | GET | 配置信息 |
| `/api/health` | GET | 健康检查 |

## 本地开发

### 后端
```bash
cd packages/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 编辑添加 API key
uvicorn app.main:app --reload
```

### Web
```bash
cd packages/web
npm install
npm run dev
# 默认 VITE_API_URL=http://localhost:8000
```

### CLI
```bash
cd packages/cli
node dist/index.js
# 或 npm run dev
# 环境变量: BACKEND_URL, OUTPUT_DIR, VERBOSE
```

### Agent 引擎 (独立运行)
```bash
cd packages/agent
pip install -e .
ic  # 启动 CLI agent
```

## 环境变量

```bash
# API Keys (至少配置一个)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DEFAULT_KEY=

# Server
BACKEND_HOST=http://localhost
BACKEND_PORT=8000

# Database
DATABASE_URL=sqlite:///./instant-coffee.db

# CORS
CORS_ALLOW_ORIGINS=["*"]

# Output
OUTPUT_DIR=./instant-coffee-output

# Feature Flags
USE_LANGGRAPH=false
ENABLE_AESTHETIC_SCORING=false
ENABLE_MCP=false

# Web
VITE_API_URL=http://localhost:8000
```

## 开发阶段

项目通过 spec 版本迭代，详见 `docs/phases/INDEX.md`:

| 版本 | 状态 | 核心特性 |
|------|------|----------|
| v0.1 | ✅ | CLI + Backend Core + Database |
| v0.2 | ✅ | Web Frontend + Planner + Executor |
| v0.3 | ✅ | LLM Calling + Tools + Real Agents |
| v0.4 | ✅ | Multi-Page + Product Doc + Workbench |
| v0.5 | ✅ | Version Management + Responses API |
| v0.6 | ✅ | Skills + Orchestrator + Multi-model + Data Protocol + Style Ref |
| v0.7 | ✅ | LangGraph + React SSG + Scene Capabilities + Component Registry |
| v0.8 | ✅ | Run-Centric Backend + App Data Layer + Verify Gate + Tool Policy |
| v0.9 | 🚧 | Soul Agentic Loop — LangGraph → Tool-Calling Loop 重构 |

### v0.9 关键路径
```
B1 (Tool Foundation ✅) → B2 (Core Tools ✅) → B3 (Interview & Ask User)
→ B4 (Context Management) → B5 (Agentic Loop Core) → B7 (API Integration & LangGraph Cleanup)
→ F1 (Product Doc Update Card)

独立: B6 (LLM Layer Simplification ✅)
```

## 代码规范

### Python (Backend + Agent)
- Ruff 格式化 (line-length 100)
- 类型提示 (Type Hints)
- Docstrings (Google 风格)
- 异步优先 (async/await)
- Python 3.11+

### TypeScript (Web)
- ESLint + TypeScript strict mode
- Tailwind CSS 4 + shadcn/ui 组件
- React hooks 模式
- `@/` 别名 → `src/`

### CLI (Node.js)
- 仅编译后 JS 签入 (`dist/`)
- 新功能建议添加 TS 源码 + 构建步骤

## 重要约束

### 移动端规范
- 视口: 9:19.5 比例
- 容器: max-width 430px
- 按钮: 最小高度 44px
- 字体: 正文 16px, 标题 24-32px
- 滚动条: 隐藏 (`.hide-scrollbar`)
- 生成产物: 单文件 HTML (内联 CSS/JS)

### 事件同步
- 后端事件模型: `packages/backend/app/events/models.py`
- 前端事件类型: `packages/web/src/types/events.ts`
- 两者必须保持同步，新增事件时两边都要更新

### 不要编辑的文件
- `packages/cli/node_modules/`
- `packages/backend/venv/`, `__pycache__/`, `.pytest_cache/`
- `*.db` 文件
- `instant-coffee-output/` 目录

## 测试

- **Backend**: `pytest` (从 `packages/backend` 运行)
- **Agent**: `pytest` (从 `packages/agent` 运行，含 1100+ 行综合测试)
- **Web**: `npm run lint` + Playwright e2e 测试
- **CLI**: 无测试

## 部署

通过 `render.yaml` 配置 Render 部署:
- **API**: Python web service (`uvicorn app.main:app`)
- **Web**: 静态站点 (Vite build → `dist/`)
- **DB**: Render PostgreSQL

## 参考文档

- **产品规格**: `docs/spec/` (spec-01 ~ spec-09)
- **开发路线**: `docs/phases/INDEX.md`
- **架构概览**: `AGENTS.md`
- **API 文档**: 后端运行后访问 http://localhost:8000/docs

---

**项目版本**: v0.9
**最后更新**: 2026-02-13
**当前状态**: Soul Agentic Loop 重构进行中
