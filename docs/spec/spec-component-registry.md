# Instant Coffee - 技术规格说明书 (Spec v0.7)

**项目名称**: Instant Coffee (速溶咖啡)  
**版本**: v0.7 - 组件 Registry 与“先组件、后页面”生成  
**日期**: 2026-02-04  
**文档类型**: Technical Specification Document (TSD)

---

## 文档变更历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v0.7 | 2026-02-04 | 引入组件 Registry、组件规划/生成 Agent、页面生成时组件替换 | Planning |

---

## 设计决策访谈记录 (2026-02-04)

本节记录引入“组件优先生成”的关键决策与取舍。

### 核心决策

| 问题 | 决策 | 说明 |
|------|------|------|
| 组件形态 | HTML 片段 + JSON Registry | 保持纯 HTML 输出，避免引入 React 构建链 |
| 组件存放位置 | `output/<session_id>/components/` | 与现有 session 输出一致，便于导出 |
| 组件如何被页面调用 | `<component ...>` 占位标签 + 后处理替换 | 保持 GenerationAgent 的整体输出方式 |
| 组件范围 | Session 级组件 + `page_map` | 保证全站一致性，同时允许页面限定 |
| 失败回退 | 组件生成失败则退回直接页面生成 | 保持流程可用性 |
| Schema 位置 | ProductDocStructured 扩展字段 | 避免新增 DB 表 |

---

## 目录

1. [版本概述](#1-版本概述)  
2. [架构设计](#2-架构设计)  
3. [数据模型与文件结构](#3-数据模型与文件结构)  
4. [组件 Registry 规范](#4-组件-registry-规范)  
5. [Agent 与 Planner 设计](#5-agent-与-planner-设计)  
6. [组件装配与生成流程](#6-组件装配与生成流程)  
7. [API / 事件 / 前端影响](#7-api--事件--前端影响)  
8. [测试与验收标准](#8-测试与验收标准)  
9. [实施拆分与文件变更清单](#9-实施拆分与文件变更清单)

---

## 1. 版本概述

### 1.1 背景

当前页面生成流程以“整页 HTML 生成”为主，组件仅以 `component_inventory` 文本提示存在，缺乏真实组件复用，导致跨页一致性不足、结构漂移明显。

### 1.2 目标

1. **先组件、后页面**：页面生成前先产出可复用组件片段。  
2. **可见组件目录**：输出目录内可见 `components/`。  
3. **最小破坏**：不引入 React 构建链，不破坏现有 HTML 输出流程。  
4. **一致性提升**：页面结构受组件定义约束，而不是纯提示词约束。  

### 1.3 非目标

- 不引入 React / shadcn 组件运行时。  
- 不重写前端工程结构或 Vite 构建流程。  
- 不强制全局设计系统改造（仅在生成链路引入组件化）。  

---

## 2. 架构设计

### 2.1 流程概览

```
Product Doc
   ↓
Sitemap / IA
   ↓
ComponentPlannerAgent  →  component_registry_plan
   ↓
ComponentBuilderAgent  →  components/*.html + components.json
   ↓
GenerationAgent (输出 <component> 占位标签)
   ↓
ComponentAssembler (替换占位标签 → 最终 HTML)
   ↓
Validator / Export
```

### 2.2 设计原则

1. **组件先行**: 组件是页面结构的“来源”，页面是组件的“组装结果”。  
2. **弱耦合**: GenerationAgent 只需要输出占位标签，不直接拼组件细节。  
3. **可回退**: 组件失败不阻塞页面生成。  

---

## 3. 数据模型与文件结构

### 3.1 ProductDocStructured 扩展字段

新增字段（schema 扩展）：

```json
{
  "component_registry_plan": {
    "components": ["HeroSplit", "FeatureGrid"],
    "page_map": {
      "index": ["HeroSplit", "FeatureGrid", "CTA", "Footer"]
    }
  },
  "component_registry": {
    "path": "components/components.json",
    "version": 1,
    "hash": "sha256:...",
    "generated_at": "2026-02-04T10:30:00Z"
  }
}
```

保持原有字段：
- `component_inventory`：继续作为高层组件清单，可由 Planner 自动同步。  

### 3.2 输出目录结构

```
instant-coffee-output/
  <session_id>/
    index.html
    pages/
      about.html
    components/
      components.json
      hero-split.html
      feature-grid.html
```

### 3.3 Registry 缓存策略

默认策略（最小实现）：
- 每次生成重新构建 `components/`。  

可选优化（后续）：
- 若 `component_registry.hash` 与当前输入 hash 一致，跳过生成。  

---

## 4. 组件 Registry 规范

### 4.1 components.json 格式

```json
{
  "version": 1,
  "session_id": "abc123",
  "generated_at": "2026-02-04T10:30:00Z",
  "components": [
    {
      "id": "hero-split",
      "name": "HeroSplitImage",
      "category": "hero",
      "sections": ["hero"],
      "slots": {
        "headline": "string",
        "subhead": "string",
        "cta_label": "string",
        "cta_href": "string",
        "image_url": "string"
      },
      "props": {
        "image_side": ["left", "right"],
        "theme": ["light", "dark"]
      },
      "usage": {
        "pages": ["index"]
      },
      "file": "components/hero-split.html"
    }
  ],
  "page_map": {
    "index": ["hero-split", "feature-grid", "pricing-table", "cta", "footer-simple"]
  }
}
```

### 4.2 组件片段约束

- **单根元素**（避免拼接混乱）。  
- 不包含 `<html>`, `<head>`, `<body>`。  
- 禁止 `<script>`（保持安全与可控）。  
- 使用 `{{slot}}` 占位符。  

示例：

```html
<section class="hero hero-split" data-component="hero-split">
  <div class="hero-copy">
    <h1>{{headline}}</h1>
    <p>{{subhead}}</p>
    <a class="btn primary" href="{{cta_href}}">{{cta_label}}</a>
  </div>
  <div class="hero-media">
    <img src="{{image_url}}" alt="{{headline}}" />
  </div>
</section>
```

### 4.3 页面调用标签

页面生成时使用占位标签：

```html
<component
  id="hero-split"
  data='{"headline":"Fresh Coffee","subhead":"Daily roast","cta_label":"Shop","cta_href":"/shop","image_url":"...","image_side":"right"}'>
</component>
```

约束：
- `<component>` 标签**不得包含子节点**。  
- `data` 必须是 JSON 字符串。  
- 允许 `data-props` 备用字段（用于 JSON 长度限制）。  

---

## 5. Agent 与 Planner 设计

### 5.1 ComponentPlannerAgent

**输入**：
- ProductDoc（结构化字段）
- Sitemap（pages + sections）
- Design direction（全局风格）

**输出**：
- `component_registry_plan`（组件清单 + page_map）
- 同步更新 `component_inventory`

**职责**：
1. 根据页面 sections 抽取通用组件候选。  
2. 将相同结构合并为统一组件。  
3. 输出每页组件序列。  

### 5.2 ComponentBuilderAgent

**输入**：
- `component_registry_plan`
- Design direction
- 页面类型上下文（landing / ecommerce / dashboard）

**输出**：
- `components/*.html`
- `components.json`
- 写入 `component_registry` 元信息

**职责**：
1. 为每个组件生成稳定 HTML 片段。  
2. 定义 slots/props（保持最小集）。  
3. 写入 Registry（JSON + 文件路径）。  

### 5.3 Task 依赖关系

```
Sitemap
  ↓
ComponentPlan (depends_on: sitemap)
  ↓
ComponentBuild (depends_on: ComponentPlan)
  ↓
Generation (depends_on: ComponentBuild)
  ↓
Validator / Export
```

---

## 6. 组件装配与生成流程

### 6.1 组件装配器 (ComponentAssembler)

执行位置：
实现备注（2026-02-04）：当前装配逻辑在 `GenerationAgent` 写盘前执行，功能等价。

步骤：
1. 解析 HTML，查找 `<component id="...">`  
2. 从 Registry 读取对应 fragment  
3. 替换 `{{slot}}`，并处理 props  
4. 用 fragment 替换占位标签  

### 6.2 错误与回退

| 场景 | 处理方式 |
|------|----------|
| Registry 缺失 | 保留原 HTML，不替换 |
| 组件缺失 | 保留 `<component>` 标签或移除（配置） |
| slot 缺失 | 用空字符串替代 |
| JSON 解析失败 | 跳过该组件替换 |

### 6.3 HTML 生成提示词调整

GenerationAgent 提示词中新增约束：
- 需输出 `<component>` 标签  
- 不得直接写组件 HTML  
- 数据通过 `data` 字段传递  

---

## 7. API / 事件 / 前端影响

### 7.1 API

无需新增 API。  
组件产物随导出一并落盘，可通过下载导出包获取。  

### 7.2 事件

复用现有事件：
- `agent_start / agent_end / task_*`  
新增 Agent 类型值：`component_plan`、`component_build`  

如需前端展示，可在 `packages/web/src/types/events.ts` 扩展支持。  

---

## 8. 测试与验收标准

### 8.1 测试范围

- Registry JSON 读写与校验  
- `<component>` 替换逻辑  
- 组件缺失/JSON 解析失败的回退  
- 多页面场景下组件替换  

### 8.2 验收标准

1. 生成流程结束后目录包含 `components/` 与 `components.json`。  
2. 页面 HTML 中不再存在 `<component>` 标签（替换完成）。  
3. 组件样式在不同页面保持一致（结构一致 + class 统一）。  
4. 组件构建失败时仍能生成页面（回退生效）。  

---

## 9. 实施拆分与文件变更清单

### 9.1 新增文件

- `packages/backend/app/agents/component_planner.py`  
- `packages/backend/app/agents/component_builder.py`  
- `packages/backend/app/services/component_registry.py`  
- `packages/backend/app/utils/component_assembler.py`  
- `docs/spec/spec-component-registry.md` (本文档)  

### 9.2 修改文件

- `packages/backend/app/agents/orchestrator.py`  
- `packages/backend/app/executor/task_executor.py`  
- `packages/backend/app/agents/prompts.py`  
- `packages/backend/app/schemas/product_doc.py`  
- `packages/backend/app/services/product_doc.py`  
- `packages/web/src/types/events.ts`（如需要前端展示组件任务）  

---

## 附录 A: 占位标签替换规则示例

输入：
```html
<component id="hero-split" data='{"headline":"Fresh","subhead":"Daily","cta_label":"Shop","cta_href":"/shop","image_url":"..."}'></component>
```

输出：
```html
<section class="hero hero-split" data-component="hero-split">
  <div class="hero-copy">
    <h1>Fresh</h1>
    <p>Daily</p>
    <a class="btn primary" href="/shop">Shop</a>
  </div>
  <div class="hero-media">
    <img src="..." alt="Fresh" />
  </div>
</section>
```

---

## 10. 实施任务清单（顺序）与状态

说明：以下顺序按“可直接开工的代码改动顺序”排列。状态将随实现更新。

| 步骤 | 任务 | 状态 |
|------|------|------|
| 01 | 扩展 ProductDoc 结构字段（component_registry_plan / component_registry） | completed |
| 02 | ProductDocService 兼容新字段 | completed |
| 03 | 新增组件 Registry 服务（读写 JSON + 路径解析） | completed |
| 04 | 新增 ComponentPlannerAgent + prompt | completed |
| 05 | 新增 ComponentBuilderAgent + prompt | completed |
| 06 | Orchestrator 插入组件规划/构建任务（依赖关系） | completed |
| 07 | TaskExecutor 扩展 agent_type（component_plan / component_build） | completed |
| 08 | 新增 ComponentAssembler（替换 `<component>`） | completed |
| 09 | Generation 生成后装配组件 | completed |
| 10 | Generation prompt 强化（输出 `<component>` 标签） | completed |
| 11 | ExportService 支持导出 components（可选） | completed |
| 12 | SSE 事件类型更新（可选） | completed |
