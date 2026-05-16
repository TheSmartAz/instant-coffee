# 前端布局重构计划

> 最后更新: 2026-05-16

## 目标

重构 Instant Coffee 所有页面的前端布局和视觉风格，建立统一的设计系统，提升用户体验和代码可维护性。

**设计方向**: Notion 风格简约美学 — 干净的白底、克制的色彩、清晰的层级、内容优先。

**不在此次重构范围内**: Dark Mode 支持（后续独立迭代）。

**实施原则**:
- 先建立设计 token，再改页面和组件，避免页面先写一轮新样式后再返工。
- 不做功能性删除。低频功能先降级到 Drawer、More 菜单或高级设置，确认无依赖后再单独清理。
- ProjectPage 拆成布局壳重构和功能迁移两步，每步都保持 chat、preview、build、page selection、version、data 等现有路径可回归。
- Drawer、响应式和版本迁移必须有可访问性与回归测试验收，不能只以视觉效果完成为准。

## 当前实施状态

> 更新于 2026-05-16。本节记录当前已落地内容，后续阶段以这里作为最新基线。

### 已完成

- Phase 1 设计系统基础: 已新增字体、圆角、阴影、动画、z-index 和 success/warning/info/danger 语义色 token，并接入 Tailwind theme。
- Phase 2 HomePage: 已重做首页信息架构，保留 pinned/search/sort/manage/delete 项目管理能力，并接入 `AppLayout` / `ContentArea`。
- Phase 3 ProjectPage 布局壳: 已迁移为共享 `AppLayout` / `PageHeader` / `ContentArea`，主工作区接入 `ResizableSplitPane`，并保留 Chat、Preview、Build、Page selection、AppMode、Data tab、Version history。
- Phase 4 Drawer 功能迁移: 已新增 Radix Dialog 驱动的 `Drawer` 基础组件，并接入 `CodeDrawer`、`DocDrawer`、`DataDrawer`、`VersionDrawer` 入口。ProjectPage 的 `RunDetailsDrawer` / `RunInspector` 已移除，不应再作为 chat 输入框附近的高级入口恢复。
- Phase 5 布局架构抽象: 已新增 `AppLayout`、`PageHeader`、`ContentArea`，并迁移 HomePage、ProjectPage、SettingsPage、ExecutionPage。
- Phase 6 视觉统一: 已完成高可见状态组件的语义色 token 收敛，简化 PhoneFrame，并统一多处状态、diff、token、文件树、任务和运行观测颜色。
- 性能收敛: `ProjectPage` 已对 Workbench、VersionPanel、Code/Doc/Data drawer 做 `React.lazy` 分包，生产 chunk 从约 554 kB 降至约 398 kB，Vite 大 chunk 警告消失。
- 回归测试: 已新增 `ProjectDrawers.spec.ts` 覆盖 Code / Product Doc / Data / Versions drawer header 入口，并保持 Data tab、Preview bridge、轻量 run status e2e 通过。

### 剩余事项

- 做一次人工视觉验收，重点检查桌面/移动端 ProjectPage header、split pane 比例、Version drawer 内容高度、Drawer 内容滚动和焦点恢复。
- 评估是否继续把 `VersionPanel` 行为拆成独立 hook/service；当前 `VersionDrawer` 复用原面板行为，降低交互回归风险。
- `RunDetailsDrawer` / `RunInspector` 已移除；继续只保留轻量 `RunStatusStrip`，不要恢复 Run details 按钮、抽屉或侧边栏。
- 可选处理 shadcn `toast.tsx` destructive group 默认红色类；这属于组件库默认样式，不影响当前业务语义色收敛。
- 后续如继续瘦身，可拆 `client` 公共 chunk 或对 CodePanel/editor 相关依赖做更细粒度懒加载。

---

## 当前问题诊断

### 视觉层面

| 问题 | 描述 |
|---|---|
| 品牌色缺失 | 当前使用 shadcn 默认 zinc 色板 + 蓝色 accent，无产品辨识度 |
| 颜色硬编码 | 状态组件直接使用 `blue-50`, `emerald-200`, `amber-900` 等 Tailwind 原始色，绕过 CSS 变量 |
| 风格不统一 | ProjectCard、ChatMessage、VersionPanel 等组件视觉语言不一致 |
| 空状态简陋 | 仅文字提示，缺少引导性设计 |
| Logo 设计陈旧 | 当前 Logo 与产品调性不匹配，需要重新设计 |

### 布局层面

| 问题 | 描述 |
|---|---|
| 面板比例写死 | ChatPanel 固定 `w-[35%]`，不可调整 |
| 无响应式适配 | 所有布局仅针对桌面端，小屏幕完全不可用 |
| 布局代码重复 | 各页面 header/wrapper 结构各自实现，无抽象 |
| 折叠动画简陋 | VersionPanel 仅宽度切换，无内容过渡 |

### 设计系统层面

| 问题 | 描述 |
|---|---|
| 字体未注册 | Inter 仅 CSS @import，未在 Tailwind theme 中配置 |
| 圆角不一致 | Card 用 `rounded-xl`，Button 用 `rounded-md`，混用别名和原始值 |
| 阴影体系缺失 | 仅 1 个自定义 shadow，其余用 Tailwind 默认或 inline arbitrary |
| 无语义色变量 | 缺少 success/warning/info 等语义色 CSS 变量 |
| 无 z-index 规范 | z-index 随意使用，无层级定义 |

---

## 重构方案

### HomePage 重新设计（实施 Phase 2）

将 HomePage 从当前的"搜索框 + 项目网格"模式，升级为更具产品感的落地页式首页。

> 顺序调整: 主页重设计依赖 Phase 1 的 token 和基础组件规范。实际实施时先完成 Phase 1，再执行本阶段。

#### 新主页布局结构

```
┌─────────────────────────────────────────────────────────────────┐
│  Header (Logo + Settings)                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                         │   │
│  │         Instant Coffee                                  │   │
│  │         Build mobile pages with a chat.                 │   │
│  │                                                         │   │
│  │    ┌──────────────────────────────────────┐             │   │
│  │    │  Describe what you want to build...   │ [Create]   │   │
│  │    └──────────────────────────────────────┘             │   │
│  │                                                         │   │
│  │    [Recent projects →]                                  │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Quick Start                                                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ 🎨 Landing   │ │ 📋 Form      │ │ 🛒 Product   │           │
│  │   Page       │ │   Builder    │ │   Catalog    │           │
│  │   Build a    │ │   Collect    │ │   Showcase   │           │
│  │   beautiful  │ │   user data  │ │   your items │           │
│  │   one-pager  │ │   in minutes │ │   beautifully│           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Recent Projects                                    [View All]  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │ Project  │ │ Project  │ │ Project  │ │ Project  │         │
│  │ Card     │ │ Card     │ │ Card     │ │ Card     │         │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
│                                                                 │
│  (空状态时显示:                                               │
│   ┌─────────────────────────────────────────────┐              │
│   │  ☕                                           │              │
│   │  No projects yet.                            │              │
│   │  Start by describing your first mobile page  │              │
│   │  above.                                      │              │
│   └─────────────────────────────────────────────┘)              │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Footer: Version · Docs · GitHub                                │
└─────────────────────────────────────────────────────────────────┘
```

#### 主页各区域设计说明

**Hero 区域**:
- 居中布局，最大宽度 max-w-2xl
- 标题 "Instant Coffee" 使用大号字体 (text-4xl font-semibold)
- 副标题 "Build mobile pages with a chat." 使用 muted-foreground (text-lg)
- 输入框: 大尺寸 (h-12)，带品牌色 focus ring，placeholder 文字更友好
- Create 按钮: 品牌色背景，右侧箭头图标
- 底部 "Recent projects" 链接: 快速跳转到最近项目

**Quick Start 区域**:
- 3 列卡片网格，每个卡片代表一个使用场景模板
- 卡片风格: 无边框、hover 时轻微背景色变化 (Notion 风格)
- 点击卡片自动填充输入框并触发创建
- 卡片图标使用简洁 emoji 或 lucide 图标

**Recent Projects 区域**:
- 标题 + "View All" 链接
- 项目卡片横向滚动（小屏幕）或 4 列网格（大屏幕）
- 卡片简化: 仅显示项目名、更新时间、页面数
- 点击卡片进入项目
- 保留当前项目管理能力: pinned projects、search、sort、manage、delete
- 置顶项目作为 Recent Projects 上方的独立分组展示，避免重设计后丢失管理功能

**空状态**:
- 居中咖啡杯图标 (lucide Coffee 或自定义 SVG)
- 简洁引导文字
- 无多余装饰

#### 主页交互细节

- 输入框聚焦时: 品牌色 ring + 轻微阴影扩散
- Create 按钮 hover: 品牌色加深 + translateY(-1px)
- Quick Start 卡片 hover: 背景色从 transparent → muted/30
- 项目卡片 hover: 背景色变化 + 轻微右移箭头提示
- 页面加载: Hero 区域 fade-in + slide-up，Quick Start 依次 stagger 动画

#### Logo 重新设计

当前 Logo 需要更新为更符合 Notion 风格简约美学的版本：

**方案 A: 文字 Logo**
```
IC  Instant Coffee
```
- "IC" 字母组合作为图标，使用品牌色
- "Instant Coffee" 作为文字标识，使用 Inter 字体
- 整体简洁，适合 Header 导航栏

**方案 B: 咖啡杯图标 + 文字**
```
☕  Instant Coffee
```
- 简洁线条风格的咖啡杯 SVG 图标
- 配合 "Instant Coffee" 文字
- 图标使用品牌色填充

**建议**: 采用方案 A，更符合 Notion 风格的克制美学。

---

### ProjectPage 重新设计（实施 Phase 3-4）

#### 当前问题分析

ProjectPage 当前采用三栏布局（Chat 35% | Workbench | VersionPanel 320px），存在以下问题：

| 问题 | 描述 |
|---|---|
| 信息密度过高 | 三个面板同时展示，视觉拥挤，注意力分散 |
| Tab 嵌套过深 | Workbench 有 4 个 tab，VersionPanel 内容又随 Workbench tab 变化，认知负担重 |
| 功能冗余 | RunStatusStrip + TokenDisplay 挤在 ChatPanel 底部，debug 感过重；RunInspector 已移除 |
| PhoneFrame 过重 | 黑色手机外框在 Notion 风格下显得突兀 |
| VersionPanel 复杂度过高 | 808 行代码，包含 pin/unpin/preview/rollback/diff 等多重 dialog，使用频率低但占据固定空间 |
| Code/Product Doc/Data tab | 这些内容更适合在需要时展开，而非始终占据 tab 位 |

#### 功能取舍分析

| 功能 | 当前状态 | 是否保留 | 理由 |
|---|---|---|---|
| **Chat** | 左侧面板 | ✅ 保留 | 核心交互方式 |
| **Preview (PhoneFrame)** | Workbench tab 之一 | ✅ 保留+升级 | 核心价值展示，应始终可见 |
| **ThreadSelector** | ChatPanel 顶部 | ✅ 保留 | 多对话分支需要 |
| **AbortDialog** | ChatPanel 顶部 | ✅ 保留 | 长任务需要中断能力 |
| **Pages 选择器** | PreviewPanel 内 | ✅ 保留 | 多页面项目需要 |
| **PreviewMode (Live/Build)** | PreviewPanel 内 | ✅ 保留 | 两种预览模式有实际用途 |
| **AppMode/StaticMode** | PreviewPanel 内 | ⚠️ 降级 | 高级功能，放到设置或隐藏 |
| **AestheticScore** | PreviewPanel 底部 | ⚠️ 降级 | 非核心，折叠或移除 |
| **Code tab** | Workbench tab | ⚠️ 移至 drawer | 开发者偶尔需要，不应占主空间 |
| **Product Doc tab** | Workbench tab | ⚠️ 移至 drawer | 重要但非实时查看，chat 中已有卡片 |
| **Data tab** | Workbench tab | ⚠️ 移至高级入口 | 现有 e2e 覆盖，不直接删除；移到 More/Advanced Drawer 或隐藏入口 |
| **VersionPanel** | 右侧固定面板 | ⚠️ 改为 drawer | 版本历史低频操作，不应占固定空间 |
| **RunStatusStrip** | ChatPanel 底部 | ✅ 保留 | 只显示轻量状态，不提供详情入口 |
| **RunInspector** | ChatPanel 底部 | ✅ 移除 | 不恢复 ProjectPage Run details 抽屉/侧边栏 |
| **TokenDisplay** | ChatPanel 底部 | ⚠️ 简化 | 保留但极简显示 |
| **Execution Flow 入口** | Header 图标 | ✅ 保留 | 需要时查看详细执行 |
| **Build 状态/操作** | PreviewPanel 顶部 | ✅ 保留 | 与预览直接相关 |
| **Export** | PreviewPanel 顶部 | ✅ 保留 | 核心导出功能 |
| **Refresh** | PreviewPanel 顶部 | ✅ 保留 | 刷新预览 |

#### 新 ProjectPage 布局

采用 **两栏 + Drawer** 模式 — 左侧聊天，右侧始终显示手机预览，其他功能按需通过 Drawer 展开：

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Header: [←]  Project Title              [📋 Doc] [💻 Code] [⚡ Flow] [⚙] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────┐  ┌─────────────────────────────────────┐  │
│  │                         │  │                                     │  │
│  │  ThreadSelector         │  │  ────────────────────────────────   │  │
│  │                         │  │  │                                 │  │  │
│  ├─────────────────────────┤  │  │                                 │  │  │
│  │                         │  │  │        Phone Frame              │  │  │
│  │  Chat Messages          │  │  │        (简化外框)                │  │  │
│  │                         │  │  │                                 │  │  │
│  │  [User bubble]          │  │  │    ┌─────────────────────┐     │  │  │
│  │  [AI text + tools]      │  │  │    │                     │     │  │  │
│  │  [Interview widget]     │  │  │    │   Preview Content   │     │  │  │
│  │  [File changes]         │  │  │    │   (iframe/HTML)     │     │  │  │
│  │                         │  │  │    │                     │     │  │  │
│  │                         │  │  │    └─────────────────────┘     │  │  │
│  │                         │  │  │                                 │  │  │
│  │                         │  │  │                                 │  │  │
│  │                         │  │  │                                 │  │  │
│  │                         │  │  └─────────────────────────────────┘  │  │
│  │                         │  │                                     │  │
│  ├─────────────────────────┤  │  ────────────────────────────────   │  │
│  │  Token Usage (mini)     │  │  [Pages] [Live/Build] [🔄] [📤]    │  │
│  ├─────────────────────────┤  │                                     │  │
│  │                         │  │                                     │  │
│  │  ChatInput              │  │                                     │  │
│  │  + @mention pages       │  │                                     │  │
│  │                         │  │                                     │  │
│  └─────────────────────────┘  └─────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

Drawer (从右侧滑出，覆盖预览区域):
┌─────────────────────────────────────┐
│  [X] Code / Product Doc / Versions  │
│                                     │
│  内容区域                            │
│  (根据触发按钮显示不同内容)           │
│                                     │
│  Code: FileTree + CodeViewer        │
│  Doc: Markdown ProductDoc           │
│  Versions: 简化版时间线列表          │
│                                     │
└─────────────────────────────────────┘
```

#### 具体改动

**1. 布局重构**:
- 移除三栏布局 → 两栏（Chat + Preview）
- Chat 宽度: 固定 380px（当前 35% 约 420px，缩小以给预览更多空间）
- Preview 宽度: flex-1 占满剩余空间
- 移除 VersionPanel 固定侧边栏 → 改为从右侧滑出的 Drawer
- 可拖拽分隔条保留，但仅在 Chat/Preview 之间

**2. PhoneFrame 简化**:
- 当前: 黑色外框 + Dynamic Island + 渐变反光 + 圆角 48px
- 重构后: 极简圆角矩形边框（2px border），无 Dynamic Island，无渐变
- 保持 scale 自适应逻辑
- 背景从 muted/30 改为纯白或极浅灰

```
重构前:                    重构后:
┌──────────────────┐      ┌──────────────────┐
│  ╔════════════╗  │      │ ┌──────────────┐ │
│  ║ ◉◉◉◉◉◉◉◉◉◉ ║  │      │ │              │ │
│  ║ ┌────────┐ ║  │      │ │              │ │
│  ║ │        │ ║  │      │ │   Preview    │ │
│  ║ │        │ ║  │      │ │   Content    │ │
│  ║ └────────┘ ║  │      │ │              │ │
│  ╚════════════╝  │      │ └──────────────┘ │
└──────────────────┘      └──────────────────┘
  黑色外框+反光              极简圆角边框
```

**3. Header 简化**:
- 保留: 返回按钮、项目标题
- 保留: Execution Flow 入口（⚡ 图标）
- 保留: Settings 入口
- 新增: Code 快捷按钮（💻 图标，打开 Code Drawer）
- 新增: Product Doc 快捷按钮（📋 图标，打开 Doc Drawer）
- 移除: 其他装饰性元素

**4. ChatPanel 精简**:
- 保留: RunStatusStrip 轻量状态，不提供详情入口
- 移除: RunInspector / Run details 按钮、抽屉和侧边栏
- 简化: TokenDisplay → 仅显示总 token 数，hover 展开详情
- 保留: 消息列表、虚拟滚动、ChatInput、ThreadSelector、AbortDialog
- 保留: ChatMessage 中的所有富内容渲染（thinking、tools、interview、file changes 等）

**5. PreviewPanel 简化**:
- 保留: PhoneFrame（简化版）、iframe 预览、Pages 选择器
- 保留: Live/Build 切换、Refresh、Export
- 保留: Build 状态显示
- 降级: AppMode/StaticMode 切换（移入 Preview 高级设置；保留 runtime 和 state persistence 能力）
- 降级: AestheticScoreCard（默认折叠或移入 Preview 信息区）
- 简化: 工具栏从 6-7 个按钮减少到 4 个

**6. Drawer 系统**:
新建 `Drawer` 组件，从右侧滑出，支持三种内容模式：

| 模式 | 触发方式 | 内容 |
|---|---|---|
| Code | Header 💻 按钮 | FileTree + CodeViewer |
| Product Doc | Header 📋 按钮 | Markdown 渲染的产品文档 |
| Versions | Preview 区域版本号点击 | 简化版版本时间线（仅列表 + 操作） |
| Data | More/Advanced 按钮 | 复用 DataTab，保留现有数据工作台能力 |

Drawer 特性:
- 宽度: w-96 (384px)
- 动画: slide-in from right, 200ms ease-out
- 背景: 白色 + 左侧阴影
- 遮罩: 半透明黑色 overlay，点击关闭
- 可关闭: X 按钮 + ESC + 点击 overlay
- 可访问性: focus trap、aria-modal、初始 focus、关闭后恢复 focus、body scroll lock
- 移动端: 小屏幕使用 full-screen sheet 或 bottom sheet，不强制 384px 固定宽
- 实现建议: 优先基于 Radix Dialog/Sheet 模式封装，避免手写焦点和键盘交互

**7. Version 历史简化**:
当前 VersionPanel 有 808 行代码，包含大量 dialog 和复杂交互。重构后：

迁移策略:
- 先提取无 UI 的版本动作 hook/service，覆盖 pin/unpin、preview、rollback、diff、product doc history 等行为。
- 再将现有 VersionTimeline / DiffViewDialog / 相关 dialog 逐步挂到 Drawer 内。
- 最后简化视觉层。不要一次性重写 VersionPanel，避免丢失边缘交互。

| 功能 | 当前 | 重构后 |
|---|---|---|
| 版本列表 | 时间线样式 | 简洁列表，版本号 + 描述 + 时间 |
| 预览版本 | Dialog + PhoneFrame | 直接在主预览区切换（临时） |
| Pin/Unpin | 按钮 + 限额处理 Dialog | 保留，简化 UI |
| Rollback | AlertDialog | 保留 |
| Diff | DiffViewDialog | 保留，通过 Drawer 内按钮触发 |
| 快照列表 | 与版本混合 | 折叠区域，默认隐藏 |
| Product Doc 历史 | 与版本混合 | 仅在 Doc Drawer 中显示 |
| Stats 面板 | Current/Pinned/Total | 简化为一行文字 |

**8. 响应式适配**（与 Phase 2 合并实施）:

| Breakpoint | 行为 |
|---|---|
| `< 768px` | 单列，仅显示 Chat，Preview 通过底部 Tab 切换 |
| `768-1280px` | 两栏，Chat 320px + Preview flex-1 |
| `> 1280px` | 两栏，Chat 380px + Preview flex-1 |

---

### 设计系统基础建设（实施 Phase 1）

建立统一的设计 token 系统，为后续组件和布局提供规范。

#### 1.1 品牌色板设计

采用 Notion 风格的简约色板 — 以黑白灰为主，品牌色作为点缀：

| 语义 | 色值 (HSL) | 色值 (HEX) | 用途 |
|---|---|---|---|
| Brand Primary | `0 0% 9%` | `#171717` (近黑) | 主按钮、active 状态 |
| Brand Accent | `240 5% 65%` | `#9F9FA6` (中性灰) | 次要强调元素 |
| Brand Highlight | `240 5% 94%` | `#EDEDEF` (浅灰) | hover 背景、分隔 |

替换当前:
- `--primary`: `240 5.9% 10%` → 保持不变（已接近目标）
- `--accent`: `217 91% 60%` (blue) → `0 0% 9%` (近黑)
- `--ring`: 同步改为品牌色

Notion 风格的核心是**克制** — 色彩仅用于传达状态，不做装饰。

#### 1.2 语义化颜色变量

新增以下 CSS 变量，替换所有硬编码状态色：

| 变量 | 色值 (HSL) | 用途 |
|---|---|---|
| `--status-info-bg` | `210 50% 96%` | 信息类背景 |
| `--status-info-text` | `210 30% 35%` | 信息类文字 |
| `--status-success-bg` | `140 40% 96%` | 成功类背景 |
| `--status-success-text` | `140 35% 30%` | 成功类文字 |
| `--status-warning-bg` | `40 60% 96%` | 警告类背景 |
| `--status-warning-text` | `40 50% 35%` | 警告类文字 |
| `--status-error-bg` | `0 50% 97%` | 错误类背景 |
| `--status-error-text` | `0 50% 40%` | 错误类文字 |

饱和度降低，保持 Notion 风格的柔和感。

#### 1.3 字体系统规范化

```css
/* Tailwind theme 扩展 */
fontFamily: {
  sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
  mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
}
```

- 保留 Inter 作为主字体
- 新增 JetBrains Mono 作为代码字体（需引入）
- 完善 fallback 栈

#### 1.4 阴影体系

在 Tailwind config 中定义完整的 elevation scale：

| Token | 值 | 用途 |
|---|---|---|
| `shadow-card` | `0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)` | 卡片默认 |
| `shadow-card-hover` | `0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04)` | 卡片 hover |
| `shadow-dropdown` | `0 10px 25px rgba(0,0,0,0.08), 0 4px 10px rgba(0,0,0,0.04)` | 下拉菜单 |
| `shadow-modal` | `0 20px 40px rgba(0,0,0,0.12), 0 8px 16px rgba(0,0,0,0.06)` | 模态框 |
| `shadow-phone` | `0 24px 60px -30px rgba(0,0,0,0.6)` | PhoneFrame 外阴影 |

阴影更轻、更柔和，符合 Notion 风格。

#### 1.5 圆角规范化

| Token | 值 | 用途 |
|---|---|---|
| `rounded-sm` | 4px | 小内联元素 |
| `rounded-md` | 6px | 按钮、输入框、徽章 |
| `rounded-lg` | 8px | 卡片、面板 |
| `rounded-xl` | 12px | 大卡片、对话框 |
| `rounded-2xl` | 16px | 聊天气泡、特殊容器 |

在 Tailwind theme 中显式定义，确保一致性。

#### 1.6 动画时长规范

| Token | 值 | 用途 |
|---|---|---|
| `--duration-fast` | `100ms` | 微交互（hover、点击） |
| `--duration-normal` | `200ms` | 常规过渡（面板切换） |
| `--duration-slow` | `300ms` | 复杂动画（折叠展开） |

---

### 布局架构抽象（实施 Phase 5）

重构页面布局结构，提升灵活性和可维护性。

#### 5.1 可拖拽面板分隔条

**当前**: ChatPanel 固定 `w-[35%]`，中间分隔条仅视觉元素。

**重构后**:
- 实现 `ResizableSplitPane` 组件
- 支持鼠标拖拽调整左右面板比例
- 最小/最大宽度约束（ChatPanel: min 280px, max 50%）
- 拖拽时显示视觉反馈（高亮分隔条 + 宽度提示）
- 面板比例持久化到 localStorage

**影响页面**: ProjectPage

#### 5.2 Drawer 组件系统

新建 Drawer 组件，替代当前 VersionPanel 的固定侧边栏模式：

```
src/components/custom/
├── Drawer.tsx              # 通用右侧滑出 Drawer
├── CodeDrawer.tsx          # Code 内容（复用 CodePanel 逻辑）
├── DocDrawer.tsx           # Product Doc 内容（复用 ProductDocPanel 逻辑）
├── VersionsDrawer.tsx      # 简化版版本历史（从 VersionPanel 提取核心逻辑）
└── DataDrawer.tsx          # 高级数据工作台（复用 DataTab 逻辑）
```

Drawer 特性:
- 宽度: w-96 (384px)，可配置
- 动画: slide-in from right, 200ms ease-out
- 遮罩: 半透明 overlay，点击关闭
- 关闭方式: X 按钮 + ESC + 点击 overlay
- 支持嵌套: Drawer 内可打开子 Drawer（如 DiffView）
- 使用 Dialog 语义: `role="dialog"` / `aria-modal="true"` / 标题关联 / ESC 关闭
- 焦点管理: 打开后 focus 到标题或第一个操作，关闭后回到触发按钮
- 背景滚动: 打开时锁定 body scroll，关闭时恢复
- 响应式: `< 768px` 使用全屏 Sheet，`>= 768px` 使用右侧 Drawer

#### 5.3 布局组件抽象

提取通用布局组件，减少各页面重复代码：

```
src/components/Layout/
├── AppLayout.tsx          # 最外层布局（header + content 结构）
├── PageHeader.tsx         # 统一页面头部（返回按钮 + 标题 + 右侧操作）
├── ResizableSplitPane     # 可拖拽分隔面板
└── ContentArea.tsx        # 内容区域包装器（padding、max-width）
```

**各页面改造**:

| 页面 | 改造内容 |
|---|---|
| HomePage | 使用 `AppLayout` + `PageHeader` + `ContentArea` |
| ProjectPage | 使用 `AppLayout` + `PageHeader` + `ResizableSplitPane` + Drawer 系统 |
| ExecutionPage | 使用 `AppLayout` + `PageHeader` + `ContentArea` |
| SettingsPage | 使用 `AppLayout` + `PageHeader` + `ContentArea` |

#### 5.4 响应式布局适配

增加 breakpoint 响应式规则：

| Breakpoint | 行为 |
|---|---|
| `< 768px` | 单列布局，Chat/Preview 通过底部 Tab 切换 |
| `768-1280px` | 两栏布局，ChatPanel 320px，Preview flex-1 |
| `> 1280px` | 两栏布局，ChatPanel 380px，Preview flex-1 |

**具体调整**:
- HomePage 项目网格: `sm:2列 → lg:3列` (已有) → 增加 `xs:1列`
- ProjectPage: 小屏幕时 Chat/Preview 通过底部 Tab 切换，非并排
- SettingsPage: 小屏幕时侧边导航变为顶部 Tab

#### 5.5 VersionPanel 折叠动画优化

**当前**: 仅宽度从 `w-80` 切换到 `w-14`，内容直接消失。

**重构后**: 改为 Drawer 模式后，折叠动画变为 slide-in/out:
- 打开时: overlay fade-in + panel slide-in from right
- 关闭时: overlay fade-out + panel slide-out to right
- 使用 CSS transition，200ms ease-out

---

### 视觉风格统一（实施 Phase 6）

在设计系统基础上，统一各页面和组件的视觉风格。

#### 6.1 卡片风格统一

统一所有卡片类组件的视觉规范（Notion 风格）：

```
- 背景: bg-card (白色)
- 边框: border border-border (极浅灰)
- 圆角: rounded-lg (8px)
- 阴影: 默认无阴影，hover 时 shadow-card
- 内边距: p-4 或 p-6
- hover 效果: 背景色变化 (transparent → muted/20)
```

Notion 风格卡片特点：**默认无边框无阴影，hover 时轻微背景色变化**。

**影响组件**: ProjectCard, ChatMessage (AI 消息背景), TaskCard

#### 6.2 按钮风格统一

| 类型 | 样式 |
|---|---|
| Primary | 近黑背景 + 白色文字 + rounded-md |
| Secondary | 浅灰背景 + 近黑文字 + rounded-md |
| Ghost | 透明背景 + hover 时 muted 背景 |
| Destructive | 红色背景 + 白色文字 (保持现有) |
| Icon | 方形 h-9 w-9 + rounded-md + ghost 变体 |

#### 6.3 PhoneFrame 简化

| 元素 | 当前 | 重构后 |
|---|---|---|
| 外框 | bg-black + 圆角 48px | border-2 border-border + 圆角 2xl |
| 内框 | bg-zinc-900 + 圆角 44px | 移除 |
| Dynamic Island | 黑色椭圆 + 阴影 | 移除 |
| 渐变反光 | from-white/10 | 移除 |
| 外阴影 | 0 24px 60px -30px rgba(0,0,0,0.6) | shadow-card-hover |
| 背景 | bg-muted/30 | bg-muted/10 或纯白 |

#### 6.4 空状态设计

为各页面的空状态增加统一设计：

| 页面 | 空状态内容 |
|---|---|
| HomePage | 咖啡杯图标 + "No projects yet" + 引导文字 |
| ProjectPage (Chat) | 保留现有 4 个建议 prompt，hover 时背景色变化 |
| ExecutionPage | 动态 loading 动画 + "Waiting for execution..." |
| Preview (无内容) | 简化 PhoneFrame + "Start chatting to generate a page" |
| Drawer (空) | 图标 + 引导文字 |

#### 6.5 状态指示器统一

使用 Phase 1 定义的语义色变量，统一所有状态显示：

| 状态 | 颜色 | 应用场景 |
|---|---|---|
| Info | `--status-info-*` | 构建中、同步中 |
| Success | `--status-success-*` | 完成、通过 |
| Warning | `--status-warning-*` | 重试、待确认 |
| Error | `--status-error-*` | 失败、错误 |

**影响组件**: BuildStatusIndicator, StatusIcon, TaskCard 状态标签, Build 状态 badge

#### 6.6 加载状态优化

| 场景 | 当前 | 重构后 |
|---|---|---|
| 列表加载 | Skeleton 块 | 骨架屏 + 柔和微光动画 |
| 按钮加载 | Loader2 spin | 按钮内嵌 spinner + 文字变 "Loading..." |
| 页面切换 | 无过渡 | fade-in 过渡动画 |
| Drawer 打开 | 无 | slide-in + overlay fade-in |
| 内容加载 | 空白 | 保持上次内容 + overlay spinner |

---

## 实施顺序

```
Phase 1 (设计系统)
├── 1.1 品牌色板 → CSS 变量更新
├── 1.2 语义色变量 → CSS 变量更新
├── 1.3 字体系统 → Tailwind config + 字体引入
├── 1.4 阴影体系 → Tailwind config
├── 1.5 圆角规范 → Tailwind config
└── 1.6 动画规范 → CSS 变量
状态: 已完成

Phase 2 (主页重设计)
├── 2.1 Hero 区域 + 输入框
├── 2.2 Quick Start 模板卡片
├── 2.3 Recent Projects 区域
├── 2.4 保留 pinned/search/sort/manage/delete 项目管理能力
├── 2.5 空状态设计
└── 2.6 Logo 更新
状态: 基本完成；Header logo 仍采用咖啡图标方案，未切换到纯文字 IC 方案

Phase 3 (ProjectPage 布局壳)
├── 3.1 两栏布局实现 (Chat + Preview)
├── 3.2 ResizableSplitPane 组件开发
├── 3.3 Header 重构 (新增 Code/Doc/More/Versions 快捷按钮)
├── 3.4 PhoneFrame 简化
├── 3.5 PreviewPanel 工具栏整理
└── 3.6 响应式 Chat/Preview 切换
状态: 基本完成；移动端采用纵向堆叠而非底部 Tab

Phase 4 (Drawer 功能迁移)
├── 4.1 Drawer 组件系统
├── 4.2 CodeDrawer
├── 4.3 DocDrawer
├── 4.4 DataDrawer (保留 DataTab 能力)
├── 4.5 VersionsDrawer 行为 hook 提取
├── 4.6 VersionsDrawer UI 迁移
└── 4.7 RunStatusStrip 保留轻量状态，RunInspector / Run details 入口移除
状态: 基本完成；Code/Doc/Data/Version 已迁移为 Drawer，Run details 抽屉和 RunInspector 已从 ProjectPage 移除

Phase 5 (布局架构抽象)
├── 5.1 AppLayout / PageHeader / ContentArea 抽象
├── 5.2 HomePage / ExecutionPage / SettingsPage 接入通用布局
├── 5.3 ProjectPage Header 操作区接入 PageHeader
├── 5.4 4 个页面响应式回归整理
└── 5.5 删除重复 header/wrapper 结构
状态: 已完成主要页面迁移；ProjectPage、HomePage、SettingsPage、ExecutionPage 已接入共享布局

Phase 6 (视觉统一)
├── 6.1 卡片风格统一
├── 6.2 按钮风格统一
├── 6.3 PhoneFrame 简化
├── 6.4 空状态设计
├── 6.5 状态指示器统一
└── 6.6 加载状态优化
状态: 部分完成；状态色、PhoneFrame、多个高可见组件已收敛，完整卡片/按钮/加载体系仍可继续细化
```

---

## 风险与注意事项

| 风险 | 应对 |
|---|---|
| ProjectPage 改动范围大 | 分步骤实施，先布局后功能迁移，每步可回退 |
| VersionPanel 808 行代码迁移 | 先提取行为 hook/service，再迁移 UI，避免一次性重写 |
| DataTab 已有 e2e 覆盖 | 不直接删除，迁移为 DataDrawer 或 More/Advanced 入口 |
| AppMode 影响 iframe runtime/state | 不删除 runtime，只把入口降级到 Preview 高级设置 |
| RunInspector 已有运行观测和 e2e | ProjectPage Run details 抽屉和 RunInspector 已移除；不要在 chat 输入框附近恢复 |
| PhoneFrame 简化可能丢失用户喜好 | 保留原版 PhoneFrame 代码，可通过配置切换 |
| 品牌色变更影响范围大 | 先更新 CSS 变量，全局搜索替换硬编码色值 |
| 可拖拽面板复杂度 | 先实现基础拖拽，后续再增加持久化等高级功能 |
| 响应式改动量大 | 按页面逐个改造，每个页面完成后单独验证 |
| 字体引入增加加载时间 | 使用 font-display: swap，预连接 Google Fonts |
| Drawer 手写可访问性易遗漏 | 优先基于 Radix Dialog/Sheet 语义封装，测试 ESC、焦点恢复和移动端布局 |

---

## 验收标准

- [x] 主页全新设计，包含 Hero / Quick Start / Recent Projects 区域
- [x] Logo 更新为简约风格
- [x] ProjectPage 改为两栏布局 (Chat + Preview)
- [x] PhoneFrame 简化为极简圆角边框
- [x] VersionPanel 改为 Drawer 模式
- [x] Code/Doc/Data/Versions 通过 Header 入口以 Drawer 打开
- [x] DataTab 能力保留，相关 e2e 不回退
- [x] AppMode/StaticMode runtime 能力保留
- [x] RunInspector 不再挤占 ChatPanel 常驻空间，RunStatusStrip 只保留轻量状态，Run details 入口已移除
- [x] Drawer 系统正常工作 (slide-in/out, overlay, ESC 关闭、focus trap、焦点恢复、body scroll lock)
- [x] CSS 变量和语义色 token 已定义，业务状态色已大范围收敛
- [x] 品牌色在主要页面一致应用
- [x] ProjectPage 面板支持拖拽调整宽度
- [ ] 4 个页面在 sm/md/xl 三种断点下正常显示
- [ ] 所有卡片、按钮风格统一（Notion 风格）
- [x] 空状态有引导性设计
- [x] 状态指示器使用语义色变量
- [x] 布局组件复用率 > 60%

## 验证清单

每个阶段完成后至少运行:

```bash
cd packages/web
npm run lint
npm run build
```

ProjectPage / Drawer / 运行观测相关阶段额外运行:

```bash
cd packages/web
npx playwright test PreviewBridge.spec.ts RunStatus.spec.ts DataTab.spec.ts v08DataTabOverhaul.spec.ts
```

当前新增 Drawer 回归也应纳入 ProjectPage 相关阶段验证:

```bash
cd packages/web
npx playwright test ProjectDrawers.spec.ts PreviewBridge.spec.ts RunStatus.spec.ts DataTab.spec.ts v08DataTabOverhaul.spec.ts
```

手动或 Playwright 断点检查:
- 375px: HomePage、ProjectPage、SettingsPage、ExecutionPage 不横向溢出
- 768px: Chat/Preview 切换或两栏过渡正常
- 1280px: ProjectPage 两栏和 Drawer 正常
- 1440px: 预览区域、版本 Drawer、项目列表密度正常

核心回归路径:
- 创建项目并进入 ProjectPage
- 发送消息并生成预览
- 多页面选择、刷新、Live/Build 切换
- Export 操作
- Abort 长任务入口
- Code / Doc / Data / Versions Drawer 打开与关闭
- Version pin/unpin、preview、rollback、diff
- Execution Flow 入口和运行详情可达
