# Instant Coffee - 技术规格说明书 (Spec v0.6)

**项目名称**: Instant Coffee (速溶咖啡)
**版本**: v0.6 - Skills 编排 + Orchestrator 路由 + 多模型路由 + 数据传递 + 风格参考 + 移动端约束
**日期**: 2026-02-03
**文档类型**: Technical Specification Document (TSD)

---

## 文档变更历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v0.6 | 2026-02-03 | 引入 Skills 生成策略、Orchestrator 路由、多模型分工、产品文档分级、跨页面数据传递、风格参考、移动端 guardrails 与 Preview Data Tab | Planning |

---

## 设计决策记录

### 核心决策

| 问题 | 决策 | 说明 |
|------|------|------|
| Skill 载体 | Static/Showcase 用 B；Flow App 用 C | B: prompt + 组件片段；C: prompt + 组件片段 + 数据结构/状态定义 |
| Orchestrator | 先分类再生成 | 先判断产品类型/复杂度，再选择 skill、文档级别、模型路由 |
| 多模型路由 | 轻/中/重分工 | 轻模型: 分类/验证；重模型: 主生成；中模型: 扩展/修正 |
| 模型来源 | 仅 OpenAI Compatible | 仅配置 model/base_url/key 的兼容通道 |
| 路由策略 | 稳定性优先 | 默认最稳模型，按规则回退 |
| 风格参考 | 默认整体复刻 | 支持图片参考，包含布局复刻 |
| 页面指定 | 支持 @Page | 无 @ 时由模型决定作用范围 |
| 产品文档 | 分级输出 | 简单输出清单；中等输出完整文档；复杂可含 mermaid/多文档 |
| 生成形态 | 纯 HTML 多页面 | 不引入 SPA/router，先以共享脚本 + localStorage 实现跨页数据传递 |
| 数据持久化 | localStorage | 会话内 + 刷新可恢复，MVP 不引入后端存储 |
| 记录范围 | 预约/表单提交 + 电商订单记录 | 覆盖优先支持的 flow 场景 |
| Data Tab | 仅预览侧可见 | 不生成 app 内管理页，仅在 Preview 面板展示 |

---

## 目录

1. [版本概述](#1-版本概述)
2. [范围与原则](#2-范围与原则)
3. [架构设计](#3-架构设计)
4. [数据模型](#4-数据模型)
5. [Orchestrator 路由规则](#5-orchestrator-路由规则)
6. [多模型路由](#6-多模型路由)
7. [产品文档分级](#7-产品文档分级)
8. [风格参考](#8-风格参考)
9. [数据传递协议](#9-数据传递协议)
10. [API 与前端设计](#10-api-与前端设计)
11. [迁移与实施拆分](#11-迁移与实施拆分)
12. [文件变更清单](#12-文件变更清单)
13. [验收标准](#13-验收标准)

---

## 1. 版本概述

### 1.1 版本定位

**Spec v0.6** 在 v0.5 的版本稳定基础上，新增“生成策略层”，并补齐跨页面数据传递：

1. **Skills 生成策略** — 通过 manifest 描述适用场景、组件一致性、数据契约与生成规则
2. **Orchestrator 路由** — 先判断“做什么”，再决定“怎么做”（skill/文档/模型）
3. **多模型分工** — 轻模型分类/验证，重模型主生成，中模型扩展修正
4. **产品文档分级** — 依据复杂度输出清单/文档/附图
5. **跨页面数据传递** — 共享状态协议 + 本地持久化 + Preview Data Tab
6. **风格参考** — 支持图片参考并默认整体复刻（包含布局）
7. **移动端约束** — 默认强移动端 guardrails（触控/字号/对比度）

### 1.2 与 v0.5 的关系

| v0.5 (现有) | v0.6 (本版本) |
|-------------|--------------|
| 统一版本管理与 Responses API | 保持不变 |
| 多页面生成 | 增加“跨页面状态协议”与 Data Tab |
| 单一生成策略 | 引入 Skills 与 Orchestrator 路由 |
| 单一模型 | 多模型路由 |
| 产品文档固定结构 | 文档分级与结构化输出 |
| 无风格参考 | 新增图片风格参考与布局复刻 |

### 1.3 设计原则

1. **先理解再生成**：生成前必须完成产品类型与复杂度判断。
2. **一致性优先**：Flow App 通过共享组件与状态契约保证跨页一致性。
3. **最小可跑**：MVP 不引入后端存储与管理页。
4. **结构可复用**：文档输出必须包含结构化字段，便于后续代理扩展。
5. **可诊断**：路由决策、模型选择、技能版本必须可追踪。
6. **策略内置**：Skills/Profiles/Guardrails 仅服务端可见，不对用户暴露或可编辑。

---

## 2. 范围与原则

### 2.1 范围

**包含**:
- Skills registry + manifest 定义
- Orchestrator 路由流程（分类/复杂度/技能/文档/模型）
- 多模型路由策略与配置
- 产品文档分级输出（清单/文档/附图）
- 图片风格参考（默认整体复刻）
- Style profiles 风格档案与路由
- 移动端 guardrails（硬性/软性约束）
- @Page 页面指定（无 @ 时由模型判断作用范围）
- 跨页面数据传递协议（state + events + records）
- Preview Data Tab（State/Events/Records）

**不包含**:
- 后端持久化的数据记录（MVP 仅 localStorage）
- App 内管理页生成（Data Tab 仅预览侧）
- 全量多语言与自由风格支持（先支持有限风格）

### 2.2 MVP 覆盖的产品类型

- Flow App: 电商 / 预约 / 仪表盘
- Static/Showcase: Landing Page / 贺卡 / 邀请函
- MVP 覆盖上述枚举类型；仪表盘仅保证基础卡片/列表视图（复杂图表与实时数据不在 MVP 范围）。

---

## 3. 架构设计

### 3.1 Orchestrator 路由流程

```
用户输入
  ↓
解析 @Page / 图片参考 / 生成/重生成范围
  ↓
产品类型识别 (product_type)
  ↓
复杂度评估 (complexity)
  ↓
选择 skill + 文档级别 + 模型路由
  ↓
风格偏好路由 (style profile)
  ↓
注入移动端 guardrails
  ↓
风格参考提取 (style tokens)
  ↓
生成 Product Doc (结构化 + Markdown)
  ↓
生成共享组件/状态契约 (Flow App)
  ↓
生成页面 HTML (多页)
  ↓
输出预览 + Data Tab
```

### 3.2 Skills 生成策略

- 每个 skill 描述适用的产品类型与规则。
- Flow App skill 必须提供：
  - 共享组件片段（卡片/列表/表单/汇总）
  - 状态契约模板（state schema + actions）
  - 交互约束（如购物车更新规则）
- 每个 skill 额外包含：
  - 可用风格档案（style profiles）
  - 移动端 guardrails（硬性/软性）
  - 页面角色（page roles）与优先级

### 3.3 组件一致性

- 共享组件在生成前“预生成”并注册到上下文。
- 页面生成必须复用共享组件的结构与样式 token。

### 3.4 数据传递

- Flow App 统一注入 `data-store.js` 与 `data-client.js`。
- 页面间以 localStorage 作为共享存储。
- 事件驱动更新 records（预约/订单提交记录）。

### 3.5 Preview Data Tab

- Preview Panel 内新增 Data Tab。
- 数据来源：预览 iframe 通过 `postMessage` 向父窗口上报 state/events/records。
- Data Tab 展示实时 JSON，支持导出。

### 3.6 风格参考（图片）

- 用户可上传 1-3 张参考图（UI 截图/设计图）。
- 默认整体复刻（包含布局节奏与组件形态）。
- 如消息包含 @Page，则仅对指定页面生效（风格参考 + 生成/重生成范围）；无 @ 时由模型判断作用范围（风格参考 + 生成/重生成范围）。

---

## 4. 数据模型

### 4.1 SkillManifest（示意）

```json
{
  "id": "flow-ecommerce-v1",
  "name": "Flow App - ECommerce",
  "version": "1.0.0",
  "product_types": ["ecommerce"],
  "doc_tiers": ["checklist", "standard", "extended"],
  "components": ["CartItem", "ProductCard", "OrderSummary"],
  "state_contract": "contracts/ecommerce.json",
  "style_profiles": ["clean-modern", "soft-elegant", "bold-tech"],
  "guardrails": "rules/mobile-guardrails.json",
  "page_roles": ["catalog", "cart", "checkout"],
  "model_prefs": {
    "classifier": "light",
    "writer": "heavy",
    "validator": "light",
    "expander": "mid"
  },
  "priority": 100
}
```

Manifest 路径与 state_contract：
- manifest 目录建议为 `packages/backend/app/services/skills/manifests/`
- `state_contract` 为相对 manifest 目录的静态模板路径（如 `contracts/ecommerce.json`）
- 若模板缺失，可由 LLM 生成并输出到 `<output_dir>/shared/state-contract.json`（不回写为模板）
 - `guardrails` 为相对技能目录的规则文件路径（如 `rules/mobile-guardrails.json`）
 - `style_profiles` 为可用风格档案 ID 列表（由 style router 选择）

**复杂度字段约定（统一口径）**：
- 路由与会话内 `complexity` 统一使用：`simple | medium | complex`。
- Skill manifest 中如出现 `complexity` 字段，需按以下兼容映射规范化：
  - `checklist` → `simple`
  - `standard` → `medium`
  - `extended` → `complex`

### 4.2 ProductDocStructured（新增字段）

```json
{
  "product_type": "ecommerce",
  "complexity": "medium",
  "doc_tier": "standard",
  "pages": [
    {"slug": "home", "role": "catalog"},
    {"slug": "cart", "role": "checkout"}
  ],
  "state_contract": {
    "shared_state_key": "instant-coffee:state",
    "records_key": "instant-coffee:records",
    "schema": {}
  },
  "data_flow": [
    {"from": "home", "event": "add_to_cart", "to": "cart"}
  ],
  "style_reference": {
    "mode": "full_mimic",
    "scope": {"type": "model_decide", "pages": []},
    "images": ["asset:style_ref_1"]
  }
}
```

### 4.3 SharedState（最小结构）

SharedState 仅保存草稿/未提交状态（UI 可变状态）。

```json
{
  "cart": {
    "items": [],
    "totals": {"subtotal": 0, "tax": 0, "total": 0},
    "currency": "USD"
  },
  "booking": {
    "draft": {}
  },
  "forms": {
    "draft": {}
  },
  "user": {
    "profile": {}
  }
}
```

### 4.4 Records（示意）

```json
{
  "records": [
    {"type": "booking_submitted", "payload": {}, "created_at": "2026-02-03T12:00:00Z"},
    {"type": "order_submitted", "payload": {}, "created_at": "2026-02-03T12:00:00Z"},
    {"type": "form_submission", "payload": {}, "created_at": "2026-02-03T12:00:00Z"}
  ]
}
```

### 4.5 StyleReference（示意）

```json
{
  "mode": "full_mimic",
  "scope": {
    "type": "model_decide",
    "pages": []
  },
  "images": [
    {"id": "style_ref_1", "source": "upload", "page_hint": "home"}
  ],
  "tokens": {
    "colors": {"primary": "#111111", "accent": "#2F6BFF", "bg": "#F7F7F7"},
    "typography": {"family": "sans", "scale": "large-title"},
    "radius": "medium",
    "shadow": "soft",
    "spacing": "airy",
    "layout_patterns": ["hero-left", "card-grid"]
  }
}
```

### 4.6 Style Profiles（示意）

```json
{
  "profiles": {
    "clean-modern": {
      "name": "Clean Modern",
      "description": "Neutral, airy, product-focused.",
      "tokens": {
        "colors": {"primary": "#1A1F2B", "accent": "#2F6BFF", "bg": "#F8FAFC"},
        "typography": {"heading": {"family": "Space Grotesk"}, "body": {"family": "DM Sans"}},
        "radius": "medium",
        "shadow": "soft",
        "spacing": "airy",
        "layout_patterns": ["hero-left", "card-grid"]
      }
    }
  }
}
```

### 4.7 Mobile Guardrails（示意）

```json
{
  "hard": [
    {"id": "touch-target-size", "title": "Touch target size", "priority": "critical"},
    {"id": "readable-font-size", "title": "Readable base size", "priority": "critical"},
    {"id": "color-contrast", "title": "Text contrast", "priority": "critical"}
  ],
  "soft": [
    {"id": "line-height", "title": "Comfortable line height", "priority": "medium"},
    {"id": "loading-states", "title": "Loading feedback", "priority": "medium"}
  ]
}
```

---

## 5. Orchestrator 路由规则

### 5.1 产品类型识别

输出枚举：
- ecommerce / booking / dashboard / landing / card / invitation

### 5.2 目标页面解析（@Page）

- 解析用户输入中的 `@Page` 标记（如 `@Home`）。
- 若存在 @Page，作用范围限定为指定页面集合（**风格参考 + 生成/重生成范围**）。
- 若不存在 @Page，**由模型判断**风格参考与生成/重生成范围（全局或局部）。

### 5.3 复杂度评估

评估维度：
- 页面数量
- 是否含跨页数据流
- 是否含表单或多步骤流程
- 数据结构复杂度

输出：
- simple / medium / complex

**兼容映射规则（用于 skill manifests 或旧数据）**：
- `checklist` → `simple`
- `standard` → `medium`
- `extended` → `complex`

### 5.4 路由伪代码

```
targets = resolve_targets(user_input)
route = classify(user_input)
complexity = evaluate(user_input, route)
skill = select_skill(route, complexity)
doc_tier = select_doc_tier(complexity, route)
model_route = select_models(route, complexity)
style_profile = route_style_profile(user_input)
guardrails = load_guardrails(skill)
style_ref = extract_style_reference(user_input, targets, model_route)
```

---

## 6. 多模型路由

### 6.1 模型角色

- **Classifier (light)**: 产品类型识别、复杂度评估
- **Writer (heavy)**: 主文档与页面生成
- **Expander (mid)**: 多页面扩展、细化组件
- **Validator (light)**: 合规检查与结构修正
- **Style Refiner (mid/heavy)**: 审美统一、排版与视觉质感提升

### 6.2 配置方式

建议在后端 config 中新增：
- `MODEL_CLASSIFIER`
- `MODEL_WRITER`
- `MODEL_EXPANDER`
- `MODEL_VALIDATOR`
- `MODEL_STYLE_REFINER`

### 6.3 模型来源与兼容

- 仅支持 **OpenAI Compatible** 的调用通道。
- 通过 `model` / `base_url` / `api_key` 配置切换供应商，不引入多 SDK。
- 仅 Style Refiner 需要 **支持图像输入** 的模型（用于风格提取与布局复刻）。
- Writer/Expander/Classifier 默认只接收文本形式的 style tokens。
- 若无可用图像模型，`style_reference.mode` 降级为 `style_only` 并记录 warning。

### 6.4 路由策略（稳定性优先）

- 默认选择 **最稳模型** 作为 Writer 与 Validator。
- 当出现失败或结构缺失时，按优先级回退到池内下一模型。
- Landing/Card 走“审美优先”路线：Writer 可轻，Style Refiner 必须强。
- 有图片参考时，Style Refiner 先输出风格 token，再参与页面生成或重写。

### 6.5 模型池与动态切换

```yaml
model_pools:
  classifier: [classifier_a, classifier_b]
  writer:
    default: [writer_stable, writer_backup]
    landing: [writer_fast, writer_stable]
    card: [writer_fast, writer_stable]
    ecommerce: [writer_stable, writer_backup]
    booking: [writer_stable, writer_backup]
    dashboard: [writer_stable, writer_backup]
  expander: [expander_mid, writer_stable]
  validator: [validator_stable, validator_backup]
  style_refiner:
    landing: [refiner_aesthetic, refiner_backup]
    card: [refiner_aesthetic, refiner_backup]
```

**回退触发条件**（任一满足则切换到池内下一模型）：
- 超时或请求失败
- Validator 标记 hard-fail（结构/约束不满足）
- 关键字段缺失（如 `state_contract` / `data_flow` / HTML 不完整）

### 6.6 Validator 判定标准（hard/soft）

**hard-fail（必须重试或回退）**：
- HTML 不完整或无法渲染（缺少 `</html>` / 主体为空）
- Flow App 缺 `state_contract` 或 `data_flow`
- 多页面缺少关键页面（如电商无 cart/checkout）
- 结构化字段解析失败（JSON 结构错误）

**soft-fail（可放行但触发优化）**：
- 风格/排版弱（不满足审美阈值）
- 组件一致性轻微偏差（样式 token 不统一）
- 文档完整但表达冗余或轻微缺漏

### 6.7 Landing/Card 审美评分规则

**评分维度（每项 1-5，合计 25）**：
1) 字体层级清晰度（标题/正文/CTA）
2) 对比度与可读性
3) 版式平衡与留白节奏
4) 色彩和谐度
5) CTA 聚焦与视觉引导

**阈值**：
- MVP 阈值：>= 18/25
- 低于阈值进入 Style Refiner 重写流程（最多两次）

**重写流程（最多两次）**：
- 若初始评分低于阈值，进入 Refiner 第 1 次。
- 若第 1 次评分低于初始评分，停止并保留初始版本。
- 若第 1 次评分仍低于阈值，可进入 Refiner 第 2 次。
- 第 2 次结束后停止；若第 2 次评分低于第 1 次，保留第 1 次版本。

**规则校验（自动）**：
- 最低对比度要求（WCAG 4.5:1）
- 行高范围 1.4-1.8
- 标题/正文/CTA 字号差异明显

### 6.8 审美评分轻模型 Prompt（草案）

```
你是视觉设计评审。请根据以下 5 个维度为页面打分（1-5 分）并给出总分：
1) 字体层级清晰度（标题/正文/CTA）
2) 对比度与可读性
3) 版式平衡与留白节奏
4) 色彩和谐度
5) CTA 聚焦与视觉引导
输出 JSON:
{
  "scores": {"typography": 0, "contrast": 0, "layout": 0, "color": 0, "cta": 0},
  "total": 0,
  "issues": ["问题1", "问题2"],
  "auto_checks": {
    "wcag_contrast": "pass/fail",
    "line_height": "pass/fail",
    "type_scale": "pass/fail"
  }
}
```

### 6.9 Expander 触发阈值（Flow App）

触发条件（任一满足）：
- 页面数 > 1
- 产品类型为 ecommerce / booking / dashboard
- `state_contract` 字段存在且包含 `cart` 或 `draft`
- 页面内表单数 >= 1
- 组件数量 >= 6（按 card/list/form/summary 计）

**职责边界（示意）**：
- Writer 负责主流程页面与核心结构。
- Expander 负责次要页面扩展或组件细化。

| 场景 | 主生成模型 | 是否触发 Expander |
|------|------------|-------------------|
| 单页 Landing | Writer | 否 |
| 单页电商产品页 | Writer | 是（含表单/组件>=6） |
| 多页电商（2页） | Writer | 是 |
| 多页电商（5页） | Writer | 是（Expander 负责次要页） |

---

## 7. 产品文档分级

### 7.1 分级规则

- **Checklist**: 简单展示型（landing/card/invitation）
- **Standard**: 中等复杂度 Flow App
- **Extended**: 复杂 Flow App，包含 mermaid 流程图与多文档拆分

### 7.2 最小输出要求

- Checklist: 目标 + 核心要点 + 关键约束
- Standard: 目标/用户/页面结构 + 数据流说明 + 组件一致性规则
- Extended: Standard + Mermaid + 数据结构清单 + 多文档索引

---

## 8. 风格参考

### 8.1 输入与模式

- 支持 1-3 张图片作为风格参考（UI 截图/设计图）。
- 默认模式：`full_mimic`（整体复刻，包含布局节奏与组件形态）。
- 可选模式：`style_only`（仅颜色/字体/质感，不复刻布局）。
- 若无图片参考，使用 style profile tokens 作为基础风格。

### 8.2 作用范围

- 若消息包含 `@Page`：仅对指定页面生效（风格参考 + 生成/重生成范围）。
- 无 `@Page`：由模型判断风格参考与生成/重生成范围（全局或局部）。

### 8.3 风格提取与布局复刻

输出风格 token：
- 颜色体系（主色/强调/背景）
- 字体风格（族系/层级/字重）
- 圆角/阴影/边框倾向
- 间距密度（紧凑/宽松）
- 布局模式（hero、card grid、split 等）

在 `full_mimic` 下：
- 推导布局节奏与组件形态，应用于目标页面结构。

### 8.4 注入策略

- 风格 token 写入 `global_style` / `design_direction`。
- 目标页面生成时强制使用 token 与布局模式。
- Style Refiner 可对生成结果进行风格重写（最多两次）。
- 风格参考 token 与 style profile 冲突时，以风格参考为主，未覆盖字段回退到 profile。

---

## 9. 数据传递协议

### 9.1 存储

- Shared state key: `instant-coffee:state`
- Records key: `instant-coffee:records`
- Events key: `instant-coffee:events`
- SharedState 保存草稿/未提交状态；Records 保存已提交结果（不可变）。
- 采用 localStorage，刷新后仍可恢复

### 9.2 事件与动作

最低支持事件：
- `add_to_cart`, `update_qty`, `remove_item`, `checkout_draft`
- `submit_booking`, `submit_form`, `clear_cart`

提交类事件（`submit_*`）触发时：
- 将当前草稿快照写入 `records_key`
- 可选：清空或保留草稿（由产品类型决定）

**事件触发与状态更新伪代码（示意）**：
```
on_add_to_cart(product, qty):
  state.cart.items.append({product, qty})
  state.cart.totals.subtotal += product.price * qty
  events.log("add_to_cart", {product_id: product.id, qty})
  persist_state()
  notify_preview_update(debounced)

on_submit_booking(payload):
  records.append({type: "booking_submitted", payload, created_at: now()})
  events.log("submit_booking", {booking_id: payload.id})
  persist_records()
  notify_preview_update(immediate)
```

### 9.3 预览与 Data Tab

- 预览 iframe 在事件触发后推送最新 state/records/events。
- Data Tab 展示：
  - State (JSON)
  - Events (列表)
  - Records (预约/订单/表单提交记录)

### 9.4 多页面同步时机

- 同页更新：写入 localStorage 后立即更新本页内存 state。
- 跨页同步：监听 `storage` 事件，触发后拉取最新 state/records/events。
- 预览推送：
  - `update_*` 事件：300-500ms debounce 推送
  - `submit_*` 事件：立即推送

---

## 10. API 与前端设计

### 10.1 前端

- Preview Panel 增加 Data Tab。
- Data Tab 通过 `postMessage` 接收 iframe 数据。
- 提供“导出 JSON”按钮。
- Chat Input 支持图片拖拽与本地文件选择（1-3 张）。
- 支持 `@Page` 提示与选择（输入 `@` 弹出页面列表），用于限制风格参考与生成/重生成范围。
- （可选）事件面板/调试区展示 `aesthetic_score` 评分与重写尝试。

### 10.2 后端

- MVP 不新增后端存储表。
- Orchestrator 记录路由决策（可写入日志或 session metadata）。
- 支持接收图片附件并传递给风格提取模型。
- 无 `@Page` 时由模型决定风格参考与生成/重生成范围。

### 10.3 Aesthetic Scoring (B7)

**目标**：为 Landing/Card/Invitation 页面提供审美评分、自动检查与阈值重写策略。

**评分维度**（每项 1-5 分，总分 5-25）：
- typography / contrast / layout / color / cta

**自动检查**：
- WCAG 对比度 ≥ 4.5:1
- body line-height 1.4-1.8
- title/body/CTA 字号层级差异

**阈值与重写策略**：
- 阈值：18/25
- 低于阈值触发 Style Refiner，最多 2 次
- 只保留评分更高的版本，禁止降级

**SSE 事件**：
- `aesthetic_score`：包含 `page_id`、score、attempts（每次尝试的总分与结论）

---

## 11. 迁移与实施拆分

### M1: Skill Registry + 路由骨架

1) 定义 SkillManifest 与 registry 读取。
2) Orchestrator 路由流程接入。
3) 初始技能：Flow App (电商/预约/仪表盘) + Static Showcase。

### M2: 文档分级与结构化输出

1) 输出 doc_tier 与 data_flow 字段。
2) Checklist/Standard 模板落地。

### M3: 风格参考 + @Page

1) Chat Input 支持图片上传与 @Page。
2) 风格参考解析与 token 输出。
3) 生成时注入风格 token 与布局模式。

### M4: 数据协议与 Data Tab

1) 生成共享脚本 `data-store.js` 与 state contract。
2) 页面统一注入 data client。
3) Preview Data Tab 可展示 state/records/events。

### M5: 多模型路由

1) 模型角色配置。
2) 分类/验证切换至轻模型。
3) 生成使用重模型，扩展使用中模型。
4) Aesthetic Scoring + Style Refiner 阈值重写。

---

## 12. 文件变更清单

### Backend

| 文件 | 变更 |
|------|------|
| `app/agents/orchestrator/*` | 接入路由逻辑与 skill 选择 |
| `app/services/product_doc.py` | 文档分级与结构化输出 |
| `app/services/skills.py` | **新增** registry 与 manifest 解析 |
| `app/services/style_reference.py` | **新增** 风格提取与 token 输出 |
| `app/api/chat.py` | 接收图片附件与 @Page 信息 |
| `app/config.py` | 新增多模型配置 |
| `app/schemas/validation.py` | **新增** 审美评分 schema |
| `app/utils/validation.py` | **新增** 自动检查（对比度/行高/字号层级） |
| `app/agents/aesthetic_scorer.py` | **新增** 审美评分 agent |
| `app/agents/style_refiner.py` | **新增** 风格重写 agent |
| `app/agents/validator.py` | **新增** 阈值重写与评分对比逻辑 |
| `app/events/types.py` | **新增** `aesthetic_score` 事件类型 |
| `app/events/models.py` | **新增** `AestheticScoreEvent` |
| `app/executor/task_executor.py` | 接入评分与重写流程 |

### Web

| 文件 | 变更 |
|------|------|
| `src/components/custom/PreviewPanel.tsx` | 增加 Data Tab |
| `src/components/custom/DataTab.tsx` | **新增** Data Tab UI |
| `src/components/custom/ChatInput.tsx` | 支持图片上传与 @Page |
| `src/components/custom/PageMention.tsx` | **新增** 页面选择弹层 |
| `src/hooks/usePreviewBridge.ts` | **新增** iframe 数据桥接 |
| `src/types/events.ts` | **新增** `aesthetic_score` 事件类型 |

### Output (Generated)

| 文件 | 变更 |
|------|------|
| `output/shared/data-store.js` | **新增** state store |
| `output/shared/data-client.js` | **新增** 页面数据 client |
| `output/shared/state-contract.json` | **新增** 数据协议 |

---

## 13. 验收标准

1. Orchestrator 在生成前完成类型与复杂度判断。
2. Flow App 必须输出 state_contract 与 data_flow。
3. 生成页面在跨页时能共享 cart/booking 数据。
4. 刷新后数据仍可恢复（localStorage）。
5. Preview Data Tab 可展示 state/events/records。
6. Checklist/Standard 两种文档输出可用，Extended 保留接口。
7. 模型路由生效：分类/验证走轻模型，生成走重模型。
8. 上传图片后可生成风格 token 并影响页面输出。
9. 默认整体复刻（包含布局节奏与组件形态）。
10. `@Page` 可限定风格参考与生成/重生成范围；无 `@Page` 时由模型判断作用范围。
11. Landing/Card 在低审美评分时进入 Style Refiner 重写流程（最多两次）。
12. 自动检查（对比度/行高/字号层级）返回结构化结果。
13. `aesthetic_score` SSE 事件可被前端消费与记录。
14. 默认强移动端 guardrails 生效（字号/触控/对比度）。

**阶段对应**：
- M1: 1, 2, 14
- M2: 6
- M3: 8, 9, 10
- M4: 3, 4, 5
- M5: 7, 11, 12, 13
