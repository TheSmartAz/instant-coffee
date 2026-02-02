# Instant Coffee - 技术规格说明书 (Spec v0.4)

**项目名称**: Instant Coffee (速溶咖啡)
**版本**: v0.4 - 多页面生成能力
**日期**: 2026-02-01
**文档类型**: Technical Specification Document (TSD)

---

## 文档变更历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v0.4 | 2026-02-01 | 多页面生成能力规划与实现方案 | Planning |

---

## 设计决策访谈记录 (2026-02-01)

本节记录多页面生成实现前的关键设计决策与取舍。

### 核心决策

| 问题 | 决策 | 说明 |
|------|------|------|
| 多页面如何触发 | AutoMultiPageDecider + 显式 override | 默认自动决策，CLI/Web 可显式强制单页或多页 |
| 版本管理 | 新增 Page / PageVersion | 保持现有 Session/Version 兼容，避免破坏单页逻辑 |
| 导出结构 | `index.html` + `pages/{slug}.html` + `assets/site.css` | 保留单页预览入口，同时支持多页面导航与共享样式 |
| 生成策略 | 先 Sitemap/IA，再并行生成 | 先统一信息架构与导航，再并行产出每页 |
| 页面一致性 | 共享设计系统 + 导航模板 | 通过 `global_style` 与 `nav` 统一风格 |
| 失败处理 | 单页失败不阻塞其它页 | Planner/Executor 允许局部失败并提供重试/跳过 |
| 计划执行 | Plan 创建即执行（默认） | POST /api/plan 直接启动执行，支持后续扩展显式 run |

### 详细问答

**Q: 多页面与单页面如何共存？**
> A: 默认仍是单页面流；多页面由显式参数或语义识别触发。历史单页会被迁移为一个默认 Page。

**Q: 每页之间如何保持一致风格？**
> A: 先用 Sitemap/IA 产出 `global_style`（色板、字体、组件基线）和 `nav`，每页生成时注入。

**Q: 多页面如何导出与预览？**
> A: 导出时生成 `index.html` 与 `pages/{slug}.html`，`index.html` 作为导航入口。

**Q: 自动多页如何触发且可回退？**
> A: 增加 AutoMultiPageDecider 输出结构化决策。高置信度自动多页，低置信度走单页或先确认页面清单；用户可一句话回退为单页。

---

## 目录

1. [版本概述](#1-版本概述)
2. [设计决策访谈记录](#设计决策访谈记录-2026-02-01)
3. [架构设计](#3-架构设计)
4. [数据模型与版本管理](#4-数据模型与版本管理)
5. [Planner 与 Agent 设计](#5-planner-与-agent-设计)
6. [执行与并发策略](#6-执行与并发策略)
7. [API 设计](#7-api-设计)
8. [前端与 CLI 交互](#8-前端与-cli-交互)
9. [事件与观测](#9-事件与观测)
10. [实施拆分](#10-实施拆分)
11. [文件变更清单](#11-文件变更清单)
12. [验收标准](#12-验收标准)

---

## 1. 版本概述

### 1.1 版本定位

**Spec v0.4** 在 v0.3 的单页面生成基础上，引入 **多页面生成能力**，支持：
- 一次生成多页（首页/关于/服务/联系等）
- 并行生成与局部失败重试
- 页面级版本管理与导出
- 页面级预览与迭代

### 1.2 与 v0.3 的关系

| v0.3 (现有) | v0.4 (本版本) |
|-------------|--------------|
| 单页 Version | Page + PageVersion |
| 单页预览与导出 | 多页预览与导出 |
| Planner 任务执行 | 多页规划 + 并行生成 |

### 1.3 设计原则

1. **单页兼容**: 不破坏现有单页流程与 API。
2. **页面自治**: 每页有独立版本历史与修订能力。
3. **一致风格**: 多页面共享设计系统与导航结构。
4. **可观测**: 任务级、页面级事件可追踪。

---

## 3. 架构设计

### 3.1 整体流程

```
用户输入 (multi_page)
    ↓
InterviewAgent (收集全局需求 + 页面范围)
    ↓
SitemapAgent / IA 产出页面清单 + nav + global_style
    ↓
Planner 生成任务图 (每页一个 Generation 任务)
    ↓
ParallelExecutor 并行执行
    ↓
PageVersion 保存 + Page 预览
    ↓
ExportService 导出多页面
```

### 3.2 分层结构

```
API Layer
  /api/chat (可触发多页面)
  /api/plan (生成多页面任务)

Agent Layer
  InterviewAgent
  SitemapAgent (新增)
  GenerationAgent
  RefinementAgent

Service Layer
  PageService (新增)
  PageVersionService (新增)
  ExportService (扩展)
```

---

## 4. 数据模型与版本管理

### 4.1 新增数据表

**Page**
- `id` (UUID)
- `session_id`
- `title`
- `slug`
- `description`
- `order_index`
- `current_version_id` (FK → PageVersion.id)
- `created_at`, `updated_at`

**PageVersion**
- `id` (int)
- `page_id`
- `version`
- `html`
- `description`
- `created_at`

> 约束: `Unique(page_id, version)`

### 4.2 兼容策略

**字段语义与约束**
- `Page.current_version_id` 指向当前 `PageVersion.id`（不使用 version number 指针）。
- `Unique(session_id, slug)`：同一 session 内 slug 唯一。
- `slug` 仅允许 `[a-z0-9-]`，最大长度 40；服务端统一 sanitize（lowercase + replace + trim）。

**旧数据迁移规则（可执行）**
对每个已有 Session：
1) 创建默认 Page：`title="首页"`, `slug="index"`, `order_index=0`。
2) 取该 Session 的最新 `Version` 作为 PageVersion v1。
3) `Page.current_version_id = newly_created_page_version.id`。

**旧接口行为定义**
- `GET /api/sessions/{id}/preview`：继续返回默认 Page（index）的当前版本。
- `GET /api/sessions/{id}/versions`：若保留，仅代表默认 Page 的历史；标记为 deprecated。

**兼容性约束**
- 现有 `Version` 保持不变；多页面启用后，PageVersion 为新主线。
- Session 继续保留 `current_version` 以兼容旧逻辑，但只用于默认 Page。

---

## 5. Planner 与 Agent 设计

### 5.1 Planner 任务结构

Planner 在 multi_page 模式下输出：

```
Task 0: AutoMultiPageDecider (可选，决定单页/多页)
Task 1: Interview (可选)
Task 2: Sitemap / IA (依赖 Task 1)
Task 3..N: Generation (每页一个，依赖 Task 2，可并行)
Task N+1..: Validator (每页一个，可并行)
Task N+X: Export (依赖所有生成/验证任务)
```

### 5.2 Auto Multi-Page Decision

在 Interview/Sitemap 前引入自动决策器，决定进入单页或多页流程。

**输出格式（结构化 JSON）**:
```json
{
  "decision": "multi_page",
  "confidence": 0.82,
  "reasons": ["包含服务/案例/联系等独立模块"],
  "suggested_pages": [
    {"title": "首页", "slug": "index", "purpose": "概览与CTA", "required": true},
    {"title": "服务", "slug": "services", "purpose": "服务与价格", "required": false}
  ],
  "risk": null
}
```

**路由规则**:
- `confidence >= 0.75` → 自动多页
- `0.45 ~ 0.75` → 先生成 sitemap 并允许用户确认/调整
- `< 0.45` → 单页

**可回退**:
用户可通过一句话回到单页（例如“合并为单页”），触发单页生成。

### 5.3 新增 SitemapAgent

**职责**:
- 生成页面清单（title、slug、purpose、sections）
- 生成 nav（导航结构与链接）
- 生成 global_style（色板、字体、按钮、间距）
- 输出需通过 Pydantic schema 验证，确保字段与约束一致

**输出 Schema 约束**:
- `pages` 数量范围 3~8（超出需合并或提示）
- 每页必须包含 `title`, `slug`, `purpose`, `sections[]`, `required`
- `nav` 为对象数组（而非字符串数组）

**输出 JSON 示例**:

```json
{
  "pages": [
    {"title": "首页", "slug": "index", "purpose": "品牌介绍", "sections": ["hero", "cta"], "required": true},
    {"title": "服务", "slug": "services", "purpose": "产品与价格", "sections": ["pricing"], "required": false}
  ],
  "nav": [
    {"slug": "index", "label": "首页", "order": 0},
    {"slug": "services", "label": "服务", "order": 1}
  ],
  "global_style": {
    "primary_color": "#1E88E5",
    "font_family": "Noto Sans"
  }
}
```

### 5.4 GenerationAgent 扩展

- 新增输入: `page_spec`, `global_style`, `nav`
- 生成时嵌入统一导航与共享样式
- 输出保存至 PageVersion

### 5.5 RefinementAgent 路由

- 用户消息若包含页面名/slug，优先定位目标页
- 若不明确，返回 disambiguation 问题
- 定位规则:
  1) 明确提到 slug → 直接定位
  2) 提到中文标题 → sitemap title 模糊匹配
  3) 仍不明确 → 返回可选列表供用户选择

---

## 6. 执行与并发策略

### 6.1 并发执行

- 依赖 Sitemap 的各页面 Generation 任务可并行执行
- `max_concurrent` 默认 5，可配置
- 单页失败不阻塞其他页

### 6.2 失败处理

- 任务失败时触发 `TaskFailedEvent`
- 支持 `retry / skip / modify / abort`
- Export 仅在所有必需页面成功后执行
- Sitemap pages 支持 `required=true/false`（默认仅 index 为 required）
- Export 输出 `export_manifest.json` 标记成功/失败页面

### 6.3 导出与共享资源

导出目录结构:
```
index.html
pages/{slug}.html
assets/site.css
assets/site.js (可选)
export_manifest.json
```

**策略**:
- `global_style + nav` 生成 `assets/site.css`
- 所有页面引用统一 `site.css`，减少重复 inline CSS
- `site.js` 用于导航高亮/滚动行为（如需）

### 6.4 轻量 Validator (MVP)

v0.4 先实现确定性规则，输出 `errors[]` 与 `warnings[]`:
- 必须包含 `<meta name="viewport" ...>`
- 必须包含 `<title>`
- 关键图片必须有 `alt`
- 禁止超大 base64 inline（限制页面体积）
- 内部链接需指向 `pages/{slug}.html`

---

## 7. API 设计

### 7.1 新增/扩展接口

**Pages**
- `POST /api/pages` 创建页面
- `GET /api/sessions/{id}/pages` 获取页面列表
- `GET /api/pages/{page_id}` 页面详情
- `GET /api/pages/{page_id}/versions`
- `GET /api/pages/{page_id}/preview`
- `POST /api/pages/{page_id}/rollback`

**Plan**
- `POST /api/plan` 支持 `multi_page=true` 与 `context.pages`
- 默认 plan 创建即执行；后续可扩展 `POST /api/plan/{plan_id}/run`

**Plan 执行语义**
- 默认 `POST /api/plan` 即开始执行
- 可选 `run_id`/`execution_id` 用于区分重跑与重入

### 7.2 请求参数示例

```json
{
  "session_id": "...",
  "message": "生成一个官网，包含首页/服务/关于/联系",
  "context": {
    "multi_page": true
  }
}
```

---

## 8. 前端与 CLI 交互

### 8.1 Web UI

- Session 详情页新增 **页面列表**
- 页面级预览与版本历史
- 多页面生成时展示任务并发进度

### 8.2 CLI

- 新增 `--multi` 或 `multipage` 子命令
- 输出导出目录结构与可预览路径

> 注意: CLI 目前仅有 `dist/`，新增功能应优先引入 TS 源码与构建流程。

---

## 9. 事件与观测

### 9.1 新增事件

- `page_created`
- `page_version_created`
- `page_preview_ready`
- `multipage_decision_made`
- `sitemap_proposed`

### 9.2 前后端同步

- 更新 `packages/web/src/types/events.ts` 以匹配后端事件模型

### 9.3 事件字段要求

所有 page 相关事件至少携带：
- `session_id`
- `page_id`
- `slug`
- （如存在）`plan_id`, `task_id`

## 10. 实施拆分

**M1: 数据层 + API**
- Page/PageVersion 数据模型与迁移
- Pages CRUD + preview/versions/rollback

**M2: Sitemap + 并行生成**
- AutoMultiPageDecider
- SitemapAgent 与并行 Generation → PageVersion

**M3: Export + Validator + 前端**
- 多页面导出与 manifest
- 轻量 Validator
- 前端页面列表/导航

---

## 11. 文件变更清单

**Backend**
- `packages/backend/app/db/models.py` (新增 Page/PageVersion)
- `packages/backend/app/db/migrations/*` (新增迁移)
- `packages/backend/app/services/page.py`
- `packages/backend/app/services/page_version.py`
- `packages/backend/app/agents/sitemap.py` (新增)
- `packages/backend/app/executor/task_executor.py` (新增 SitemapTaskExecutor)
- `packages/backend/app/api/pages.py` (新增)
- `packages/backend/app/api/plan.py` (扩展 multi_page 参数)
- `packages/backend/app/services/export.py` (扩展多页面导出)

**Web**
- `packages/web/src/components/*` (页面列表与预览)
- `packages/web/src/types/events.ts` (事件同步)

**CLI**
- `packages/cli/src/*` (新增多页面命令，若引入 TS 源码)

---

## 12. 验收标准

1. 支持多页面需求输入并生成多个 HTML 页面。
2. 每个页面可独立预览、修订、回滚版本。
3. 导出目录包含 `index.html` 与 `pages/{slug}.html`。
4. 页面导航互相可达，且共享一致风格。
5. Planner 任务并行执行，失败页面可重试而不阻塞其他页面。
6. 前端页面列表与事件展示正常。
7. 旧 session（仅有 Version）仍可预览并自动映射为默认 index Page。
8. 事件可按 page 聚合展示，同一 plan 并发生成时可区分每页。
9. 自动多页决策可解释（含 reasons/confidence）且支持一条指令回退单页。
