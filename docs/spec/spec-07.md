# Instant Coffee - 技术规格说明书 (Spec v0.7.1)

**项目名称**: Instant Coffee (速溶咖啡)
**版本**: v0.7.1 - LangGraph 编排 + 场景旅程能力 + 组件一致性 + Mobile Shell 自动修复 + React SSG 多文件产物
**日期**: 2026-02-05
**文档类型**: Technical Specification Document (TSD)

---

## 文档变更历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v0.7.1 | 2026-02-05 | 细化构建方案、页面 Schema、组件映射、风格提取、数据模型、节点契约、托管方案、迁移依赖、验收标准 | Planning |
| v0.7 | 2026-02-05 | 引入 LangGraph 编排与精简 Agent；对齐场景旅程能力；组件一致性统一；Mobile Shell 自动修复；9:19.5 仅预览；输出改为 React SSG 多文件静态站 | Planning |
| v0.6 | 2026-02-03 | Skills 编排、Orchestrator 路由、多模型分工、文档分级、风格参考、移动端 guardrails、Data Tab | Planning |

---

## 设计决策记录

### 核心决策

| 问题 | 决策 | 说明 |
|------|------|------|
| 编排框架 | LangGraph | 用 StateGraph 明确控制流与可恢复性，替代散乱的 Orchestrator 分支 |
| Agent 数量 | 精简为 4 个核心节点 | Brief / Component Registry / Generate / Render；Refine 作为条件分支 |
| 输出形态 | React SSG 多文件静态站 | 预渲染首屏 + 客户端交互，手机可用且加载稳定 |
| 构建工具 | Vite + React 18 | 轻量、快速、支持 SSG 预渲染 |
| 样式方案 | Tailwind CSS | 原子化样式，便于组件复用与风格一致性 |
| 9:19.5 约束 | 仅用于预览 | 生成 HTML 不强锁比例，避免真实设备比例错配 |
| Mobile Shell | 自动修复 | 注入 viewport、#app.page 容器、max-width、min-height 等强约束 |
| 组件一致性 | 强制执行 | 所有页面复用统一组件注册表（nav/sidebar/card 等） |
| 风格参考 | 必须 | 图片/风格 token 全链路注入，冲突时优先风格参考 |
| Product Doc | 核心 | 作为所有生成的单一事实来源（source of truth） |
| 审美评分 | 可选，默认关闭 | Landing/Card 场景可启用，低于阈值提供建议但不阻断 |

---

## 目录

1. [版本概述](#1-版本概述)
2. [范围与原则](#2-范围与原则)
3. [架构设计](#3-架构设计)
4. [场景旅程能力对齐](#4-场景旅程能力对齐)
5. [数据模型](#5-数据模型)
6. [LangGraph 编排与节点](#6-langgraph-编排与节点)
7. [页面 Schema 规范](#7-页面-schema-规范)
8. [组件一致性与组件注册表](#8-组件一致性与组件注册表)
9. [风格参考与资产注册](#9-风格参考与资产注册)
10. [Mobile Shell 与移动端约束](#10-mobile-shell-与移动端约束)
11. [数据流与 Data Tab](#11-数据流与-data-tab)
12. [审美评分](#12-审美评分)
13. [构建与托管方案](#13-构建与托管方案)
14. [API 与前端设计](#14-api-与前端设计)
15. [迁移与实施拆分](#15-迁移与实施拆分)
16. [文件变更清单](#16-文件变更清单)
17. [验收标准](#17-验收标准)

---

## 1. 版本概述

### 1.1 版本定位

**Spec v0.7.1** 在 v0.7 基础上细化实施细节：
1) 明确 **构建技术选型**（Vite + React 18 + Tailwind）
2) 定义 **页面 Schema 结构** 与 **组件映射规则**
3) 补充 **LangGraph 节点契约** 与 **迁移依赖关系**
4) 增加 **可量化的验收标准**

### 1.2 与 v0.6/v0.7 的关系

| v0.6 | v0.7 | v0.7.1 |
|------|------|--------|
| Orchestrator + 多 Agent | LangGraph 编排 + 核心节点 | + 节点契约与数据流定义 |
| 单文件 HTML 输出 | React SSG 多文件静态站 | + Vite 构建方案细节 |
| 9:19.5 作为移动端约束 | 9:19.5 仅预览 | 保持 |
| 组件规划/构建分散 | 统一 Component Registry 节点 | + 组件映射规则 |
| 审美评分内置 | 默认关闭 | 可选启用，Landing/Card 场景支持 |
| Flow App 能力为主 | 五大场景旅程能力 | + 数据模型字段定义 |

### 1.3 设计原则

1. **一致性优先**：组件与样式必须跨页面一致
2. **可恢复**：编排必须可追踪、可回放、可中断
3. **移动端真实可用**：生成结果不依赖预览框架即可移动端可用
4. **风格参考强约束**：图片/风格 token 作为最高优先级视觉来源
5. **结构化优先**：所有场景都必须先产出结构化文档与模型
6. **可测试**：所有验收标准必须可量化测试

---

## 2. 范围与原则

### 2.1 包含
- LangGraph 编排与节点拆分
- 场景能力矩阵（电商/行程/说明书/看板/Landing）
- 结构化输入与 Product Doc 统一
- 组件注册表 + 组件一致性约束
- 风格参考（图片/风格 token）
- Mobile Shell 自动修复
- Data Tab/跨页状态协议（localStorage）
- 预览分享（只读链接）与本地托管
- Vite + React 18 构建链路
- 审美评分（可选，Landing/Card 场景）

### 2.2 不包含
- 后端持久化业务数据（仍以 localStorage 为主）
- 完整协作权限系统
- SPA 路由（仍以静态多页为主）
- 源码导出（仅托管产物）
- 云端托管（本地托管优先）

---

## 3. 架构设计

### 3.1 总体流程

```
用户输入 + 参考图 + 资产
  ↓
解析 @Page / 资源
  ↓
┌─────────────────────────────────────┐
│         LangGraph StateGraph        │
├─────────────────────────────────────┤
│  Brief Node                         │
│  ├─ 生成 Product Doc                │
│  ├─ 输出结构化数据模型              │
│  └─ 确定页面清单                    │
│            ↓                        │
│  Style Reference Extractor (Vision API / 非LLM可选)  │
│  └─ 提取风格 tokens                 │
│            ↓                        │
│  Component Registry Node            │
│  └─ 生成统一组件规范                │
│            ↓                        │
│  Generate Node                      │
│  └─ 输出页面 Schema (组件树+props)  │
│            ↓                        │
│  [可选] Aesthetic Scorer Node       │
│  └─ 评估视觉质量，提供优化建议      │
│            ↓                        │
│  [条件] 用户反馈? ──→ Refine Node   │
│            ↓                        │
│  Render Node                        │
│  └─ Vite 构建 React SSG             │
└─────────────────────────────────────┘
  ↓
Mobile Shell Normalizer (后处理)
  ↓
托管 dist/ + Preview + Data Tab
```

### 3.2 关键服务层

| 服务 | 职责 | 技术方案 |
|------|------|---------|
| `style_reference` | 图片风格提取 + token 标准化 | Claude Vision API（默认）/ 规则提取（可选） |
| `component_registry` | 统一组件方案输出 | LLM + 预置组件库 |
| `aesthetic_scorer` | 视觉质量评估 + 优化建议 | Claude Vision API |
| `renderer` | 页面 schema → React SSG 产物 | Vite + React 18 |
| `mobile_shell` | HTML 自动修复 + 规则校验 | 正则 + DOM 解析 |
| `data_store` | localStorage state/records/events | postMessage 桥接 |
| `asset_registry` | Logo/背景/风格图统一管理 | 文件存储 + URL 映射 |

### 3.3 产物形态（React SSG 多文件静态站）

```
dist/
├── index.html                 # 首页（预渲染）
├── pages/
│   ├── cart/index.html       # 购物车页
│   ├── checkout/index.html   # 结算页
│   └── product/index.html    # 商品详情页
├── assets/
│   ├── app.[hash].js         # 主应用脚本
│   ├── app.[hash].css        # 主样式表
│   └── vendor.[hash].js      # 第三方依赖
└── shared/
    ├── data-store.js         # localStorage 状态管理
    └── components.js         # 共享组件运行时
```

### 3.4 构建技术选型

| 选项 | 选择 | 理由 |
|------|------|------|
| 构建工具 | **Vite 5.x** | 快速、轻量、原生 ESM |
| UI 框架 | **React 18** | 生态成熟、SSG 支持好 |
| 样式方案 | **Tailwind CSS 3.x** | 原子化、便于动态生成 |
| SSG 方案 | **vite-plugin-ssr** 或自定义 | 预渲染多页 |
| 构建触发 | 后端 Node 子进程 | `child_process.spawn('npm', ['run', 'build'])` |

**构建流程**：
1. 后端生成页面 Schema JSON
2. 写入预置模板项目的 `src/pages/` 目录
3. 调用 `npm run build` 执行 Vite 构建
4. 输出 `dist/` 到会话目录
5. 后端提供静态文件服务

---

## 4. 场景旅程能力对齐

### 4.1 场景矩阵

| 场景 | 必备页面 | 数据模型 | 关键组件 | 事件/埋点 |
|------|----------|----------|----------|-----------||
| 电商独立站 | Home / Product / Cart / Checkout / Order | Product/Category/Cart/Order/User | 商品卡片、购物车、订单摘要 | add_to_cart/checkout/order_submitted |
| 旅行行程 | Overview / DayPlan / Detail | Trip/Booking/DayPlan/Location | 时间轴、日程卡片、详情卡 | save_plan/share_link |
| 说明书网站 | Index / Section / Page | Manual/Section/Page | 目录、分页、面包屑 | page_view/search |
| 任务看板 | Board / Detail | Board/Column/Task/User/Tag | 列/任务卡/详情面板 | task_created/task_moved |
| Landing | Single Page | Lead/Form | Hero/Features/CTA/Testimonials | lead_submitted/cta_click |

### 4.2 场景检测规则

> 注：`card`/`invitation` 作为 Landing 的轻量子类型，主要用于审美评分与模板选择，不单列场景矩阵。

```python
SCENARIO_KEYWORDS = {
    "ecommerce": ["商品", "购物车", "下单", "商城", "电商", "store", "cart", "checkout"],
    "travel": ["行程", "旅行", "日程", "景点", "trip", "itinerary", "booking"],
    "manual": ["说明书", "文档", "手册", "指南", "manual", "docs", "guide"],
    "kanban": ["看板", "任务", "项目管理", "board", "task", "kanban"],
    "landing": ["落地页", "宣传页", "首页", "landing", "hero", "cta"]
}
```

### 4.3 资产能力

| 资产类型 | 用途 | 注入位置 |
|---------|------|---------|
| Logo | 导航栏与页脚 | `nav.logo` / `footer.logo` |
| 风格图 | 全局视觉约束 | Style Tokens |
| 背景图 | 首屏/分区背景 | `hero.background` / `section.background` |
| 产品图 | 商品/内容展示 | `card.image` / `detail.image` |

---

## 5. 数据模型

### 5.1 ProductDocStructured（核心）

```typescript
interface ProductDocStructured {
  product_type: "ecommerce" | "travel" | "manual" | "kanban" | "landing" | "card" | "invitation";
  complexity: "simple" | "medium" | "complex";

  // 页面清单
  pages: PageDefinition[];

  // 数据模型
  data_model: DataModel;

  // 组件注册表
  component_registry: ComponentRegistry;

  // 风格参考
  style_reference: StyleReference;

  // 资产注册
  asset_registry: AssetRegistry;
}

interface PageDefinition {
  slug: string;           // URL 路径
  title: string;          // 页面标题
  role: string;           // 页面角色 (catalog/detail/checkout/...)
  description?: string;   // 页面描述
}
```

### 5.2 DataModel（场景数据模型）

```typescript
interface DataModel {
  entities: Record<string, EntityDefinition>;
  relations: Relation[];
}

interface EntityDefinition {
  fields: FieldDefinition[];
  primaryKey: string;
}

interface FieldDefinition {
  name: string;
  type: "string" | "number" | "boolean" | "array" | "object";
  required: boolean;
  description?: string;
}

interface Relation {
  from: string;      // 源实体
  to: string;        // 目标实体
  type: "one-to-one" | "one-to-many" | "many-to-one" | "many-to-many";
  foreignKey: string;
}
```

**电商场景数据模型示例**：

```json
{
  "entities": {
    "Product": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "name", "type": "string", "required": true },
        { "name": "price", "type": "number", "required": true },
        { "name": "image", "type": "string", "required": true },
        { "name": "description", "type": "string", "required": false },
        { "name": "category_id", "type": "string", "required": true }
      ],
      "primaryKey": "id"
    },
    "Category": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "name", "type": "string", "required": true }
      ],
      "primaryKey": "id"
    },
    "CartItem": {
      "fields": [
        { "name": "order_id", "type": "string", "required": false },
        { "name": "product_id", "type": "string", "required": true },
        { "name": "quantity", "type": "number", "required": true }
      ],
      "primaryKey": "product_id"
    },
    "Order": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "items", "type": "array", "required": true },
        { "name": "total", "type": "number", "required": true },
        { "name": "status", "type": "string", "required": true },
        { "name": "created_at", "type": "string", "required": true }
      ],
      "primaryKey": "id"
    }
  },
  "relations": [
    { "from": "Product", "to": "Category", "type": "many-to-one", "foreignKey": "category_id" },
    { "from": "CartItem", "to": "Product", "type": "many-to-one", "foreignKey": "product_id" },
    { "from": "Order", "to": "CartItem", "type": "one-to-many", "foreignKey": "order_id" }
  ]
}
```

### 5.3 AssetRegistry

```typescript
interface AssetRegistry {
  logo?: AssetRef;
  style_refs: AssetRef[];
  backgrounds: AssetRef[];
  product_images: AssetRef[];
}

interface AssetRef {
  id: string;           // asset:{type}_{hash}
  url: string;          // /assets/{session_id}/logo_1.png
  type: "image/png" | "image/jpeg" | "image/webp" | "image/svg+xml";
  width?: number;
  height?: number;
}
```

### 5.4 ComponentRegistry

```typescript
interface ComponentRegistry {
  components: ComponentDefinition[];
  tokens: DesignTokens;
}

interface ComponentDefinition {
  id: string;           // nav-primary, card-product
  type: string;         // nav, card, hero, form, list, ...
  slots: string[];      // 可填充的插槽
  props: PropDefinition[];
  variants?: string[];  // 可选变体
}

interface PropDefinition {
  name: string;
  type: "string" | "number" | "boolean" | "asset" | "binding";
  required: boolean;
  default?: any;
}

interface DesignTokens {
  radius: "none" | "small" | "medium" | "large";
  spacing: "compact" | "normal" | "airy";
  shadow: "none" | "subtle" | "medium" | "strong";
}

// DesignTokens 为 StyleTokens 的归一化子集，用于组件一致性约束与默认样式映射
```

---

## 6. LangGraph 编排与节点

### 6.1 状态定义

```python
from typing import TypedDict, Optional, List
from langgraph.graph import StateGraph

class GraphState(TypedDict):
    # 输入
    session_id: str
    user_input: str
    assets: List[dict]

    # Brief 输出
    product_doc: Optional[dict]
    pages: List[dict]
    data_model: Optional[dict]

    # Style 输出
    style_tokens: Optional[dict]

    # Component Registry 输出
    component_registry: Optional[dict]

    # Generate 输出
    page_schemas: List[dict]

    # Aesthetic Scorer 输出
    aesthetic_enabled: bool  # 是否启用审美评分
    aesthetic_scores: Optional[dict]  # 各维度评分
    aesthetic_suggestions: List[dict]  # 优化建议 (AestheticSuggestion)

    # Refine 输入/输出
    user_feedback: Optional[str]

    # Render 输出
    build_artifacts: Optional[dict]
    build_status: str  # pending / building / success / failed

    # 错误处理
    error: Optional[str]
    retry_count: int
```

### 6.2 节点契约

| 节点 | 输入字段 | 输出字段 | 触发条件 |
|------|---------|---------|---------|
| **Brief** | `user_input`, `assets` | `product_doc`, `pages`, `data_model` | 初始入口 |
| **StyleExtractor** | `assets` (style_refs) | `style_tokens` | `assets` 包含风格图 |
| **ComponentRegistry** | `product_doc`, `style_tokens`, `pages` | `component_registry` | Brief 完成 |
| **Generate** | `component_registry`, `pages`, `data_model` | `page_schemas` | ComponentRegistry 完成 |
| **AestheticScorer** | `page_schemas`, `style_tokens` | `aesthetic_scores`, `aesthetic_suggestions` | 启用审美评分且为 Landing/Card/Invitation |
| **Refine** | `page_schemas`, `user_feedback`, `aesthetic_suggestions` | `page_schemas` (updated) | `user_feedback` 非空 |
| **Render** | `page_schemas`, `component_registry` | `build_artifacts`, `build_status` | Generate/Refine 完成 |

### 6.3 状态图定义

```python
from langgraph.graph import StateGraph, END

def create_generation_graph():
    graph = StateGraph(GraphState)

    # 添加节点
    graph.add_node("brief", brief_node)
    graph.add_node("style_extractor", style_extractor_node)
    graph.add_node("component_registry", component_registry_node)
    graph.add_node("generate", generate_node)
    graph.add_node("aesthetic_scorer", aesthetic_scorer_node)
    graph.add_node("check_refine", check_refine_node)  # no-op，用于条件分支汇合
    graph.add_node("refine", refine_node)
    graph.add_node("render", render_node)

    # 设置入口
    graph.set_entry_point("brief")

    # 添加边
    graph.add_edge("brief", "style_extractor")
    graph.add_edge("style_extractor", "component_registry")
    graph.add_edge("component_registry", "generate")

    # 条件分支：Generate 后检查是否启用审美评分
    graph.add_conditional_edges(
        "generate",
        should_score_aesthetic,
        {
            "aesthetic": "aesthetic_scorer",
            "skip": "check_refine"
        }
    )

    # 审美评分后进入 refine 检查
    graph.add_edge("aesthetic_scorer", "check_refine")

    # 条件分支：检查是否有用户反馈需要 refine
    graph.add_conditional_edges(
        "check_refine",
        should_refine,
        {
            "refine": "refine",
            "render": "render"
        }
    )

    graph.add_edge("refine", "render")
    graph.add_edge("render", END)

    return graph.compile()

def should_score_aesthetic(state: GraphState) -> str:
    """判断是否需要执行审美评分"""
    if not state.get("aesthetic_enabled", False):
        return "skip"
    product_type = state.get("product_doc", {}).get("product_type", "")
    if product_type in ("landing", "card", "invitation"):
        return "aesthetic"
    return "skip"

def check_refine_node(state: GraphState) -> GraphState:
    """占位节点：便于审美评分与非评分路径汇合"""
    return state

def should_refine(state: GraphState) -> str:
    if state.get("user_feedback"):
        return "refine"
    return "render"
```

### 6.4 错误处理与重试

```python
MAX_RETRIES = 3

def with_retry(node_fn):
    async def wrapper(state: GraphState) -> GraphState:
        retry_count = state.get("retry_count", 0)
        try:
            return await node_fn(state)
        except Exception as e:
            if retry_count < MAX_RETRIES:
                return {**state, "retry_count": retry_count + 1, "error": str(e)}
            else:
                return {**state, "error": f"Max retries exceeded: {e}", "build_status": "failed"}
    return wrapper
```

---

## 7. 页面 Schema 规范

### 7.1 PageSchema 结构

```typescript
interface PageSchema {
  slug: string;                    // 页面路径
  title: string;                   // 页面标题
  layout: "default" | "fullscreen" | "sidebar";
  components: ComponentInstance[];
  head?: HeadMeta;
}

interface ComponentInstance {
  id: string;                      // 引用 ComponentRegistry 中的组件 id
  key: string;                     // 实例唯一标识
  props: Record<string, PropValue>;
  children?: ComponentInstance[];
  repeat?: RepeatBinding;          // 循环渲染
  condition?: string;              // 条件渲染表达式
}

interface PropValue {
  type: "static" | "binding" | "asset";
  value: string | number | boolean | any[] | Record<string, any>;
}

interface RepeatBinding {
  source: string;                  // 数据源路径 e.g. "state.cart.items"
  itemName: string;                // 迭代变量名 e.g. "item"
}

interface HeadMeta {
  description?: string;
  keywords?: string[];
  ogImage?: string;
}
```

### 7.2 PageSchema 示例（购物车页）

```json
{
  "slug": "cart",
  "title": "购物车",
  "layout": "default",
  "head": {
    "description": "查看和管理您的购物车"
  },
  "components": [
    {
      "id": "nav-primary",
      "key": "nav-1",
      "props": {
        "logo": { "type": "asset", "value": "asset:logo_a1b2c3d4" },
        "links": { "type": "static", "value": [
          { "label": "首页", "href": "/" },
          { "label": "商品", "href": "/products" },
          { "label": "购物车", "href": "/cart", "active": true }
        ]}
      }
    },
    {
      "id": "section-header",
      "key": "header-1",
      "props": {
        "title": { "type": "static", "value": "购物车" },
        "subtitle": { "type": "binding", "value": "state.cart.items.length + ' 件商品'" }
      }
    },
    {
      "id": "card-product",
      "key": "cart-item",
      "repeat": {
        "source": "state.cart.items",
        "itemName": "item"
      },
      "props": {
        "image": { "type": "binding", "value": "item.product.image" },
        "title": { "type": "binding", "value": "item.product.name" },
        "price": { "type": "binding", "value": "item.product.price" },
        "quantity": { "type": "binding", "value": "item.quantity" }
      }
    },
    {
      "id": "cart-summary",
      "key": "summary-1",
      "props": {
        "total": { "type": "binding", "value": "state.cart.total" },
        "itemCount": { "type": "binding", "value": "state.cart.items.length" }
      }
    },
    {
      "id": "button-primary",
      "key": "checkout-btn",
      "props": {
        "label": { "type": "static", "value": "去结算" },
        "href": { "type": "static", "value": "/checkout" },
        "fullWidth": { "type": "static", "value": true }
      }
    },
    {
      "id": "footer-simple",
      "key": "footer-1",
      "props": {
        "copyright": { "type": "static", "value": "© 2026 Your Store" }
      }
    }
  ]
}
```

### 7.3 数据绑定语法

| 语法 | 说明 | 示例 |
|------|------|------|
| `state.xxx` | 读取 localStorage 状态 | `state.cart.items` |
| `item.xxx` | repeat 循环中的当前项 | `item.product.name` |
| `expr + expr` | 简单表达式 | `state.cart.items.length + ' 件'` |
| `xxx ? a : b` | 条件表达式 | `state.cart.total > 0 ? '去结算' : '空'` |

**表达式规范**：仅支持安全的表达式子集（属性访问、算术/比较/逻辑、三元、字符串拼接、数组 length），不执行任意 JS，不允许函数调用/全局对象访问。

---

## 8. 组件一致性与组件注册表

### 8.1 预置组件库

| 组件 ID | 类型 | 用途 | 映射 React 组件 |
|---------|------|------|----------------|
| `nav-primary` | nav | 主导航栏 | `@/components/Nav` |
| `nav-bottom` | nav | 底部导航 | `@/components/BottomNav` |
| `hero-banner` | hero | 首屏横幅 | `@/components/Hero` |
| `card-product` | card | 商品卡片 | `@/components/ProductCard` |
| `card-task` | card | 任务卡片 | `@/components/TaskCard` |
| `card-timeline` | card | 时间轴卡片 | `@/components/TimelineCard` |
| `list-simple` | list | 简单列表 | `@/components/SimpleList` |
| `list-grid` | list | 网格列表 | `@/components/GridList` |
| `form-basic` | form | 基础表单 | `@/components/BasicForm` |
| `form-checkout` | form | 结算表单 | `@/components/CheckoutForm` |
| `button-primary` | button | 主按钮 | `@/components/Button` |
| `button-secondary` | button | 次按钮 | `@/components/Button` |
| `section-header` | section | 区块标题 | `@/components/SectionHeader` |
| `cart-summary` | summary | 购物车摘要 | `@/components/CartSummary` |
| `order-summary` | summary | 订单摘要 | `@/components/OrderSummary` |
| `footer-simple` | footer | 简单页脚 | `@/components/Footer` |
| `breadcrumb` | nav | 面包屑 | `@/components/Breadcrumb` |
| `tabs-basic` | tabs | 基础标签页 | `@/components/Tabs` |
| `modal-confirm` | modal | 确认弹窗 | `@/components/ConfirmModal` |
| `toast-message` | toast | 消息提示 | `@/components/Toast` |

### 8.2 组件映射规则

```typescript
// 组件映射表
const COMPONENT_MAP: Record<string, React.ComponentType<any>> = {
  'nav-primary': Nav,
  'nav-bottom': BottomNav,
  'hero-banner': Hero,
  'card-product': ProductCard,
  'card-task': TaskCard,
  // ...
};

// Schema 渲染器
function renderComponent(instance: ComponentInstance, data: any): React.ReactNode {
  const Component = COMPONENT_MAP[instance.id];
  if (!Component) {
    console.warn(`Unknown component: ${instance.id}`);
    return null;
  }

  const resolvedProps = resolveProps(instance.props, data);

  if (instance.repeat) {
    const items = getNestedValue(data, instance.repeat.source) || [];
    return items.map((item, index) => (
      <Component
        key={`${instance.key}-${index}`}
        {...resolveProps(instance.props, { ...data, [instance.repeat.itemName]: item })}
      />
    ));
  }

  return <Component key={instance.key} {...resolvedProps} />;
}
```

### 8.3 一致性校验

```python
def validate_page_schema(schema: dict, registry: dict) -> List[str]:
    """校验页面 schema 中的组件是否都在注册表中"""
    errors = []
    registered_ids = {c["id"] for c in registry["components"]}

    def check_component(comp: dict, path: str):
        if comp["id"] not in registered_ids:
            errors.append(f"{path}: 未注册的组件 '{comp['id']}'")
        for i, child in enumerate(comp.get("children", [])):
            check_component(child, f"{path}.children[{i}]")

    for i, comp in enumerate(schema["components"]):
        check_component(comp, f"components[{i}]")

    return errors

def auto_fix_unknown_components(schema: dict, registry: dict) -> dict:
    """将未知组件替换为最接近的注册组件"""
    # 实现模糊匹配与替换逻辑
    pass
```

---

## 9. 风格参考与资产注册

### 9.1 风格提取流程

```
用户上传风格参考图
  ↓
Claude Vision API 分析
  ↓
输出 StyleTokens JSON
  ↓
注入 ComponentRegistry + Generate
```

### 9.2 StyleTokens 结构

```typescript
interface StyleTokens {
  colors: {
    primary: string;      // 主色 #3B82F6
    secondary: string;    // 辅色 #10B981
    accent: string;       // 强调色 #F59E0B
    background: string;   // 背景色 #FFFFFF
    surface: string;      // 表面色 #F3F4F6
    text: {
      primary: string;    // 主文字 #111827
      secondary: string;  // 次文字 #6B7280
      muted: string;      // 弱文字 #9CA3AF
    };
  };

  typography: {
    fontFamily: string;   // 'Inter, sans-serif'
    scale: "compact" | "normal" | "spacious";
  };

  radius: "none" | "small" | "medium" | "large" | "full";

  spacing: "compact" | "normal" | "airy";

  shadow: "none" | "subtle" | "medium" | "strong";

  style: "modern" | "classic" | "playful" | "minimal" | "bold";
}
```

### 9.3 风格提取 Prompt

```python
STYLE_EXTRACTION_PROMPT = """
分析这张图片的视觉设计风格，提取以下信息并以 JSON 格式返回：

1. colors: 识别主色、辅色、强调色、背景色、文字色
2. typography: 字体风格（现代/经典）、间距密度
3. radius: 圆角程度 (none/small/medium/large/full)
4. spacing: 元素间距 (compact/normal/airy)
5. shadow: 阴影强度 (none/subtle/medium/strong)
6. style: 整体风格 (modern/classic/playful/minimal/bold)

返回格式：
```json
{
  "colors": { ... },
  "typography": { ... },
  "radius": "...",
  "spacing": "...",
  "shadow": "...",
  "style": "..."
}
```
"""
```

### 9.4 资产注册服务

```python
class AssetRegistryService:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.base_path = Path(f"~/.instant-coffee/sessions/{session_id}/assets").expanduser()
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def register_asset(self, file: UploadFile, asset_type: str) -> AssetRef:
        """注册资产并返回引用"""
        asset_id = f"{asset_type}_{uuid4().hex[:8]}"
        file_ext = Path(file.filename).suffix
        file_path = self.base_path / f"{asset_id}{file_ext}"

        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(await file.read())

        # 获取图片尺寸
        with Image.open(file_path) as img:
            width, height = img.size

        return AssetRef(
            id=f"asset:{asset_id}",
            url=f"/assets/{self.session_id}/{asset_id}{file_ext}",
            type=file.content_type,
            width=width,
            height=height
        )

    def get_registry(self) -> AssetRegistry:
        """获取当前会话的资产注册表"""
        pass

# 约定：页面 Schema 仅允许引用 AssetRef.id（不可手写 URL）
```

### 9.5 风格优先级

冲突解决规则（从高到低）：

1. **风格参考图** - 用户上传的参考图提取的 tokens
2. **用户指定** - 用户明确指定的颜色/风格
3. **场景默认** - 场景类型的默认风格
4. **系统默认** - 全局默认值

---

## 10. Mobile Shell 与移动端约束

### 10.1 设计原则

- 9:19.5 **仅用于预览**（PhoneFrame 组件）
- 生成的 HTML **不锁死比例**，适配多种手机尺寸
- 通过 Mobile Shell 自动修复确保移动端可用

### 10.2 Mobile Shell 自动修复

```python
import re
from bs4 import BeautifulSoup

def ensure_mobile_shell(html: str) -> str:
    """
    自动修复 HTML 以确保移动端兼容性

    修复项：
    1. viewport meta 标签
    2. #app.page 根容器
    3. 基础 CSS 约束
    """
    soup = BeautifulSoup(html, 'html.parser')

    # 1. 确保 viewport meta
    viewport = soup.find('meta', attrs={'name': 'viewport'})
    if not viewport:
        viewport = soup.new_tag('meta')
        viewport['name'] = 'viewport'
        head = soup.find('head') or soup.new_tag('head')
        if not soup.find('head'):
            soup.html.insert(0, head)
        head.insert(0, viewport)
    viewport['content'] = 'width=device-width, initial-scale=1, viewport-fit=cover, maximum-scale=1'

    # 2. 确保 #app.page 容器
    body = soup.find('body')
    if body:
        app_container = soup.find(id='app')
        if not app_container:
            app_container = soup.new_tag('div')
            app_container['id'] = 'app'
            app_container['class'] = ['page']
            # 将 body 的所有子元素移入 app 容器
            for child in list(body.children):
                app_container.append(child.extract())
            body.append(app_container)
        elif 'page' not in app_container.get('class', []):
            app_container['class'] = app_container.get('class', []) + ['page']

    # 3. 注入基础 CSS
    mobile_css = """
    <style id="mobile-shell">
      * { box-sizing: border-box; }
      html, body {
        margin: 0;
        padding: 0;
        min-height: 100dvh;
        -webkit-font-smoothing: antialiased;
      }
      #app.page {
        max-width: min(430px, 100%);
        width: 100%;
        margin: 0 auto;
        min-height: 100dvh;
        overflow-x: hidden;
        position: relative;
      }
      /* 隐藏滚动条 */
      ::-webkit-scrollbar { display: none; }
      * { scrollbar-width: none; }
      /* 触摸优化 */
      button, a, [role="button"] {
        min-height: 44px;
        touch-action: manipulation;
      }
    </style>
    """

    existing_shell = soup.find('style', id='mobile-shell')
    if not existing_shell:
        head = soup.find('head')
        if head:
            head.append(BeautifulSoup(mobile_css, 'html.parser'))

    return str(soup)
```

### 10.3 校验规则

```python
MOBILE_VALIDATION_RULES = [
    {
        "id": "viewport",
        "description": "必须包含正确的 viewport meta",
        "check": lambda soup: soup.find('meta', attrs={'name': 'viewport'}) is not None,
        "auto_fix": True
    },
    {
        "id": "app_container",
        "description": "必须包含 #app.page 容器",
        "check": lambda soup: soup.find(id='app') is not None,
        "auto_fix": True
    },
    {
        "id": "max_width",
        "description": "#app 容器必须设置 max-width",
        "check": lambda soup: (
            soup.find('style', id='mobile-shell') and 'max-width' in soup.find('style', id='mobile-shell').text
        ) or (
            soup.find(id='app') and 'max-width' in str(soup.find(id='app').get('style', ''))
        ),
        "auto_fix": True
    },
    {
        "id": "touch_targets",
        "description": "可点击元素最小高度 44px",
        "check": check_touch_targets,
        "auto_fix": False  # 需要手动修复
    }
]
```

---

## 11. 数据流与 Data Tab

### 11.1 localStorage 协议

```typescript
// 命名空间
const NAMESPACE = 'instant-coffee';

// 存储结构
interface DataStore {
  state: Record<string, any>;     // 当前状态
  records: DataRecord[];          // 持久化记录
  events: Event[];                // 事件日志
}

interface DataRecord {
  id: string;
  type: string;
  data: Record<string, any>;
  timestamp: string;
}

// 存储键
const KEYS = {
  state: `${NAMESPACE}:state`,
  records: `${NAMESPACE}:records`,
  events: `${NAMESPACE}:events`
};
```

### 11.2 场景事件定义

```typescript
type EventType =
  // 通用
  | 'page_view'
  | 'click'
  // 电商
  | 'add_to_cart'
  | 'remove_from_cart'
  | 'checkout_start'
  | 'order_submitted'
  | 'payment_success'
  // 旅行
  | 'save_plan'
  | 'share_link'
  | 'add_bookmark'
  // 说明书
  | 'search'
  | 'reading_progress'
  // 看板
  | 'task_created'
  | 'task_moved'
  | 'task_completed'
  // Landing
  | 'lead_submitted'
  | 'cta_click';

interface Event {
  id: string;
  type: EventType;
  timestamp: string;
  payload: Record<string, any>;
  page?: string;
}
```

### 11.3 Data Tab 场景分类

```typescript
const EVENT_CATEGORIES: Record<string, EventType[]> = {
  ecommerce: ['add_to_cart', 'remove_from_cart', 'checkout_start', 'order_submitted', 'payment_success'],
  travel: ['save_plan', 'share_link', 'add_bookmark'],
  manual: ['page_view', 'search', 'reading_progress'],
  kanban: ['task_created', 'task_moved', 'task_completed'],
  landing: ['lead_submitted', 'cta_click']
};

// UI 显示
const EVENT_LABELS: Record<EventType, { label: string; icon: string; color: string }> = {
  add_to_cart: { label: '加入购物车', icon: '🛒', color: 'blue' },
  order_submitted: { label: '订单提交', icon: '📦', color: 'green' },
  task_created: { label: '任务创建', icon: '✅', color: 'purple' },
  // ...
};
```

### 11.4 postMessage 桥接

```typescript
// 预览 iframe 内
const ALLOWED_ORIGIN = new URL(document.referrer || location.origin).origin; // 或由配置注入
window.addEventListener('message', (event) => {
  if (event.origin !== ALLOWED_ORIGIN) return;
  if (event.data.type === 'DATA_TAB_REQUEST') {
    const store = {
      state: JSON.parse(localStorage.getItem('instant-coffee:state') || '{}'),
      records: JSON.parse(localStorage.getItem('instant-coffee:records') || '[]'),
      events: JSON.parse(localStorage.getItem('instant-coffee:events') || '[]')
    };
    parent.postMessage({ type: 'DATA_TAB_RESPONSE', payload: store }, ALLOWED_ORIGIN);
  }
});

// 主应用
function requestDataTabUpdate() {
  previewIframe.contentWindow?.postMessage({ type: 'DATA_TAB_REQUEST' }, ALLOWED_ORIGIN);
}
```

---

## 12. 审美评分

### 12.1 功能定位

审美评分是一个**可选功能**，用于评估生成页面的视觉质量，提供优化建议。

- **默认关闭**：需要通过配置或 API 参数显式启用
- **适用场景**：Landing Page、Card/Invitation 类型页面
- **不阻断流程**：低于阈值仅提供建议，不阻止渲染

### 12.2 启用条件

```python
def should_enable_aesthetic_scoring(product_doc: dict, config: dict) -> bool:
    """判断是否启用审美评分"""
    # 用户配置显式启用
    if not config.get("aesthetic_scoring_enabled", False):
        return False

    # 仅 Landing/Card 场景启用
    product_type = product_doc.get("product_type", "")
    return product_type in ("landing", "card", "invitation")
```

### 12.3 评分维度

| 维度 | 权重 | 说明 | 评分标准 |
|------|------|------|---------|
| **视觉层次** | 25% | 信息层级清晰度 | 标题/正文/辅助文字的对比度 |
| **色彩和谐** | 20% | 色彩搭配协调性 | 主色/辅色/强调色的搭配 |
| **间距一致性** | 20% | 元素间距的规律性 | 符合 8px 栅格系统 |
| **对齐规范** | 15% | 元素对齐方式 | 左对齐/居中/右对齐一致 |
| **可读性** | 10% | 文字可读性 | 字号、行高、对比度 |
| **移动端适配** | 10% | 移动端体验 | 触摸目标、滚动体验 |

### 12.4 评分结构

```typescript
interface AestheticScore {
  overall: number;           // 总分 0-100
  dimensions: {
    visualHierarchy: number; // 视觉层次 0-100
    colorHarmony: number;    // 色彩和谐 0-100
    spacingConsistency: number; // 间距一致性 0-100
    alignment: number;       // 对齐规范 0-100
    readability: number;     // 可读性 0-100
    mobileAdaptation: number; // 移动端适配 0-100
  };
  suggestions: AestheticSuggestion[];
  passThreshold: boolean;    // 是否通过阈值
}

interface AestheticSuggestion {
  dimension: string;         // 所属维度
  severity: "info" | "warning" | "critical";
  message: string;           // 建议内容
  location?: string;         // 涉及的组件/位置
  autoFixable: boolean;      // 是否可自动修复
}
```

### 12.5 评分阈值

| 场景 | 通过阈值 | 建议阈值 | 说明 |
|------|---------|---------|------|
| Landing | 70 | 85 | 高标准，直接影响转化 |
| Card | 65 | 80 | 中等标准 |
| 其他 | 60 | 75 | 基础标准 |

### 12.6 评分实现

```python
from typing import Optional

class AestheticScorerAgent:
    """审美评分 Agent"""

    SCORING_PROMPT = """
    分析这个页面的视觉设计质量，从以下维度评分（0-100）：

    1. **视觉层次 (Visual Hierarchy)**: 信息层级是否清晰？标题、正文、辅助文字的对比是否明显？
    2. **色彩和谐 (Color Harmony)**: 色彩搭配是否协调？主色、辅色、强调色是否和谐？
    3. **间距一致性 (Spacing Consistency)**: 元素间距是否遵循规律？是否符合 8px 栅格？
    4. **对齐规范 (Alignment)**: 元素对齐方式是否一致？是否有不规则的偏移？
    5. **可读性 (Readability)**: 文字是否易读？字号、行高、对比度是否合适？
    6. **移动端适配 (Mobile Adaptation)**: 触摸目标是否足够大？滚动体验是否流畅？

    对于每个低于 70 分的维度，提供具体的改进建议。

    返回 JSON 格式：
    ```json
    {
      "overall": 75,
      "dimensions": {
        "visualHierarchy": 80,
        "colorHarmony": 70,
        "spacingConsistency": 75,
        "alignment": 85,
        "readability": 72,
        "mobileAdaptation": 68
      },
      "suggestions": [
        {
          "dimension": "mobileAdaptation",
          "severity": "warning",
          "message": "底部按钮高度不足 44px，建议增加到 48px",
          "location": "button-primary",
          "autoFixable": true
        }
      ]
    }
    ```
    """

    async def score(
        self,
        page_schema: dict,
        rendered_html: Optional[str],
        style_tokens: dict
    ) -> AestheticScore:
        """执行审美评分"""
        # 1. 将 HTML 渲染为截图（可选；无 HTML 时仅基于 schema + tokens）
        # 2. 使用 Vision API 分析
        # 3. 返回结构化评分

        response = await self.llm.invoke(
            messages=[
                {"role": "system", "content": self.SCORING_PROMPT},
                {"role": "user", "content": f"页面 Schema:\n{json.dumps(page_schema)}\n\n风格 Tokens:\n{json.dumps(style_tokens)}"}
            ]
        )

        return self._parse_score(response)

    def _parse_score(self, response: str) -> AestheticScore:
        """解析评分结果"""
        data = json.loads(response)
        return AestheticScore(**data)
```

### 12.7 建议自动应用

对于 `autoFixable: true` 的建议，可选择自动应用：

```python
async def auto_fix_suggestions(
    page_schema: dict,
    suggestions: List[AestheticSuggestion]
) -> dict:
    """自动应用可修复的建议"""
    for suggestion in suggestions:
        if not suggestion.autoFixable:
            continue

        if suggestion.dimension == "mobileAdaptation":
            # 修复触摸目标大小
            fix_touch_targets(page_schema, suggestion)
        elif suggestion.dimension == "spacingConsistency":
            # 修复间距
            fix_spacing(page_schema, suggestion)
        # ... 其他修复逻辑

    return page_schema
```

### 12.8 前端展示

审美评分结果在前端展示为可折叠的评分卡片：

```typescript
interface AestheticScoreDisplay {
  showInPreview: boolean;    // 是否在预览区显示
  expandedByDefault: boolean; // 是否默认展开
  showSuggestions: boolean;   // 是否显示建议
  allowAutoFix: boolean;      // 是否允许一键修复
}
```

---

## 13. 构建与托管方案

### 13.1 构建流程

```
┌─────────────────────────────────────────────────────┐
│                   Render Node                        │
├─────────────────────────────────────────────────────┤
│  1. 接收 page_schemas + component_registry          │
│  2. 写入模板项目:                                    │
│     - src/pages/*.tsx (页面组件)                    │
│     - src/data/schema.json (页面配置)               │
│     - src/data/tokens.json (风格 tokens)            │
│  3. 执行构建:                                        │
│     npm run build                                    │
│  4. 输出 dist/ 到会话目录                           │
│  5. 执行 Mobile Shell 修复                          │
└─────────────────────────────────────────────────────┘
```

### 13.2 模板项目结构

```
templates/react-ssg/
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── components/           # 预置组件库
│   │   ├── Nav.tsx
│   │   ├── Hero.tsx
│   │   ├── ProductCard.tsx
│   │   └── ...
│   ├── pages/                # 由 Render Node 生成
│   │   └── .gitkeep
│   ├── data/                 # 由 Render Node 写入
│   │   └── .gitkeep
│   └── lib/
│       ├── data-store.ts     # localStorage 封装
│       └── schema-renderer.ts # Schema 渲染器
└── public/
    └── assets/               # 静态资产
```

### 13.3 构建实现

```python
import subprocess
import shutil
from pathlib import Path

class ReactSSGBuilder:
    TEMPLATE_PATH = Path(__file__).parent / "templates" / "react-ssg"

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.work_dir = Path(f"~/.instant-coffee/sessions/{session_id}/build").expanduser()
        self.dist_dir = Path(f"~/.instant-coffee/sessions/{session_id}/dist").expanduser()

    async def build(
        self,
        page_schemas: List[dict],
        component_registry: dict,
        style_tokens: dict,
        assets: dict
    ) -> dict:
        """执行 React SSG 构建"""

        # 1. 复制模板
        if self.work_dir.exists():
            shutil.rmtree(self.work_dir)
        shutil.copytree(self.TEMPLATE_PATH, self.work_dir)

        # 2. 写入配置
        (self.work_dir / "src/data/schemas.json").write_text(
            json.dumps(page_schemas, ensure_ascii=False, indent=2)
        )
        (self.work_dir / "src/data/tokens.json").write_text(
            json.dumps(style_tokens, ensure_ascii=False, indent=2)
        )
        (self.work_dir / "src/data/registry.json").write_text(
            json.dumps(component_registry, ensure_ascii=False, indent=2)
        )

        # 3. 复制资产
        assets_dir = self.work_dir / "public/assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        for asset in assets.get("files", []):
            shutil.copy(asset["path"], assets_dir / asset["filename"])

        # 4. 安装依赖 & 构建
        install_cmd = ["npm", "ci"] if (self.work_dir / "package-lock.json").exists() else ["npm", "install"]
        result = subprocess.run(
            install_cmd,
            cwd=self.work_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise BuildError(f"npm install failed: {result.stderr}")

        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=self.work_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise BuildError(f"Build failed: {result.stderr}")

        # 5. 移动 dist
        build_dist = self.work_dir / "dist"
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
        shutil.move(build_dist, self.dist_dir)

        # 6. Mobile Shell 修复
        for html_file in self.dist_dir.rglob("*.html"):
            content = html_file.read_text()
            fixed = ensure_mobile_shell(content)
            html_file.write_text(fixed)

        return {
            "status": "success",
            "dist_path": str(self.dist_dir),
            "pages": [p.name for p in self.dist_dir.rglob("*.html")]
        }
```

### 13.4 托管服务

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# 静态文件服务
@app.get("/preview/{session_id}/{path:path}")
async def serve_preview(session_id: str, path: str):
    dist_dir = Path(f"~/.instant-coffee/sessions/{session_id}/dist").expanduser()
    file_path = (dist_dir / path).resolve()
    if dist_dir not in file_path.parents and file_path != dist_dir:
        raise HTTPException(400, "Invalid path")

    if file_path.is_dir() or not file_path.exists():
        # 尝试 index.html
        file_path = (file_path / "index.html").resolve()
        if dist_dir not in file_path.parents:
            raise HTTPException(400, "Invalid path")

    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    raise HTTPException(404, "File not found")

# 分享链接（只读）
@app.get("/share/{session_id}")
async def share_redirect(session_id: str):
    return RedirectResponse(f"/preview/{session_id}/index.html")
```

### 13.5 存储路径

```
~/.instant-coffee/
├── sessions/
│   └── {session_id}/
│       ├── build/              # 构建工作目录（临时）
│       ├── dist/               # 构建产物（托管）
│       │   ├── index.html
│       │   ├── pages/
│       │   └── assets/
│       ├── assets/             # 用户上传的资产
│       ├── schemas/            # 页面 Schema JSON
│       └── session.db          # 会话元数据
└── templates/
    └── react-ssg/              # 构建模板（只读）
```

---

## 14. API 与前端设计

### 14.1 新增 API 端点

```python
# 资产上传
@router.post("/sessions/{session_id}/assets")
async def upload_asset(
    session_id: str,
    file: UploadFile,
    asset_type: str = Query(..., enum=["logo", "style_ref", "background", "product_image"])
) -> AssetRef:
    pass

# 获取资产列表
@router.get("/sessions/{session_id}/assets")
async def list_assets(session_id: str) -> AssetRegistry:
    pass

# 触发构建
@router.post("/sessions/{session_id}/build")
async def trigger_build(session_id: str) -> BuildStatus:
    pass

# 获取构建状态
@router.get("/sessions/{session_id}/build/status")
async def get_build_status(session_id: str) -> BuildStatus:
    pass

# 获取页面 Schema
@router.get("/sessions/{session_id}/schemas")
async def get_page_schemas(session_id: str) -> List[PageSchema]:
    pass

# 获取组件注册表
@router.get("/sessions/{session_id}/registry")
async def get_component_registry(session_id: str) -> ComponentRegistry:
    pass
```

### 14.2 前端变更

| 组件 | 变更 |
|------|------|
| `ChatInput` | 新增资产上传按钮（支持多类型） |
| `PreviewPanel` | 保持 9:19.5 预览，新增构建状态指示 |
| `DataTab` | 按场景分类显示事件 |
| `PageSelector` | 支持多页选择与预览 |

### 14.3 SSE 事件扩展

```typescript
type SSEEventType =
  | 'brief_start' | 'brief_complete'
  | 'style_extracted'
  | 'registry_complete'
  | 'generate_start' | 'generate_progress' | 'generate_complete'
  | 'refine_start' | 'refine_complete'
  | 'build_start' | 'build_progress' | 'build_complete' | 'build_failed';
```

### 14.4 SSE Payload 约定

```typescript
interface SSEEvent<T = any> {
  type: SSEEventType;
  session_id: string;
  timestamp: string;
  payload?: T;
}

type ProgressPayload = {
  step?: string;
  percent?: number;      // 0-100
  message?: string;
  page?: string;         // 对应页面 slug（可选）
};

type ErrorPayload = {
  error: string;
  retry_count?: number;
};
```

> 约定：前端 `packages/web/src/types/events.ts` 与后端事件模型保持一致。

---

## 15. 迁移与实施拆分

### 15.1 迁移阶段

```
┌─────────────────────────────────────────────────────────────┐
│  M1: LangGraph 编排骨架                                      │
│  ├─ 添加 langgraph 依赖                                     │
│  ├─ 创建 StateGraph 与状态定义                              │
│  ├─ 实现 Brief/Generate/Refine 核心节点                     │
│  └─ Feature Flag: use_langgraph=true 切换                   │
│                          ↓                                   │
├─────────────────────────────────────────────────────────────┤
│  M2: 场景旅程能力          │  M3: Component Registry        │
│  ├─ 场景检测规则           │  ├─ 组件注册表节点              │
│  ├─ 数据模型字段定义       │  ├─ 预置组件库 (20+)           │
│  └─ ProductDoc 扩展        │  └─ 一致性校验                  │
│              ↘            ↙                                  │
├─────────────────────────────────────────────────────────────┤
│  M4: React SSG 构建链路                                      │
│  ├─ 模板项目创建                                            │
│  ├─ Render Node 实现                                        │
│  ├─ 构建服务与托管                                          │
│  └─ 依赖: M3 完成                                           │
│                          ↓                                   │
├─────────────────────────────────────────────────────────────┤
│  M5: Mobile Shell          │  M6: 资产注册                   │
│  ├─ ensure_mobile_shell()  │  ├─ AssetRegistryService       │
│  ├─ 校验规则扩展           │  ├─ 风格提取 Prompt            │
│  └─ 自动修复后处理         │  └─ StyleExtractor 节点        │
│              ↘            ↙                                  │
├─────────────────────────────────────────────────────────────┤
│  M7: 审美评分              │  M8: 前端适配与 Data Tab        │
│  ├─ AestheticScorer 节点   │  ├─ ChatInput 资产上传          │
│  ├─ 评分维度与阈值         │  ├─ Data Tab 场景分类           │
│  ├─ 建议自动应用           │  ├─ 审美评分 UI 展示            │
│  └─ Feature Flag 控制      │  └─ 构建状态 UI                 │
└─────────────────────────────────────────────────────────────┘
```

### 15.2 依赖关系

| 阶段 | 依赖 | 可并行 |
|------|------|--------|
| M1 | 无 | - |
| M2 | M1 | M2 ↔ M3 可并行 |
| M3 | M1 | M2 ↔ M3 可并行 |
| M4 | M3 | - |
| M5 | M4 | M5 ↔ M6 可并行 |
| M6 | M1 | M5 ↔ M6 可并行 |
| M7 | M4 | M7 ↔ M8 可并行 |
| M8 | M4, M5, M6, M7 | - |

### 15.3 Feature Flag 策略

```python
# config.py
class FeatureFlags:
    USE_LANGGRAPH = os.getenv("FF_USE_LANGGRAPH", "false").lower() == "true"
    USE_REACT_SSG = os.getenv("FF_USE_REACT_SSG", "false").lower() == "true"
    ENABLE_STYLE_EXTRACTOR = os.getenv("FF_STYLE_EXTRACTOR", "false").lower() == "true"
    ENABLE_AESTHETIC_SCORING = os.getenv("FF_AESTHETIC_SCORING", "false").lower() == "true"

# 使用
if FeatureFlags.USE_LANGGRAPH:
    result = await langgraph_pipeline.run(state)
else:
    result = await legacy_orchestrator.run(state)
```

### 15.4 工作量估算

| 阶段 | 预计工作量 | 关键风险 |
|------|-----------|---------|
| M1 | 3-4 天 | LangGraph 学习曲线 |
| M2 | 2-3 天 | 场景覆盖完整性 |
| M3 | 2-3 天 | 组件库设计 |
| M4 | 4-5 天 | 构建稳定性、Node 子进程 |
| M5 | 1-2 天 | HTML 解析边界情况 |
| M6 | 2-3 天 | Vision API 准确性 |
| M7 | 2-3 天 | 评分维度设计、Vision API |
| M8 | 2-3 天 | 前后端对接 |
| **总计** | **18-26 天** | - |

---

## 16. 文件变更清单

### 16.1 新增文件

```
packages/backend/
├── app/graph/
│   ├── __init__.py
│   ├── state.py              # GraphState 定义
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── brief.py          # Brief Node
│   │   ├── style_extractor.py
│   │   ├── component_registry.py
│   │   ├── generate.py
│   │   ├── aesthetic_scorer.py  # 审美评分节点
│   │   ├── refine.py
│   │   └── render.py
│   └── graph.py              # StateGraph 组装
├── app/renderer/
│   ├── __init__.py
│   ├── builder.py            # ReactSSGBuilder
│   └── templates/
│       └── react-ssg/        # 模板项目
├── app/services/
│   ├── asset_registry.py
│   ├── style_extractor.py
│   └── aesthetic_scorer.py   # 审美评分服务
├── app/schemas/
│   └── aesthetic.py          # 审美评分数据结构
└── requirements.txt          # + langgraph

packages/web/
└── src/components/custom/
    ├── BuildStatus.tsx       # 构建状态组件
    └── AestheticScore.tsx    # 审美评分展示组件
```

### 16.2 修改文件

```
packages/backend/
├── app/agents/orchestrator.py    # Feature Flag 切换
├── app/generators/mobile_html.py # + ensure_mobile_shell()
├── app/schemas/product_doc.py    # 场景数据模型字段
├── app/api/chat.py               # LangGraph 集成
└── app/config.py                 # Feature Flags (含 AESTHETIC_SCORING)

packages/web/
├── src/components/custom/ChatInput.tsx      # 资产上传
├── src/components/custom/DataTab.tsx        # 场景分类
├── src/components/custom/PreviewPanel.tsx   # 构建状态 + 审美评分
└── src/types/events.ts                      # 新事件类型
```

---

## 17. 验收标准

### 17.1 功能验收

| 编号 | 验收项 | 测试方法 | 通过标准 |
|------|-------|---------|---------|
| A1 | LangGraph 编排完整闭环 | E2E 测试 | Brief→Registry→Generate→Render 完成 |
| A2 | React SSG 产物可访问 | 浏览器访问 | dist/index.html 200 OK |
| A3 | 多页生成 | 生成电商场景 | ≥3 个页面（Home/Cart/Checkout） |
| A4 | Mobile Shell 注入 | DOM 检查 | viewport + #app.page 存在 |
| A5 | 组件一致性 | Schema 校验 | 0 个未注册组件 |
| A6 | 风格提取 | 上传参考图 | 输出 StyleTokens JSON |
| A7 | 场景能力 | 五大场景测试 | 每场景输出正确页面清单 |
| A8 | Data Tab 事件 | UI 检查 | 显示场景对应事件 |
| A9 | 9:19.5 预览 | UI 检查 | PhoneFrame 比例正确 |
| A10 | 资产上传 | 功能测试 | Logo/背景/风格图可上传并引用 |
| A11 | 审美评分执行 | Landing 页面测试 | 启用时输出 AestheticScore JSON |
| A12 | 审美评分建议 | 低分场景测试 | 输出 ≥1 条优化建议 |
| A13 | 审美评分 UI | 前端检查 | 评分卡片正确显示，可展开/折叠 |

### 17.2 性能验收

| 编号 | 验收项 | 测试方法 | 通过标准 |
|------|-------|---------|---------|
| P1 | 端到端生成延迟 | 计时 | ≤90 秒（简单场景，不含审美评分） |
| P2 | 构建时间 | 计时 | ≤30 秒（npm run build） |
| P3 | 产物大小 | 文件检查 | ≤500KB（HTML + 首屏关键 CSS/JS） |
| P4 | 首屏加载 | Lighthouse | LCP ≤2.5 秒 |
| P5 | 审美评分延迟 | 计时 | ≤15 秒（单页评分） |

### 17.3 质量验收

| 编号 | 验收项 | 测试方法 | 通过标准 |
|------|-------|---------|---------|
| Q1 | Mobile Shell 校验 | 自动化检查 | 100% 通过率 |
| Q2 | 组件注册表覆盖 | 统计 | 预置组件 ≥20 个 |
| Q3 | 错误处理 | 异常注入 | 重试 3 次后优雅降级 |
| Q4 | 回滚能力 | 功能测试 | 可回滚到任意版本 |
| Q5 | 审美评分覆盖 | 维度检查 | 6 个维度全部输出 |
| Q6 | 评分阈值 | Landing 测试 | 通过阈值 70 分，建议阈值 85 分 |

---

## 附录 A: 场景数据模型完整定义

### A.1 电商场景

```json
{
  "entities": {
    "Product": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "name", "type": "string", "required": true },
        { "name": "price", "type": "number", "required": true },
        { "name": "originalPrice", "type": "number", "required": false },
        { "name": "image", "type": "string", "required": true },
        { "name": "images", "type": "array", "required": false },
        { "name": "description", "type": "string", "required": false },
        { "name": "category_id", "type": "string", "required": true },
        { "name": "stock", "type": "number", "required": false },
        { "name": "tags", "type": "array", "required": false }
      ],
      "primaryKey": "id"
    },
    "Category": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "name", "type": "string", "required": true },
        { "name": "icon", "type": "string", "required": false }
      ],
      "primaryKey": "id"
    },
    "CartItem": {
      "fields": [
        { "name": "order_id", "type": "string", "required": false },
        { "name": "product_id", "type": "string", "required": true },
        { "name": "quantity", "type": "number", "required": true },
        { "name": "selected", "type": "boolean", "required": false }
      ],
      "primaryKey": "product_id"
    },
    "Order": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "items", "type": "array", "required": true },
        { "name": "total", "type": "number", "required": true },
        { "name": "status", "type": "string", "required": true },
        { "name": "shippingAddress", "type": "object", "required": false },
        { "name": "user_id", "type": "string", "required": false },
        { "name": "created_at", "type": "string", "required": true }
      ],
      "primaryKey": "id"
    },
    "User": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "name", "type": "string", "required": true },
        { "name": "avatar", "type": "string", "required": false },
        { "name": "phone", "type": "string", "required": false }
      ],
      "primaryKey": "id"
    }
  },
  "relations": [
    { "from": "Product", "to": "Category", "type": "many-to-one", "foreignKey": "category_id" },
    { "from": "CartItem", "to": "Product", "type": "many-to-one", "foreignKey": "product_id" },
    { "from": "Order", "to": "CartItem", "type": "one-to-many", "foreignKey": "order_id" },
    { "from": "Order", "to": "User", "type": "many-to-one", "foreignKey": "user_id" }
  ]
}
```

### A.2 旅行行程场景

```json
{
  "entities": {
    "Trip": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "title", "type": "string", "required": true },
        { "name": "destination", "type": "string", "required": true },
        { "name": "startDate", "type": "string", "required": true },
        { "name": "endDate", "type": "string", "required": true },
        { "name": "coverImage", "type": "string", "required": false },
        { "name": "description", "type": "string", "required": false }
      ],
      "primaryKey": "id"
    },
    "DayPlan": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "trip_id", "type": "string", "required": true },
        { "name": "date", "type": "string", "required": true },
        { "name": "dayNumber", "type": "number", "required": true },
        { "name": "title", "type": "string", "required": false }
      ],
      "primaryKey": "id"
    },
    "Activity": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "day_id", "type": "string", "required": true },
        { "name": "time", "type": "string", "required": true },
        { "name": "title", "type": "string", "required": true },
        { "name": "location_id", "type": "string", "required": false },
        { "name": "location", "type": "string", "required": false },
        { "name": "duration", "type": "number", "required": false },
        { "name": "notes", "type": "string", "required": false }
      ],
      "primaryKey": "id"
    },
    "Location": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "name", "type": "string", "required": true },
        { "name": "address", "type": "string", "required": false },
        { "name": "lat", "type": "number", "required": false },
        { "name": "lng", "type": "number", "required": false },
        { "name": "type", "type": "string", "required": false }
      ],
      "primaryKey": "id"
    }
  },
  "relations": [
    { "from": "DayPlan", "to": "Trip", "type": "many-to-one", "foreignKey": "trip_id" },
    { "from": "Activity", "to": "DayPlan", "type": "many-to-one", "foreignKey": "day_id" },
    { "from": "Activity", "to": "Location", "type": "many-to-one", "foreignKey": "location_id" }
  ]
}
```

### A.3 说明书场景

```json
{
  "entities": {
    "Manual": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "title", "type": "string", "required": true },
        { "name": "version", "type": "string", "required": false },
        { "name": "lastUpdated", "type": "string", "required": false }
      ],
      "primaryKey": "id"
    },
    "Section": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "manual_id", "type": "string", "required": true },
        { "name": "title", "type": "string", "required": true },
        { "name": "order", "type": "number", "required": true },
        { "name": "parent_id", "type": "string", "required": false }
      ],
      "primaryKey": "id"
    },
    "Page": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "section_id", "type": "string", "required": true },
        { "name": "title", "type": "string", "required": true },
        { "name": "content", "type": "string", "required": true },
        { "name": "order", "type": "number", "required": true }
      ],
      "primaryKey": "id"
    }
  },
  "relations": [
    { "from": "Section", "to": "Manual", "type": "many-to-one", "foreignKey": "manual_id" },
    { "from": "Section", "to": "Section", "type": "many-to-one", "foreignKey": "parent_id" },
    { "from": "Page", "to": "Section", "type": "many-to-one", "foreignKey": "section_id" }
  ]
}
```

### A.4 看板场景

```json
{
  "entities": {
    "Board": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "title", "type": "string", "required": true },
        { "name": "description", "type": "string", "required": false }
      ],
      "primaryKey": "id"
    },
    "Column": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "board_id", "type": "string", "required": true },
        { "name": "title", "type": "string", "required": true },
        { "name": "order", "type": "number", "required": true },
        { "name": "color", "type": "string", "required": false }
      ],
      "primaryKey": "id"
    },
    "Task": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "column_id", "type": "string", "required": true },
        { "name": "title", "type": "string", "required": true },
        { "name": "description", "type": "string", "required": false },
        { "name": "priority", "type": "string", "required": false },
        { "name": "dueDate", "type": "string", "required": false },
        { "name": "assignee_id", "type": "string", "required": false },
        { "name": "order", "type": "number", "required": true }
      ],
      "primaryKey": "id"
    },
    "User": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "name", "type": "string", "required": true },
        { "name": "avatar", "type": "string", "required": false }
      ],
      "primaryKey": "id"
    },
    "Tag": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "name", "type": "string", "required": true },
        { "name": "color", "type": "string", "required": true }
      ],
      "primaryKey": "id"
    }
  },
  "relations": [
    { "from": "Column", "to": "Board", "type": "many-to-one", "foreignKey": "board_id" },
    { "from": "Task", "to": "Column", "type": "many-to-one", "foreignKey": "column_id" },
    { "from": "Task", "to": "User", "type": "many-to-one", "foreignKey": "assignee_id" }
  ]
}
```

### A.5 Landing 场景

```json
{
  "entities": {
    "Lead": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "email", "type": "string", "required": true },
        { "name": "name", "type": "string", "required": false },
        { "name": "phone", "type": "string", "required": false },
        { "name": "company", "type": "string", "required": false },
        { "name": "message", "type": "string", "required": false },
        { "name": "source", "type": "string", "required": false },
        { "name": "created_at", "type": "string", "required": true }
      ],
      "primaryKey": "id"
    },
    "Feature": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "title", "type": "string", "required": true },
        { "name": "description", "type": "string", "required": true },
        { "name": "icon", "type": "string", "required": false }
      ],
      "primaryKey": "id"
    },
    "Testimonial": {
      "fields": [
        { "name": "id", "type": "string", "required": true },
        { "name": "quote", "type": "string", "required": true },
        { "name": "author", "type": "string", "required": true },
        { "name": "role", "type": "string", "required": false },
        { "name": "avatar", "type": "string", "required": false }
      ],
      "primaryKey": "id"
    }
  },
  "relations": []
}
```

---

## 附录 B: 预置组件 Props 定义

### B.1 nav-primary

```typescript
interface NavPrimaryProps {
  logo: AssetRef;
  links: Array<{
    label: string;
    href: string;
    active?: boolean;
  }>;
  showSearch?: boolean;
  showCart?: boolean;
  cartCount?: number;
}
```

### B.2 card-product

```typescript
interface CardProductProps {
  image: string;
  title: string;
  price: number;
  originalPrice?: number;
  badge?: string;
  rating?: number;
  onClick?: () => void;
}
```

### B.3 hero-banner

```typescript
interface HeroBannerProps {
  title: string;
  subtitle?: string;
  backgroundImage?: string;
  backgroundColor?: string;
  cta?: {
    label: string;
    href: string;
  };
  alignment?: 'left' | 'center' | 'right';
}
```

（其他组件 Props 定义略，完整列表见组件库文档）

---

**文档结束**

版本: v0.7.1
最后更新: 2026-02-05
