# Instant Coffee - 技术规格说明书 (Spec v0.4)

**项目名称**: Instant Coffee (速溶咖啡)
**版本**: v0.4 - 多页面生成 + Product Doc + 工作台
**日期**: 2026-02-01
**文档类型**: Technical Specification Document (TSD)

---

## 文档变更历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v0.4 | 2026-02-01 | 多页面生成 + Product Doc 驱动 + Preview 工作台重构 | Planning |

---

## 设计决策记录

### 核心决策

| 问题 | 决策 | 说明 |
|------|------|------|
| 多页面如何触发 | Product Doc 确认后触发 AutoMultiPageDecider + 显式 override | 默认自动决策，CLI/Web 可显式强制单页或多页 |
| 生成模式 | 标准确认 / Generate Now | 标准模式：Product Doc 确认后才生成 Plan 与 Code；Generate Now：生成 Product Doc 后自动确认并直接生成 |
| 版本管理 | 仅页面级版本（PageVersion） | 一次 message 互动只为被 touch 的页面生成一个新版本 |
| 导出结构 | `index.html` + `pages/{slug}.html` + `assets/site.css` | index 仅导出为根目录 `index.html`；其余页面在 `pages/`；共享样式 |
| 生成策略 | 先 Product Doc，再 Sitemap/IA，再并行生成 | Product Doc 为 source of truth，通过后才进入页面生成 |
| 页面一致性 | 共享设计系统 + 导航模板 | 通过 `global_style` 与 `nav` 统一风格 |
| 失败处理 | 单页失败不阻塞其它页 | Planner/Executor 允许局部失败并提供重试/跳过 |
| 计划执行 | Plan 创建即执行（默认） | Product Doc 确认后创建 Plan 并执行；Generate Now 自动确认后立即创建 |
| Product Doc 定位 | Source of Truth，生成前必须先产出并确认 | 所有对话默认携带 Product Doc 上下文 |
| Product Doc 编辑 | 仅通过 Chat 修改，不支持直接文字编辑 | 保持单一入口，避免并发编辑冲突 |
| Preview Panel 结构 | 三 Tab：Preview / Code / Product Doc | Preview 支持多页面切换，Code 只读，Product Doc 只读 |
| VersionPanel | 独立右侧面板，仅显示当前页面版本 | 仅对页面进行版本管理；Code/Product Doc 不展示版本历史 |

### 详细问答

**Q: Product Doc 与 Sitemap 是什么关系？**
> A: Product Doc 是更上层的产品定义文档（目标、受众、功能需求、设计方向）；Sitemap 是 Product Doc 的子产出，描述具体页面结构。Product Doc 确认后，Sitemap 从中自动派生。

**Q: Product Doc 能直接编辑吗？**
> A: 不能。Product Doc 只在 Product Doc Tab 中只读展示。所有修改必须通过 Chat Panel 发消息，由 ProductDocAgent 处理后更新。这确保了变更入口统一。

**Q: Code Tab 的文件可以编辑吗？**
> A: 不能。Code Tab 展示导出后的项目结构（HTML/CSS/JS），用户只能通过 Chat 描述修改意图，由 Agent 执行代码变更。

**Q: 新对话是否自动关联 Product Doc？**
> A: 是。每次对话（新消息或新 session）都会自动加载当前 session 的 Product Doc 作为上下文。如果还没有 Product Doc，首次对话会触发 Product Doc 的生成流程。

**Q: 多页面预览如何切换？**
> A: Preview Tab 顶部增加页面选择器（Tab Bar 或 Select），列出所有 Page slug/title。选中后 PhoneFrame 中加载对应页面的 HTML。

**Q: VersionPanel 如何工作？**
> A: VersionPanel 是独立的右侧可折叠面板（保持 v0.3 三栏布局）。本版本仅支持页面级版本：
> - **Preview Tab**: 展示当前选中页面的 PageVersion 历史
> - **Code Tab / Product Doc Tab**: 不展示版本历史
> 回滚操作仅作用于当前页面。

---

## 目录

1. [版本概述](#1-版本概述)
2. [架构设计](#2-架构设计)
3. [数据模型](#3-数据模型)
4. [Product Doc 系统](#4-product-doc-系统)
5. [Agent 设计](#5-agent-设计)
6. [执行与并发策略](#6-执行与并发策略)
7. [API 设计](#7-api-设计)
8. [前端设计](#8-前端设计)
9. [事件与观测](#9-事件与观测)
10. [实施拆分](#10-实施拆分)
11. [文件变更清单](#11-文件变更清单)
12. [验收标准](#12-验收标准)

---

## 1. 版本概述

### 1.1 版本定位

**Spec v0.4** 在 v0.3 的单页面生成基础上，引入三大能力：

1. **Product Doc 驱动生成** — Product Doc 作为 source of truth，生成页面前必须先产出并确认
2. **多页面生成** — 支持一次生成多页，并行执行，页面级版本管理
3. **Preview 工作台** — Preview Panel 从单一预览升级为三 Tab 工作台（Preview / Code / Product Doc）

### 1.2 与 v0.3 的关系

| v0.3 (现有) | v0.4 (本版本) |
|-------------|--------------|
| 直接 Interview → Generation | Interview → Product Doc → Generation |
| 单页 Version | Page + PageVersion |
| 单页预览 | 多页预览 + Code + Product Doc 三 Tab |
| 无产品文档概念 | Product Doc 作为 source of truth |
| Preview Panel 仅展示 HTML | Preview 工作台（三 Tab） |

### 1.3 设计原则

1. **Product Doc First**: 先定义再生成，Product Doc 是所有页面的依据。
2. **Chat 是唯一入口**: 所有修改（Product Doc、页面、代码）都通过 Chat 驱动，其他地方只读。
3. **单页兼容**: 不破坏现有单页流程与 API。
4. **页面自治**: 每页有独立版本历史与修订能力。
5. **一致风格**: 多页面共享设计系统与导航结构。
6. **可观测**: 任务级、页面级事件可追踪。


---

## 2. 架构设计

### 2.1 整体流程

```
用户输入
    ↓
InterviewAgent (收集需求，可选)
    ↓
ProductDocAgent (生成/更新 Product Doc)
    ↓
用户确认 Product Doc (通过 Chat: "looks good" / 提出修改)
  └─ Generate Now 模式：跳过确认，Product Doc 生成后自动标记 confirmed
    ↓
AutoMultiPageDecider (自动决策单页/多页)
    ↓
SitemapAgent (从 Product Doc 派生页面清单 + nav + global_style)
    ↓
Planner 生成任务图 (每页一个 Generation 任务)
    ↓
ParallelExecutor 并行执行
    ↓
PageVersion 保存 → Preview Tab 可预览每页
    ↓
Code Tab 可查看项目结构
    ↓
ExportService 导出
```

### 2.2 后续对话流程（Refinement）

```
用户在 Chat 中发消息
    ↓
Orchestrator 判断意图:
  ├─ 修改 Product Doc → ProductDocAgent 更新 → 触发受影响页面重新生成
  ├─ 修改某个页面 → RefinementAgent (定位目标页)
  ├─ 全局修改 → 批量 Refinement
  └─ 提问/反馈 → 直接回复
    ↓
所有 Agent 执行时自动注入当前 Product Doc 作为上下文
```

### 2.3 分层结构

```
API Layer
  /api/chat                    (触发所有流程)
  /api/sessions/{id}/pages     (页面列表)
  /api/pages/{id}/*            (页面 CRUD)
  /api/sessions/{id}/product-doc  (Product Doc 读取)
  /api/plan                    (多页面任务)

Agent Layer
  InterviewAgent               (需求收集)
  ProductDocAgent              (新增：生成/更新 Product Doc)
  SitemapAgent                 (新增：派生页面结构)
  GenerationAgent              (页面生成)
  RefinementAgent              (页面修改)

Service Layer
  ProductDocService            (新增)
  PageService                  (新增)
  PageVersionService           (新增)
  ExportService                (扩展)
```

---

## 3. 数据模型

### 3.1 新增：ProductDoc

```
ProductDoc
├── id            (UUID, PK)
├── session_id    (FK → Session.id, Unique)
├── content       (TEXT, Markdown 格式)
├── structured    (JSON, 结构化数据)
├── status        (enum: draft / confirmed / outdated)
├── created_at    (datetime)
└── updated_at    (datetime)
```

**`structured` JSON Schema:**

```json
{
  "project_name": "string",
  "description": "string",
  "target_audience": "string",
  "goals": ["string"],
  "features": [
    {
      "name": "string",
      "description": "string",
      "priority": "must|should|nice"
    }
  ],
  "design_direction": {
    "style": "string",
    "color_preference": "string",
    "tone": "string",
    "reference_sites": ["string"]
  },
  "pages": [
    {
      "title": "string",
      "slug": "string",
      "purpose": "string",
      "sections": ["string"],
      "required": true
    }
  ],
  "constraints": ["string"]
}
```

**约束:**
- 每个 Session 最多一个 ProductDoc（`Unique(session_id)`）。
- `status`:
  - `draft` — 初次生成或正在修改中
  - `confirmed` — 用户确认，可进入页面生成
  - `outdated` — 页面已生成后 Product Doc 被修改，需要决定是否重新生成受影响页面
 
### 3.2 新增：Page

```
Page
├── id                 (UUID, PK)
├── session_id         (FK → Session.id)
├── title              (string)
├── slug               (string, [a-z0-9-], max 40)
├── description        (string)
├── order_index        (int)
├── current_version_id (FK → PageVersion.id, nullable)
├── created_at         (datetime)
└── updated_at         (datetime)
```

**约束:** `Unique(session_id, slug)`

### 3.3 新增：PageVersion

```
PageVersion
├── id          (int, PK, auto)
├── page_id     (FK → Page.id)
├── version     (int)
├── html        (TEXT)
├── description (string)
└── created_at  (datetime)
```

**约束:** `Unique(page_id, version)`

**版本生成规则:**
- 一次 message 互动后，只有被 touch 的页面会产生新版本
- 对于每个被 touch 的页面，一次互动最多生成一个新 PageVersion

### 3.4 兼容策略

**旧数据迁移（可执行脚本）:**

对每个已有 Session：
1. 创建 ProductDoc（status=confirmed, content 从最近一次 Interview 上下文生成或留空）。
2. 创建默认 Page：`title="首页"`, `slug="index"`, `order_index=0`。
3. 取该 Session 的最新 `Version` 作为 PageVersion v1。
4. `Page.current_version_id = newly_created_page_version.id`。

**旧接口兼容:**
- `GET /api/sessions/{id}/preview`：返回默认 Page（index）的当前版本。
- `GET /api/sessions/{id}/versions`：仅代表默认 Page 的历史；标记为 deprecated。
- 现有 `Version` 表保持不变，多页面启用后 PageVersion 为新主线。

---

## 4. Product Doc 系统

### 4.1 核心概念

Product Doc 是整个项目的 **source of truth**，定义了：
- 项目目标与受众
- 功能需求与优先级
- 设计方向（风格、色彩、调性）
- 页面结构（标题、用途、分区）
- 约束条件

所有 Agent 在执行时都会注入当前 Product Doc 的 `structured` 字段作为上下文。

### 4.2 生成流程

**模式 A：标准确认（默认）**
```
首次对话
    ↓
Orchestrator 检测: 该 session 无 ProductDoc
    ↓
(可选) InterviewAgent 收集需求
    ↓
ProductDocAgent.generate(interview_context + user_message)
    ↓
输出: ProductDoc (status=draft)
    ↓
前端展示 Product Doc Tab (只读) + Chat 中询问确认
    ↓
用户回复:
  ├─ 确认 ("可以" / "开始生成" / "looks good")
  │    → status=confirmed
  │    → 触发 AutoMultiPageDecider → Sitemap → Plan → Code
  └─ 修改 ("把颜色改为蓝色" / "加一个博客页面")
       → ProductDocAgent.update() → 重新展示
```

**模式 B：Generate Now**
```
首次对话 + 客户端传入 generate_now=true（或显式指令“generate now”）
    ↓
ProductDocAgent.generate(...)
    ↓
输出: ProductDoc (自动标记 status=confirmed)
    ↓
直接触发 AutoMultiPageDecider → Sitemap → Plan → Code
    ↓
前端仍展示 Product Doc Tab（只读），但不阻塞生成流程
```

### 4.3 更新流程

```
用户通过 Chat 提出修改
    ↓
Orchestrator 识别意图: 修改 Product Doc
    ↓
ProductDocAgent.update(current_doc, user_message)
    ↓
更新 ProductDoc（status 视情况）
    ↓
若页面已生成 → status=outdated，Chat 中提示:
  "Product Doc 已更新。是否重新生成受影响的页面？"
    ↓
用户确认 → 触发受影响页面的重新生成
```

### 4.4 与对话的关系

**每条消息都自动注入 Product Doc：**

- Orchestrator 在调用任何 Agent 前，从 DB 加载当前 session 的 ProductDoc。
- 将 `ProductDoc.structured` 序列化后注入到 Agent 的 system prompt 或 context 中。
- Agent 无需显式请求 Product Doc，Orchestrator 统一注入。

**意图识别优先级：**

1. 用户消息包含 Product Doc 相关关键词（"需求"、"目标"、"加一个页面"、"改功能"）→ ProductDocAgent
2. 用户消息包含页面名/slug → RefinementAgent（定位目标页）
3. 用户消息包含样式/布局修改 → RefinementAgent
4. 其他 → 直接回复或引导

---

## 5. Agent 设计

### 5.1 Planner 任务结构

```
Task 0: Interview (可选)
Task 1: ProductDoc Generation (依赖 Task 0)
Task 2: ProductDoc Confirmation (等待用户确认；Generate Now 时自动确认)
Task 3: AutoMultiPageDecider (依赖 Task 2)
Task 4: Sitemap / IA (依赖 Task 3, 从 ProductDoc 派生)
Task 5..N: Generation (每页一个，依赖 Task 4，可并行)
Task N+1..: Validator (每页一个，可并行)
Task N+X: Export (依赖所有页面任务结束，成功/失败均可；失败在 manifest 标记)
```

### 5.2 ProductDocAgent (新增)

**职责:**
- 根据用户需求和 Interview 上下文生成结构化 Product Doc
- 根据用户反馈更新 Product Doc
- 输出同时包含 Markdown (`content`) 和结构化 JSON (`structured`)

**generate() 输入:**
- `user_message`: 用户原始需求
- `interview_context`: Interview 收集的结构化信息（可选）
- `history`: 对话历史

**generate() 输出:**
```json
{
  "content": "# 项目名称\n\n## 目标\n...",
  "structured": {
    "project_name": "...",
    "description": "...",
    "target_audience": "...",
    "goals": [],
    "features": [],
    "design_direction": {},
    "pages": [],
    "constraints": []
  },
  "message": "这是为您生成的产品文档，请查看 Product Doc 标签页。如果需要调整，请告诉我；确认后我将开始生成页面。"
}
```

**update() 输入:**
- `current_doc`: 当前 ProductDoc
- `user_message`: 用户修改意图
- `history`: 对话历史

**update() 输出:**
```json
{
  "content": "更新后的 Markdown",
  "structured": { "更新后的结构化数据" },
  "change_summary": "增加了博客页面，修改了主色调为蓝色",
  "affected_pages": ["index", "blog"],
  "message": "已更新 Product Doc。受影响的页面：首页、博客。是否重新生成这些页面？"
}
```

### 5.3 Auto Multi-Page Decision

在 ProductDoc 确认后（或 Generate Now 自动确认后）引入自动决策，决定单页或多页流程。

**输出格式:**
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

**路由规则:**
- `confidence >= 0.75` → 自动多页
- `0.45 ~ 0.75` → 先生成 sitemap 并允许用户确认/调整
- `< 0.45` → 单页

**可回退:** 用户可通过一句话回到单页（"合并为单页"）。

### 5.4 SitemapAgent (新增)

**职责:**
- 从 Product Doc 的 `structured.pages` 派生详细 Sitemap
- 生成 nav（导航结构与链接）
- 生成 global_style（色板、字体、按钮、间距）
- 输出需通过 Pydantic schema 验证

**输出 Schema 约束:**
- 若用户明确要求多页：`pages` 数量范围 2~8
- 若用户未明确要求多页（交由 AutoMultiPageDecider 判定）：`pages` 数量范围 1~8（允许单页/双页/多页）
- 每页包含 `title`, `slug`, `purpose`, `sections[]`, `required`
- `nav` 为对象数组

**输出 JSON 示例:**
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

### 5.5 GenerationAgent 扩展

- 新增输入: `page_spec`, `global_style`, `nav`, `product_doc`
- 生成时嵌入统一导航与共享样式
- 输出保存至 PageVersion

### 5.6 RefinementAgent 路由

- 用户消息若包含页面名/slug，优先定位目标页
- 若不明确，返回 disambiguation 问题
- 定位规则:
  1. 明确提到 slug → 直接定位
  2. 提到中文标题 → sitemap title 模糊匹配
  3. 仍不明确 → 返回可选列表供用户选择
- Refinement 时自动注入当前 Product Doc 上下文

### 5.7 Orchestrator 意图路由更新

```python
def route(user_message, session_state, generate_now=False):
    # 1. 无 ProductDoc → 走 ProductDoc 生成流程（Generate Now 时自动确认）
    if not session.product_doc:
        return "product_doc_generation_generate_now" if generate_now else "product_doc_generation"

    # 2. ProductDoc 为 draft → 检查是否确认或修改
    if session.product_doc.status == "draft":
        if generate_now or is_confirmation(user_message):
            return "product_doc_confirm"
        else:
            return "product_doc_update"

    # 3. 意图是修改 Product Doc
    if intent_is_product_doc_change(user_message):
        return "product_doc_update"

    # 4. 有 HTML + 指定页面修改
    if has_pages and intent_is_page_refinement(user_message):
        return "refinement"

    # 5. 无页面 → 从 ProductDoc 开始生成
    if not has_pages:
        return "generation_pipeline"

    # 6. 其他
    return "direct_reply"
```

---

## 6. 执行与并发策略

### 6.1 并发执行

- Sitemap 之后各页面 Generation 任务可并行执行
- `max_concurrent` 默认 5，可配置
- 单页失败不阻塞其他页

### 6.2 失败处理

- 任务失败时触发 `TaskFailedEvent`
- 支持 `retry / skip / modify / abort`
- Export 在所有页面任务结束后执行（成功/失败均可），失败页面仅在 manifest 标记，不阻塞导出
- Sitemap pages 支持 `required=true/false`（默认仅 index 为 required）
- Export 输出 `export_manifest.json` 标记成功/失败页面

### 6.3 导出与共享资源

导出目录结构:
```
index.html
pages/{slug}.html
assets/site.css
assets/site.js (可选)
product-doc.md
export_manifest.json
```

**策略:**
- `global_style + nav` 生成 `assets/site.css`
- 所有页面引用统一 `site.css`，减少重复 inline CSS
- `index` 页面仅导出为根目录 `index.html`，不在 `pages/` 下重复生成
- `site.js` 用于导航高亮/滚动行为（如需）
- `product-doc.md` 导出 Product Doc 的 Markdown 内容

**Preview 样式策略:**
- `preview_html` 必须为自包含 HTML（内联 `site.css` 的内容），确保无需额外静态资源也能正确预览
- `preview_url` 若存在，返回与 `preview_html` 等价的自包含 HTML（便于 iframe/缓存）

### 6.4 轻量 Validator (MVP)

确定性规则，输出 `errors[]` 与 `warnings[]`:
- 必须包含 `<meta name="viewport" ...>`
- 必须包含 `<title>`
- 关键图片必须有 `alt`
- 禁止超大 base64 inline（限制页面体积）
- 内部链接规则：index 指向 `index.html`，其他页面指向 `pages/{slug}.html`

---

## 7. API 设计

### 7.1 Product Doc 接口

| 端点 | 方法 | 功能 |
|------|------|------|
| `GET /api/sessions/{id}/product-doc` | GET | 获取当前 Product Doc |

> Product Doc 的创建和更新通过 Chat 流程触发，不提供直接的 POST/PUT 端点。

**GET /api/sessions/{id}/product-doc 响应:**
```json
{
  "id": "uuid",
  "session_id": "uuid",
  "content": "# 项目名称\n...",
  "structured": { ... },
  "status": "confirmed",
  "created_at": "...",
  "updated_at": "..."
}
```

### 7.2 Pages 接口

| 端点 | 方法 | 功能 |
|------|------|------|
| `GET /api/sessions/{id}/pages` | GET | 获取页面列表 |
| `GET /api/pages/{page_id}` | GET | 页面详情 |
| `GET /api/pages/{page_id}/versions` | GET | 页面版本历史 |
| `GET /api/pages/{page_id}/preview` | GET | 页面当前 HTML |
| `POST /api/pages/{page_id}/rollback` | POST | 回滚页面版本 |

### 7.3 Code 接口 (项目结构)

| 端点 | 方法 | 功能 |
|------|------|------|
| `GET /api/sessions/{id}/files` | GET | 获取项目文件树 |
| `GET /api/sessions/{id}/files/{path}` | GET | 获取文件内容（只读） |

**GET /api/sessions/{id}/files 响应:**
```json
{
  "tree": [
    {
      "name": "index.html",
      "path": "index.html",
      "type": "file",
      "size": 12480
    },
    {
      "name": "pages",
      "path": "pages",
      "type": "directory",
      "children": [
        {"name": "services.html", "path": "pages/services.html", "type": "file", "size": 8320},
        {"name": "about.html", "path": "pages/about.html", "type": "file", "size": 6720}
      ]
    },
    {
      "name": "assets",
      "path": "assets",
      "type": "directory",
      "children": [
        {"name": "site.css", "path": "assets/site.css", "type": "file", "size": 2048}
      ]
    },
    {
      "name": "product-doc.md",
      "path": "product-doc.md",
      "type": "file",
      "size": 3200
    }
  ]
}
```

**GET /api/sessions/{id}/files/{path} 响应:**
```json
{
  "path": "pages/services.html",
  "content": "<!DOCTYPE html>...",
  "language": "html",
  "size": 8320
}
```

### 7.4 Chat 接口扩展

`POST /api/chat` 请求新增可选字段:

```json
{
  "generate_now": true
}
```

> `generate_now` 默认 false；为 true 时进入 Generate Now 流程（Product Doc 自动确认并立即生成 Plan 与 Code）。

`POST /api/chat` 响应新增字段:

```json
{
  "session_id": "...",
  "message": "...",
  "preview_url": "...",
  "preview_html": "...",
  "product_doc_updated": true,
  "affected_pages": ["index", "services"],
  "action": "product_doc_generated | product_doc_updated | product_doc_confirmed | pages_generated | page_refined"
}
```

**preview_url vs preview_html 规则:**
- 若 `preview_url` 存在，前端优先使用（更适合 iframe/缓存）
- 若仅有 `preview_html`，必须为自包含 HTML（含内联 `site.css`），确保可直接渲染

### 7.5 Plan 接口扩展

`POST /api/plan` 支持 `multi_page=true` 与 `context.pages`。默认 plan 创建即执行；仅在 Product Doc 确认后（或 Generate Now 自动确认后）触发。

---

## 8. 前端设计

### 8.1 整体布局（三栏 + 独立 VersionPanel）

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Header                                                                  │
├──────────────────┬───────────────────────────────────┬───────────────────┤
│  Left Panel (35%)│  Center Panel (flex-1)             │ Right: Version   │
│ ┌──────────────┐ │ ┌───────────────────────────────┐ │ Panel (折叠/展开) │
│ │Chat │ Events │ │ │ [Preview] [Code] [Product Doc]│ │                  │
│ ├──────────────┤ │ ├───────────────────────────────┤ │  内容随当前 Tab  │
│ │              │ │ │                               │ │  动态切换:       │
│ │  Chat Panel  │ │ │   Tab Content Area            │ │                  │
│ │              │ │ │                               │ │  Preview Tab:    │
│ │  - Messages  │ │ │   (Preview / Code / ProdDoc)  │ │   页面版本历史   │
│ │  - Interview │ │ │                               │ │   (仅 Preview)   │
│ │  - Steps     │ │ │                               │ │                  │
│ │              │ │ │                               │ │                  │
│ ├──────────────┤ │ │                               │ │  Code Tab:       │
│ │  ChatInput   │ │ │                               │ │   无版本历史     │
│ └──────────────┘ │ └───────────────────────────────┘ │                  │
│                  │                                   │  ProdDoc Tab:    │
│                  │                                   │   无版本历史     │
└──────────────────┴───────────────────────────────────┴───────────────────┘
```

**关键设计:**
- **保持 v0.3 三栏布局**：Left (Chat) + Center (Workbench) + Right (VersionPanel)
- Center 区域从原来的纯 PreviewPanel 升级为三 Tab 工作台
- VersionPanel 保持独立，仅在 Preview Tab 展示页面版本（其他 Tab 显示空状态）
- VersionPanel 宽度保持原有行为：折叠 48px / 展开 256px

### 8.2 Preview Tab

```
┌─────────────────────────────────────────┐
│  [首页] [服务] [关于] [联系]  ← 页面选择器 │
├─────────────────────────────────────────┤
│                                         │
│         ┌───────────────┐               │
│         │  PhoneFrame   │               │
│         │               │               │
│         │  (当前选中页面) │               │
│         │               │               │
│         └───────────────┘               │
│                                         │
│  [刷新] [导出]                           │
└─────────────────────────────────────────┘
```

**组件: PageSelector**
- 当仅有一个页面时隐藏
- 多页面时显示为水平 Tab Bar（slug 为 key，title 为 label）
- 选中页面高亮
- 切换时加载对应 PageVersion 的 HTML 到 PhoneFrame
- 切换页面时通知 VersionPanel 更新当前页面版本列表

**组件: PreviewPanel (扩展)**
- 接收 `pages: Page[]` 和 `selectedPageId`
- 加载选中页面的 `preview_html`
- 保留 PhoneFrame、刷新、导出功能

### 8.3 Code Tab

```
┌──────────────────┬──────────────────────┐
│  File Tree       │  File Content        │
│                  │                      │
│  📁 pages/       │  (选中文件的内容)      │
│    📄 services   │                      │
│    📄 about      │  语法高亮显示          │
│  📁 assets/      │  (HTML/CSS/JS/MD)    │
│    📄 site.css   │                      │
│  📄 index.html   │  只读，不可编辑        │
│  📄 product-doc  │                      │
└──────────────────┴──────────────────────┘
```

**组件: CodePanel (新增)**

```typescript
interface CodePanelProps {
  sessionId: string
}
```

**子组件: FileTree**
- 从 `GET /api/sessions/{id}/files` 加载文件树
- 支持目录折叠/展开
- 点击文件选中，高亮显示
- 文件图标区分类型（html/css/js/md）

**子组件: FileViewer**
- 从 `GET /api/sessions/{id}/files/{path}` 加载文件内容
- 按 `language` 字段进行语法高亮（使用轻量高亮库如 `highlight.js` 或 `prism`）
- 显示行号
- 只读，无编辑功能
- 空状态: "选择左侧文件查看内容"

### 8.4 Product Doc Tab

```
┌─────────────────────────────────────────┐
│  Product Doc                 draft      │
├─────────────────────────────────────────┤
│                                         │
│  # 项目名称                              │
│                                         │
│  ## 目标                                 │
│  - 目标 1                                │
│  - 目标 2                                │
│                                         │
│  ## 功能需求                              │
│  ...                                    │
│                                         │
│  ## 页面结构                              │
│  ...                                    │
│                                         │
│  (Markdown 渲染，只读)                    │
│                                         │
├─────────────────────────────────────────┤
│  💡 通过左侧聊天修改此文档                  │
└─────────────────────────────────────────┘
```

**组件: ProductDocPanel (新增)**

```typescript
interface ProductDocPanelProps {
  sessionId: string
}
```

**功能:**
- 从 `GET /api/sessions/{id}/product-doc` 加载
- 将 `content` (Markdown) 渲染为 HTML（使用 `react-markdown` 或类似库）
- 顶部显示状态 badge (draft / confirmed / outdated)
- 底部提示条: "通过左侧聊天修改此文档"
- 只读，不可编辑
- 实时更新: 当 Chat 中 ProductDoc 更新时，通过 SSE 事件触发刷新
- 无 Product Doc 时显示空状态: "开始对话后将自动生成产品文档"

### 8.5 WorkbenchPanel (三 Tab 容器)

**组件: WorkbenchPanel (新增)**

```typescript
interface WorkbenchPanelProps {
  sessionId: string
  activeTab: 'preview' | 'code' | 'product-doc'
  onTabChange: (tab: string) => void
  // Preview Tab props
  pages: Page[]
  selectedPageId: string | null
  onSelectPage: (pageId: string) => void
  previewHtml: string | null
  // Product Doc props
  productDoc: ProductDoc | null
}
```

**Tab 定义:**

| Tab ID | 标签 | 组件 | 说明 |
|--------|------|------|------|
| `preview` | Preview | PreviewPanel | 默认选中；多页面时显示 PageSelector |
| `code` | Code | CodePanel | 文件树 + 文件查看器 |
| `product-doc` | Product Doc | ProductDocPanel | Markdown 渲染，只读 |

**行为:**
- 默认激活 Preview Tab
- 当 Product Doc 首次生成时，自动切换到 Product Doc Tab（一次性）
- 当页面生成完成时，自动切换到 Preview Tab
- Tab 切换时保留各 Tab 的内部状态（选中的文件、选中的页面等）
- **Tab 切换时向外通知 `activeTab`**，ProjectPage 据此更新 VersionPanel 的内容

### 8.6 VersionPanel (独立右侧面板，仅页面版本)

```
┌──────────────────────┐
│  Versions        [▶] │  ← 折叠/展开按钮
├──────────────────────┤
│  当前页面: 首页        │
│                      │
│  ● v3  当前  2分钟前   │
│  ○ v2        10分钟前  │  [回滚]
│  ○ v1        1小时前   │  [回滚]
│                      │
│  (Code / ProdDoc Tab)│
│  本版本仅页面有历史     │
└──────────────────────┘
```

**组件: VersionPanel (扩展)**

```typescript
interface VersionPanelProps {
  isCollapsed: boolean
  onToggleCollapse: () => void
  pageVersions: PageVersion[]
  currentPageVersionId: string | null
  onRevertPageVersion: (versionId: string) => void
  selectedPageTitle: string | null
  activeTab: 'preview' | 'code' | 'product-doc'
}
```

**行为:**
- 折叠/展开保持原有逻辑（48px / 256px）
- 仅在 Preview Tab 展示页面版本历史
- 在 Code / Product Doc Tab 显示空状态提示（不显示版本列表）

### 8.7 ChatPanel 扩展

**无结构性变更，行为变更:**
- 消息发送后，Orchestrator 返回的 `action` 字段驱动工作台 Tab 切换:
  - `product_doc_generated` / `product_doc_updated` → 切换到 Product Doc Tab
  - `pages_generated` / `page_refined` → 切换到 Preview Tab
- Chat 中展示 Product Doc 相关的操作提示（如 "Product Doc 已更新，查看 Product Doc 标签页"）

### 8.8 新增 Hooks

**useProductDoc**
```typescript
function useProductDoc(sessionId: string) {
  return {
    productDoc: ProductDoc | null
    isLoading: boolean
    error: string | null
    refresh: () => Promise<void>
  }
}
```

**usePages**
```typescript
function usePages(sessionId: string) {
  return {
    pages: Page[]
    selectedPage: Page | null
    selectPage: (pageId: string) => void
    isLoading: boolean
    refresh: () => Promise<void>
  }
}
```

**useFileTree**
```typescript
function useFileTree(sessionId: string) {
  return {
    tree: FileTreeNode[]
    selectedFile: FileContent | null
    selectFile: (path: string) => Promise<void>
    isLoading: boolean
  }
}
```

### 8.9 新增 Types

```typescript
// Product Doc
interface ProductDoc {
  id: string
  sessionId: string
  content: string          // Markdown
  structured: ProductDocStructured
  status: 'draft' | 'confirmed' | 'outdated'
  createdAt: Date
  updatedAt: Date
}

interface ProductDocStructured {
  projectName: string
  description: string
  targetAudience: string
  goals: string[]
  features: ProductDocFeature[]
  designDirection: DesignDirection
  pages: ProductDocPage[]
  constraints: string[]
}

interface ProductDocFeature {
  name: string
  description: string
  priority: 'must' | 'should' | 'nice'
}

interface DesignDirection {
  style: string
  colorPreference: string
  tone: string
  referenceSites: string[]
}

interface ProductDocPage {
  title: string
  slug: string
  purpose: string
  sections: string[]
  required: boolean
}

// Page
interface Page {
  id: string
  sessionId: string
  title: string
  slug: string
  description: string
  orderIndex: number
  currentVersionId: string | null
  createdAt: Date
  updatedAt: Date
}

// File Tree
interface FileTreeNode {
  name: string
  path: string
  type: 'file' | 'directory'
  size?: number
  children?: FileTreeNode[]
}

interface FileContent {
  path: string
  content: string
  language: string
  size: number
}

// Project Snapshot
// Page Version (for VersionPanel)
interface PageVersion {
  id: number
  pageId: string
  version: number
  description: string | null
  createdAt: Date
}

```

---

## 9. 事件与观测

### 9.1 新增事件

| 事件 | 触发时机 | 关键字段 |
|------|---------|---------|
| `product_doc_generated` | ProductDoc 首次生成 | session_id, doc_id |
| `product_doc_updated` | ProductDoc 被更新 | session_id, doc_id, change_summary |
| `product_doc_confirmed` | 用户确认 ProductDoc | session_id, doc_id |
| `product_doc_outdated` | ProductDoc 被标记为 outdated | session_id, doc_id |
| `page_created` | 页面记录创建 | session_id, page_id, slug |
| `page_version_created` | 页面新版本生成 | session_id, page_id, slug, version |
| `page_preview_ready` | 页面可预览 | session_id, page_id, slug, preview_url |
| `multipage_decision_made` | 自动多页决策完成 | session_id, decision, confidence |
| `sitemap_proposed` | Sitemap 生成完成 | session_id, pages_count |

### 9.2 前端事件处理

SSE 事件中增加对上述事件的处理:
- `product_doc_generated` → 刷新 ProductDoc + 切换到 Product Doc Tab
- `product_doc_updated` → 刷新 ProductDoc
- `product_doc_confirmed` → 刷新 ProductDoc（状态变为 confirmed）
- `product_doc_outdated` → 刷新 ProductDoc（状态变为 outdated）+ 提示可重新生成
- `multipage_decision_made` → 记录决策原因与置信度（Events 面板展示）
- `sitemap_proposed` → 刷新页面列表/导航结构（如有 UI 可展示 IA）
- `page_version_created` → 刷新 Pages 列表 + 刷新 VersionPanel（若在 Preview Tab）
- `page_preview_ready` → 刷新 Preview（如果当前选中该页面）

### 9.3 事件字段要求

所有 page 相关事件至少携带：
- `session_id`
- `page_id`
- `slug`
- （如存在）`plan_id`, `task_id`

所有 product_doc 相关事件至少携带：
- `session_id`
- `doc_id`

---

## 10. 实施拆分

### M1: Product Doc 数据层 + API + Agent

**后端:**
- ProductDoc 数据模型与迁移
- ProductDocService (CRUD)
- ProductDocAgent (generate / update)
- `GET /api/sessions/{id}/product-doc` 端点
- Orchestrator 路由: 检测 ProductDoc 状态并路由到 ProductDocAgent

**前端:**
- ProductDocPanel 组件（Markdown 渲染，只读）
- WorkbenchPanel 骨架（三 Tab，仅 Product Doc Tab 可用）
- VersionPanel 重构为页面模式（Preview Tab）
- useProductDoc hook
- 新增 Types

### M2: Page 数据层 + 多页面生成

**后端:**
- Page / PageVersion 数据模型与迁移
- PageService / PageVersionService
- SitemapAgent
- AutoMultiPageDecider
- GenerationAgent 扩展（page_spec, global_style, nav, product_doc）
- Pages API 端点
- ParallelExecutor 多页面并行

**前端:**
- PageSelector 组件
- PreviewPanel 扩展（多页面）
- VersionPanel 完善（页面模式）
- usePages hook
- Preview Tab 完善

### M3: Code Tab + 文件接口

**后端:**
- `GET /api/sessions/{id}/files` 文件树端点
- `GET /api/sessions/{id}/files/{path}` 文件内容端点

**前端:**
- FileTree 组件
- FileViewer 组件（语法高亮）
- CodePanel 组件
- useFileTree hook

### M4: Export + Validator + 集成

**后端:**
- 多页面导出（含 product-doc.md）
- 轻量 Validator
- export_manifest.json

**前端:**
- 导出功能对接
- 事件流完善
- Tab 自动切换逻辑

---

## 11. 文件变更清单

### Backend

| 文件 | 变更 |
|------|------|
| `app/db/models.py` | 新增 ProductDoc, Page, PageVersion |
| `app/db/migrations/*` | 新增迁移脚本 |
| `app/agents/product_doc.py` | **新增** ProductDocAgent |
| `app/agents/sitemap.py` | **新增** SitemapAgent |
| `app/agents/orchestrator.py` | 扩展路由逻辑（ProductDoc 意图识别） |
| `app/agents/generation.py` | 扩展输入（page_spec, global_style, nav, product_doc） |
| `app/agents/refinement.py` | 扩展（Product Doc 上下文注入 + 页面定位） |
| `app/agents/prompts.py` | 新增 Product Doc / Sitemap 相关 prompt |
| `app/services/product_doc.py` | **新增** ProductDocService |
| `app/services/page.py` | **新增** PageService |
| `app/services/page_version.py` | **新增** PageVersionService |
| `app/services/export.py` | 扩展多页面 + Product Doc 导出 |
| `app/api/product_doc.py` | **新增** Product Doc 端点 |
| `app/api/pages.py` | **新增** Pages 端点 |
| `app/api/files.py` | **新增** Files 端点（文件树 + 文件内容） |
| `app/api/chat.py` | 扩展响应字段 |
| `app/api/plan.py` | 扩展 multi_page 参数 |
| `app/executor/task_executor.py` | 新增 ProductDocTaskExecutor, SitemapTaskExecutor |
| `app/events/models.py` | 新增事件类型 |

### Web

| 文件 | 变更 |
|------|------|
| `src/components/custom/WorkbenchPanel.tsx` | **新增** 三 Tab 工作台容器 |
| `src/components/custom/ProductDocPanel.tsx` | **新增** Product Doc 只读展示 |
| `src/components/custom/CodePanel.tsx` | **新增** 文件树 + 文件查看器 |
| `src/components/custom/FileTree.tsx` | **新增** 文件树组件 |
| `src/components/custom/FileViewer.tsx` | **新增** 文件内容查看器（语法高亮） |
| `src/components/custom/PageSelector.tsx` | **新增** 多页面选择器 |
| `src/components/custom/PreviewPanel.tsx` | 扩展（接收 pages, selectedPageId） |
| `src/components/custom/VersionPanel.tsx` | 重构为仅页面模式（Preview Tab） |
| `src/pages/ProjectPage.tsx` | 布局保持三栏，Center 区域替换为 WorkbenchPanel |
| `src/hooks/useProductDoc.ts` | **新增** |
| `src/hooks/usePages.ts` | **新增** |
| `src/hooks/useFileTree.ts` | **新增** |
| `src/hooks/useChat.ts` | 扩展（处理 product_doc 相关事件和 action） |
| `src/api/client.ts` | 新增 productDoc / pages / files 端点 |
| `src/types/index.ts` | 新增 ProductDoc, Page, FileTree 类型 |
| `src/types/events.ts` | 新增事件类型 |

### CLI

| 文件 | 变更 |
|------|------|
| `packages/cli/src/*` | 新增多页面命令（若引入 TS 源码） |

---

## 12. 验收标准

### Product Doc

1. 首次对话自动触发 Product Doc 生成，展示在 Product Doc Tab。
2. Product Doc 只能通过 Chat 修改，Tab 中只读展示。
3. Product Doc 确认后才能进入页面生成流程。
4. Product Doc 更新后，已生成页面标记为 outdated，用户可选择重新生成。
5. 本版本不提供 Product Doc 版本历史/回滚。

### 多页面生成

6. 支持多页面需求输入并生成多个 HTML 页面。
7. 每个页面可独立预览、修订、回滚版本。
8. 导出目录包含已成功生成的页面（`index.html` 与 `pages/{slug}.html`），失败页面记录在 `export_manifest.json`。
9. 页面导航互相可达，且共享一致风格。
10. Planner 任务并行执行，失败页面可重试而不阻塞其他页面。

### Preview Tab

11. 多页面时，Preview Tab 顶部显示页面选择器。
12. 切换页面后 PhoneFrame 加载对应页面 HTML。

### Code Tab

13. Code Tab 展示完整项目文件树（HTML/CSS/JS/MD）。
14. 点击文件显示内容，有语法高亮和行号。
15. 文件不可编辑，只能通过 Chat 修改。

### Product Doc Tab

16. Product Doc Tab 以 Markdown 渲染展示文档内容。
17. 显示状态 badge。
18. 底部提示"通过聊天修改此文档"。

### VersionPanel (独立面板)

19. VersionPanel 保持独立右侧面板，不嵌入 Tab 内。
20. Preview Tab 激活时，VersionPanel 展示当前选中页面的 PageVersion 历史，支持回滚单页。
21. Code Tab / Product Doc Tab 显示空状态提示（无版本历史）。

### 对话与上下文

22. 每条消息自动注入当前 Product Doc 上下文。
23. Orchestrator 正确识别意图（修改 Product Doc / 修改页面 / 其他）。
24. 旧 session 兼容：无 ProductDoc 的旧 session 仍可预览。

### 事件

25. Product Doc 相关事件正确触发并前端响应。
26. 页面相关事件可按 page 聚合，并发生成时可区分每页。
27. 页面版本事件正确触发并刷新 VersionPanel。
28. 自动多页决策可解释（含 reasons/confidence）且支持一条指令回退单页。
