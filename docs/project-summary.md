# Instant Coffee 项目阶段性总结

> **生成时间**: 2026-02-08
> **项目版本**: web 0.0.0 / cli 0.1.0 / backend 无独立版本标记
> **项目状态**: v0.7 能力已落地（多页 / Product Doc / 资产 / Build / Data Tab / Aesthetic Scoring / LangGraph skeleton）；默认仍走 legacy orchestrator；已补齐 Product Doc API 的磁盘 fallback（避免 DB 记录缺失时 404）；CLI 仍仅有 dist 产物

---

## 项目概述

**Instant Coffee (速溶咖啡)** 是一个通过自然对话生成 **移动端优先的多页 HTML/静态站点** 的 AI 工具。项目采用 monorepo 架构，后端为 FastAPI + SQLite + 多模型 LLM 调度，前端为 Vite + React + Tailwind + shadcn，CLI 采用 Node（Commander）并当前仅保留 `dist/` 构建产物。系统支持 Product Doc、Multi‑page Sitemap、页面版本与快照、资产管理、React SSG 构建与预览、SSE 事件流、Data Tab 交互数据回传，以及可选的 LangGraph 工作流骨架。

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
| LangGraph | 可选工作流编排骨架（USE_LANGGRAPH） |
| openai | LLM 调用（Responses/Chat API 可切换） |
| httpx | 规划器与视觉服务请求 |
| Server-Sent Events | 实时事件流 |
| python-dotenv | 可选环境变量加载 |
| Pillow / BeautifulSoup4 | 图片与 HTML 处理 |

### 前端技术栈
| 技术 | 版本/说明 |
|------|----------|
| React | 19.2.0 |
| TypeScript | 5.9.3 |
| Vite | 7.2.4 |
| React Router | 7.13.0 |
| Tailwind CSS | 4.1.18 |
| Radix UI + shadcn | 组件库 |
| Sonner | Toast |
| React Resizable Panels | 分栏布局 |
| react-markdown / diff | 文档/差异显示 |
| Playwright | E2E 测试 |

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
│   ├── backend/
│   │   ├── app/
│   │   │   ├── agents/              # Interview / ProductDoc / Generation / Refinement / ...
│   │   │   ├── api/                 # REST/SSE 端点
│   │   │   ├── db/                  # 数据库层 + 迁移
│   │   │   ├── events/              # 事件模型/发射器
│   │   │   ├── executor/            # DAG 执行引擎
│   │   │   ├── generators/          # HTML 验证
│   │   │   ├── graph/               # LangGraph skeleton
│   │   │   ├── llm/                 # LLM 客户端 + 模型池
│   │   │   ├── planner/             # Planner（OpenAI/Anthropic）
│   │   │   ├── renderer/            # React SSG 构建器 + 模板
│   │   │   ├── schemas/             # API/领域 Schema
│   │   │   ├── services/            # 业务服务（产品文档/版本/资产/快照/…）
│   │   │   ├── utils/               # HTML/样式/守卫/数据协议
│   │   │   └── main.py              # 应用入口
│   │   ├── tests/                   # 后端测试 + e2e
│   │   └── requirements.txt
│   ├── web/                         # Vite + React 前端
│   └── cli/                         # CLI 构建产物（dist/）
├── docs/                            # 规格 / 阶段文档 / 总结
└── README.md
```

---

## 核心运行流程

### 1) Chat / Orchestration
1. `POST /api/chat` 或 `GET /api/chat/stream` 接收用户输入（支持 style reference 图片/Token、指定页面、生成模式）。
2. Orchestrator 决策路径：
   - 首次对话触发 Interview；
   - 基于意图/复杂度/场景检测生成或更新 Product Doc；
   - Multi‑page 决策 → Sitemap → Page 创建；
   - Generation / Refinement / Expander / Style Refiner / Validator 执行。
3. 页面结果写入 PageVersion；必要时写入 Export/组件目录，并触发事件。
4. SSE 事件与响应字段（preview_url / preview_html / affected_pages / action）同步前端。

### 2) Plan + Task 执行
1. Planner 生成 DAG 任务（Plan / Task），EventStore 持久化事件。
2. ParallelExecutor 进行并行执行，支持 retry/skip/abort。
3. 任务状态与进度通过 SSE 回推至前端，支持 UI 操作。

### 3) Build / Preview（React SSG）
1. `POST /api/sessions/{id}/build` 触发 React SSG 构建；输出到 `~/.instant-coffee/sessions/<id>/dist`。
2. `GET /preview/{session_id}` 直接预览 build 产物（支持多页路径）。
3. Build 过程写入 build.log 并通过 build SSE 事件流展示状态。

### 4) Export / Files
1. ExportService 将页面导出到 `OUTPUT_DIR/<session_id>`，生成 `index.html` / `pages/*.html` / `assets/site.css` / 组件/数据协议脚本。
2. `/api/sessions/{id}/files` & `/files/{path}` 为 CodePanel 提供文件树/内容。

---

## 后端功能

### 1) Agent / Orchestrator
| Agent | 功能摘要 |
|-------|----------|
| InterviewAgent | 结构化问题采集（支持 `<INTERVIEW_ANSWERS>`） |
| ProductDocAgent | 生成/更新产品文档与结构化字段 |
| MultipageDecider / SitemapAgent | 多页决策与站点地图 |
| GenerationAgent | 多页 HTML 生成 + 版本写入 |
| RefinementAgent | 增量改写已有页面 |
| ExpanderAgent | 结构扩展/补全 |
| StyleRefiner / AestheticScorer | 视觉评分与优化（可选） |
| Validator | HTML 校验与 fallback 摘要 |
| ComponentPlanner / Builder / Registry | 组件库存与 schema 校验 |
| AgentOrchestrator | 路由与任务编排（legacy） |
| LangGraphOrchestrator | LangGraph skeleton（可选） |

### 2) LLM 客户端与多模型调度
- OpenAIClient 支持 Responses/Chat 双模式与 Token 统计。
- ModelCatalog + ModelPool 支持多模型池、失败回退、角色级路由（classifier/writer/validator 等）。
- 支持视觉能力检测（style reference / image input）。

### 3) Product Doc / Skills 体系
- ProductDoc + History + Pin/Retention；支持 doc tier（checklist/standard/extended）。
- SkillsRegistry 提供 manifests / guardrails / style profiles / state contracts。
- Scenario Detector 与 Doc Tier/Complexity 路由。

### 4) 页面与版本管理
- Page / PageVersion 多页模型，支持 pin/unpin 与 retention。
- ProjectSnapshot 实现跨页回滚（替代旧的单页 rollback）。
- Version/Session 兼容旧单页数据（v04 迁移）。

### 5) Build / Renderer
- React SSG Builder 将 page schema + component registry + tokens 生成静态站。
- 自动注入 Mobile Shell，保障移动端可用性。

### 6) Data Protocol & App Mode
- DataProtocolGenerator 注入 data-store/client 脚本与 state contract。
- Preview 框架通过 postMessage 回传数据，用于 Data Tab 展示。

### 7) 资产与文件
- AssetRegistry 支持 logo/background/style_ref/product_image 上传与引用。
- FileTreeService 输出代码面板所需文件树（pages + site.css + product doc）。

### 8) 事件系统
- EventEmitter + EventStore 将结构化事件持久化（session_events + seq）。
- 事件类型覆盖：Agent/Tool/Plan/Task、ProductDoc、Page、Snapshot、Build、Aesthetic 等。

---

## API 端点（核心）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/chat` | POST | 聊天请求（含 preview / action 字段） |
| `/api/chat/stream` | GET/POST | SSE 流式响应 |
| `/api/sessions` | GET/POST | 会话列表/创建 |
| `/api/sessions/{id}` | GET/DELETE | 会话详情/删除 |
| `/api/sessions/{id}/messages` | GET/DELETE | 消息读取/清空 |
| `/api/sessions/{id}/versions` | GET | 版本列表（兼容旧版） |
| `/api/sessions/{id}/preview` | GET | 预览 HTML |
| `/api/sessions/{id}/metadata` | GET/PATCH/DELETE | Graph State / Build 状态 |
| `/api/sessions/{id}/pages` | GET | 页面列表 |
| `/api/pages/{id}` | GET | 页面详情 |
| `/api/pages/{id}/versions` | GET | 页面版本 |
| `/api/pages/{id}/preview` | GET | 页面预览 |
| `/api/pages/{id}/versions/{ver}/preview` | GET | 版本预览 |
| `/api/pages/{id}/versions/{ver}/pin` | POST | 版本 Pin/Unpin |
| `/api/sessions/{id}/product-doc` | GET | 产品文档（DB 缺失时回退读取 `OUTPUT_DIR/<session_id>/product-doc.json`） |
| `/api/sessions/{id}/product-doc/history` | GET | 文档历史（DB 缺失且磁盘有 doc 时返回空历史） |
| `/api/sessions/{id}/product-doc/history/{id}` | GET | 文档历史详情 |
| `/api/sessions/{id}/product-doc/history/{id}/pin` | POST | 历史 Pin/Unpin |
| `/api/sessions/{id}/snapshots` | GET/POST | 项目快照列表/创建 |
| `/api/sessions/{id}/snapshots/{sid}` | GET | 快照详情 |
| `/api/sessions/{id}/snapshots/{sid}/rollback` | POST | 快照回滚 |
| `/api/sessions/{id}/assets` | GET/POST | 资产列表/上传 |
| `/api/sessions/{id}/assets/{aid}` | GET/DELETE | 资产详情/删除 |
| `/api/sessions/{id}/files` | GET | 文件树 |
| `/api/sessions/{id}/files/{path}` | GET | 文件内容 |
| `/api/sessions/{id}/schemas` | GET | 页面 Schema 列表 |
| `/api/sessions/{id}/schemas/{slug}` | GET | 单页 Schema |
| `/api/sessions/{id}/registry` | GET | 组件注册表 |
| `/api/sessions/{id}/tokens` | GET | Style Tokens |
| `/api/sessions/{id}/build` | POST/DELETE | 触发/取消 Build |
| `/api/sessions/{id}/build/status` | GET | Build 状态 |
| `/api/sessions/{id}/build/logs` | GET | Build 日志 |
| `/api/sessions/{id}/build/stream` | GET | Build SSE |
| `/api/plan` | POST | 生成计划 |
| `/api/plan/{id}/status` | GET | 计划状态 |
| `/api/task/{id}/retry` | POST | 任务重试 |
| `/api/task/{id}/skip` | POST | 任务跳过 |
| `/api/session/{id}/abort` | POST | 中断活跃计划 |
| `/api/sessions/{id}/events` | GET | Session Event 拉取 |
| `/api/settings` | GET/PUT | 运行时设置 |
| `/api/migrations/v04` | POST | v04 数据迁移 |
| `/preview/{session_id}` | GET | Build 预览入口 |
| `/health` | GET | 健康检查 |

---

## 数据库模型（关键）

| 模型 | 说明 |
|------|------|
| Session / Message / Version | 会话、消息、旧版单页版本 |
| Page / PageVersion | 多页与页面版本（pin/retention） |
| ProductDoc / ProductDocHistory | 产品文档与历史版本 |
| ProjectSnapshot / SnapshotPage | 跨页快照与回滚 |
| Plan / Task | 计划与任务 |
| SessionEvent / Sequence | 事件持久化与序号 |
| TokenUsage | Token & 费用统计 |

**状态枚举**：
- Plan: `pending` / `in_progress` / `done` / `failed` / `aborted`
- Task: `pending` / `in_progress` / `done` / `failed` / `blocked` / `skipped` / `retrying` / `aborted` / `timeout`
- ProductDoc: `draft` / `confirmed` / `outdated`
- Build: `pending` / `building` / `success` / `failed`

---

## 前端功能

### 1) 页面与布局
- HomePage / ProjectPage / ExecutionPage / SettingsPage。
- 三栏工作台：Chat + Workbench + 事件流/任务。

### 2) Workbench 面板
- Preview：支持 Live/Build 切换、Page Selector、移动端外框、Build 状态、Aesthetic Score。
- Code：文件树 + 文件内容查看（index/pages/site.css/product-doc）。
- Product Doc：文档展示、历史版本、diff 与 pin。

### 3) Data Tab / App Mode
- App Mode 将预览中的交互状态/事件/提交记录回传到 Data Tab。
- 按场景（电商/旅行/说明书/看板/landing）过滤展示。

### 4) Chat 与资产
- Interview Widget（结构化问答）。
- Chat 支持资产上传、style reference、页面引用（@page）。

### 5) 事件与任务视图
- EventList / ToolCall / ToolResult / Progress / Status。
- TaskCard / AgentActivity / ToolCallLog。

---

## CLI 功能（`packages/cli/dist`）

**可用命令**：
- `chat`：交互式对话（SSE 优先）
- `history`：历史会话查看
- `export`：导出内容
- `rollback`：回滚版本（旧版单页）
- `stats`：统计信息
- `clean`：清理输出
- `migrate-v04`：运行 v04 数据迁移

**运行时配置**：`BACKEND_URL`, `OUTPUT_DIR`, `VERBOSE`

> CLI 仅保留编译产物，TS 源码未在仓库中。

---

## 测试覆盖

- **Backend 单元测试**：agents/orchestrator、planner、model pool、product doc、component registry、mobile shell、data protocol、files/pages API、event store 等。
- **Backend E2E**：full generation、multi-model routing、product doc tiers、chat images、style reference、aesthetic scoring、data protocol 等。
- **Web**：Playwright E2E（Data Tab、Image Upload、Preview Bridge 等）。

---

## 配置管理

### 后端环境变量（`app/config.py`）
| 配置项 | 环境变量 | 默认值 |
|--------|----------|--------|
| 数据库 | `DATABASE_URL` | `sqlite:///./instant-coffee.db` |
| 输出目录 | `OUTPUT_DIR` | `instant-coffee-output` |
| 规划器 | `PLANNER_PROVIDER` / `PLANNER_MODEL` | `openai` / `kimi-k2.5` |
| OpenAI Key | `OPENAI_API_KEY` / `DEFAULT_KEY` / `DMX_API_KEY` | - |
| OpenAI Base | `OPENAI_BASE_URL` | model catalog 默认值 |
| OpenAI 模式 | `OPENAI_API_MODE` | `responses` |
| Timeout/Retry | `OPENAI_TIMEOUT_SECONDS` / `OPENAI_MAX_RETRIES` / `OPENAI_BASE_DELAY` | 60 / 2 / 1.0 |
| 模型 | `MODEL` / `MODEL_*` | model catalog 默认值 |
| 模型池 | `MODEL_POOLS` / `MODEL_FAILURE_*` | 内置默认池 |
| LangGraph | `USE_LANGGRAPH` | false |
| Style Extractor | `ENABLE_STYLE_EXTRACTOR` | true |
| Aesthetic | `ENABLE_AESTHETIC_SCORING` / `AESTHETIC_THRESHOLDS` | false / {} |
| 并发与超时 | `MAX_CONCURRENCY` / `TASK_TIMEOUT_SECONDS` | 3 / 600 |
| 迁移 | `MIGRATE_V04_ON_STARTUP` | false |
| Interview / ProductDoc 超时 | `INTERVIEW_TIMEOUT_SECONDS` / `PRODUCT_DOC_TIMEOUT_SECONDS` | 180 / 180 |

### 前端运行时配置
- `VITE_API_URL`（默认 `http://localhost:8000`）

---

## 当前完成度与待完善

### 已实现
- ✅ 多页生成 + PageVersion 管理
- ✅ Product Doc + 历史版本 + Pin
- ✅ Product Doc API 磁盘 fallback（DB 缺失时读取产物并返回）
- ✅ Asset Registry + 预览/引用
- ✅ React SSG Build + Preview + Mobile Shell
- ✅ Data Tab / App Mode 交互数据回传
- ✅ 多模型池与失败回退
- ✅ SSE 事件流与持久化
- ✅ LangGraph skeleton（可选）

### 待完善
- ⚠️ LangGraph 仍为骨架流程，默认走 legacy orchestrator
- ⚠️ Validator 规则仍偏基础，守卫规则需持续扩展
- ⚠️ CLI 仅保留 dist 构建产物，缺少可维护源码
- ⚠️ 更完整的端到端 CI/发布流程仍待补齐

---

## 文档资源

- **产品规格**: `docs/spec/`
- **路线与阶段**: `docs/phases/INDEX.md`
- **设计系统**: `docs/design-system.md`

---

*此文档由代码与仓库结构分析生成。*
