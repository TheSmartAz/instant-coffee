# ProjectPage 页面布局与组件分析

## Component Tree

```
ProjectPage
  ├── ChatPanel (35% width, left column)
  │     ├── ChatMessage[] (virtualized)
  │     │     ├── InterviewWidget
  │     │     ├── AssetThumbnail[]
  │     │     └── ReactMarkdown
  │     └── ChatInput
  │           ├── ImageThumbnail[]
  │           ├── PageMentionPopover
  │           └── AssetTypeSelector (Dialog)
  │
  ├── EventList (alternate left tab)
  │     └── EventItem[] (virtualized)
  │
  ├── WorkbenchPanel (flex-1, center)
  │     ├── PreviewPanel (preview tab)
  │     │     ├── PageSelector
  │     │     ├── PhoneFrame > iframe
  │     │     ├── DataTab (sub-tab)
  │     │     ├── AestheticScoreCard
  │     │     └── BuildStatusIndicator
  │     ├── CodePanel (code tab)
  │     └── ProductDocPanel (product-doc tab)
  │
  └── VersionPanel (w-80 / w-14 collapsed, right)
        ├── VersionTimeline
        ├── PinnedLimitDialog
        └── PhoneFrame (preview dialog)
```

---

## 1. ProjectPage (Root)

**文件:** `packages/web/src/pages/ProjectPage.tsx` (772 lines)
**Props:** 无 (路由组件, 从 `useParams()` 读取 `id`)

### Layout Drawing

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ HEADER  [← Back]  [Title]                        [Activity] [Settings]      │
├──────────────┬───┬──────────────────────────────────┬────────────────────────┤
│              │ ┃ │                                    │                        │
│  LEFT PANEL  │ ┃ │       WORKBENCH (flex-1)           │   VERSION PANEL        │
│  w-[35%]     │ ┃ │                                    │   w-80 / w-14          │
│  min-300px   │ ┃ │                                    │                        │
│  max-[45%]   │ ┃ │                                    │                        │
│              │ ┃ │                                    │                        │
│  ┌─────────┐ │ ┃ │  ┌──────────────────────────────┐ │  ┌──────────────────┐  │
│  │ Tabs:   │ │ ┃ │  │ Tabs: Preview|Code|ProdDoc   │ │  │ Context Card     │  │
│  │ Chat |  │ │ ┃ │  ├──────────────────────────────┤ │  ├──────────────────┤  │
│  │ Events  │ │ ┃ │  │                              │ │  │                  │  │
│  ├─────────┤ │ ┃ │  │   (active tab content)       │ │  │ VersionTimeline  │  │
│  │         │ │ ┃ │  │                              │ │  │                  │  │
│  │ content │ │ ┃ │  │                              │ │  │                  │  │
│  │         │ │ ┃ │  │                              │ │  │                  │  │
│  └─────────┘ │ ┃ │  └──────────────────────────────┘ │  └──────────────────┘  │
│              │ ┃ │                                    │                        │
└──────────────┴───┴──────────────────────────────────┴────────────────────────┘
                 ↑ resize handle (1px divider)
```

### Key State

- `activeTab`: `'chat' | 'events'` — 左侧面板内容切换
- `workbenchTab`: `'preview' | 'code' | 'product-doc'` — 工作台标签
- `appMode`: boolean — 预览中的 App 模式开关
- `previewMode`: `'live' | 'build'` — 实时预览 vs 构建输出
- `previewHtml` / `previewUrl`: 当前预览内容
- `isVersionPanelCollapsed`: boolean — 版本面板折叠状态
- `pagePreviewVersion`: `number | null`
- `buildPreviewStamp`: 缓存刷新时间戳

### Hooks

- `useSession(sessionId)` — 加载 session、messages、versions
- `useChat({...})` — 管理聊天流、资产、面试操作
- `useSSE({...})` — SSE 连接用于事件标签
- `usePages(sessionId)` — 多页面管理
- `useProductDoc(sessionId)` — 产品文档状态
- `useAestheticScore(sessionId)` — 美学评分
- `useBuildStatus(sessionId)` — 构建状态管理

---

## 2. ChatPanel

**文件:** `packages/web/src/components/custom/ChatPanel.tsx` (259 lines)

### Props

```typescript
interface ChatPanelProps {
  messages: Message[]
  assets?: ChatAsset[]
  onSendMessage: (content: string, options?: {
    triggerInterview?: boolean
    generateNow?: boolean
    attachments?: ChatAttachment[]
    targetPages?: string[]
    styleReference?: ChatStyleReference
  }) => void
  onAssetUpload?: ChatInputProps['onAssetUpload']
  onAssetRemove?: (assetId: string) => void
  onInterviewAction?: (payload: InterviewActionPayload) => void
  onTabChange?: (tab: 'preview' | 'code' | 'product-doc') => void
  onDisambiguationSelect?: (option: { id: string; slug: string; title: string }) => void
  isLoading?: boolean
  title?: string
  status?: string
  errorMessage?: string | null
  showHeader?: boolean
  showBorder?: boolean
  className?: string
  pages?: Page[]
}
```

### Layout Drawing

```
┌──────────────────────────┐
│ [Optional Header + Status]│
├──────────────────────────┤
│ ScrollArea (flex-1)       │
│ ┌──────────────────────┐ │
│ │ ChatMessage (asst)   │ │
│ │  ┌─ ReactMarkdown ─┐ │ │
│ │  │ content          │ │ │
│ │  └─────────────────┘ │ │
│ │  ┌─ InterviewWidget ┐│ │
│ │  │ (conditional)     ││ │
│ │  └──────────────────┘│ │
│ ├──────────────────────┤ │
│ │    ChatMessage (user)│ │
│ │         ┌──────────┐ │ │
│ │         │ bubble ▐▐ │ │ │
│ │         └──────────┘ │ │
│ └──────────────────────┘ │
│  (virtualized, 80+ items)│
├──────────────────────────┤
│ [Error banner]            │
├──────────────────────────┤
│ ChatInput                 │
└──────────────────────────┘
```

### Logic

- 使用 `useVirtualList` 虚拟列表 (threshold: 80, overscan: 8)
- 接近底部 (80px) 时自动滚动
- 资产解析: 将消息中的 `asset:ID` 引用映射到实际 ChatAsset 对象
- 过滤隐藏消息, 如果有资产但消息中无资产引用则前置资产摘要消息

---

## 3. ChatMessage

**文件:** `packages/web/src/components/custom/ChatMessage.tsx` (299 lines)

### Props

```typescript
interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
  timestamp?: Date
  isStreaming?: boolean
  steps?: ChatStep[]
  interview?: InterviewBatch
  interviewSummary?: InterviewSummary
  action?: ChatAction
  affectedPages?: string[]
  disambiguation?: Disambiguation
  assets?: ChatAsset[]
  onAssetRemove?: (assetId: string) => void
  onInterviewAction?: (payload: InterviewActionPayload) => void
  onTabChange?: (tab: 'preview' | 'code' | 'product-doc') => void
  onDisambiguationSelect?: (option: { id: string; slug: string; title: string }) => void
}
```

### Layout Drawing

```
Assistant message:                    User message:
┌─────────────────────────┐          ┌─────────────────────────┐
│ ┌─ max-w-3xl ─────────┐│          │         ┌─ max-w-[70%] ┐│
│ │ ReactMarkdown        ││          │         │ bubble (blue) ││
│ │ (content)            ││          │         │ text content  ││
│ ├──────────────────────┤│          │         └──────────────┘│
│ │ AssetThumbnail[]     ││          │              timestamp   │
│ ├──────────────────────┤│          └─────────────────────────┘
│ │ InterviewWidget      ││
│ │ (if interview batch) ││
│ ├──────────────────────┤│
│ │ InterviewSummary     ││
│ │ Disambiguation opts  ││
│ │ Action links         ││
│ │ Affected pages       ││
│ │ Steps                ││
│ │ Timestamp            ││
│ └──────────────────────┘│
└─────────────────────────┘
```

### Logic

- 使用 `React.memo` 优化渲染
- 根据消息属性条件渲染 InterviewWidget、summary、disambiguation、action links
- 使用 ReactMarkdown + remarkGfm 渲染内容

---

## 4. ChatInput

**文件:** `packages/web/src/components/custom/ChatInput.tsx` (1116 lines)

### Props

```typescript
interface ChatInputProps {
  onSend: (message: string, options?: {
    triggerInterview?: boolean
    attachments?: ChatAttachment[]
    targetPages?: string[]
    styleReference?: ChatStyleReference
  }) => void
  onAssetUpload?: (file: File, type: AssetType, options?: {
    onProgress?: (progress: number) => void
  }) => Promise<void>
  disabled?: boolean
  placeholder?: string
  initialInterviewOn?: boolean
  showInterviewToggle?: boolean
  pages?: Page[]
}
```

### Layout Drawing

```
┌──────────────────────────────────────┐
│ ┌─ Attachment row ─────────────────┐ │
│ │ [ImageThumb] [ImageThumb] [+]    │ │
│ └──────────────────────────────────┘ │
│ ┌─ Upload progress bar ───────────┐ │
│ └──────────────────────────────────┘ │
│ ┌──────────────────────────────────┐ │
│ │ Textarea (auto-resize, max 160px)│ │
│ │ (drag/drop, paste, @mention)     │ │
│ └──────────────────────────────────┘ │
│ ┌──────────────────────────────────┐ │
│ │ [Interview] [Model▾]  [📎][🎤][➤] │ │
│ └──────────────────────────────────┘ │
│                                      │
│ ┌─ PageMentionPopover (floating) ─┐ │
│ │ @page1  @page2  @page3          │ │
│ └──────────────────────────────────┘ │
│                                      │
│ ┌─ AssetTypeSelector (Dialog) ────┐ │
│ │ [logo] [style_ref]              │ │
│ │ [background] [product_image]    │ │
│ └──────────────────────────────────┘ │
└──────────────────────────────────────┘
```

### Logic

- **@mention 系统:** 检测 textarea 中的 `@`, 显示 PageMentionPopover, 键盘导航 (上/下/回车/ESC)
- **图片附件:** 拖放、粘贴、文件选择器。最多 3 个附件, 10MB 限制, canvas 自动压缩
- **资产上传:** 先打开 AssetTypeSelector 对话框, 再打开文件选择器
- **语音输入:** Web Speech API (SpeechRecognition)
- **模型选择:** 使用 `useSettings` hook, 显示模型 logo
- **自动调整高度:** textarea 最高 160px

---

## 5. InterviewWidget

**文件:** `packages/web/src/components/custom/InterviewWidget.tsx` (372 lines)

### Props

```typescript
interface InterviewWidgetProps {
  batch: InterviewBatch
  onAction: (payload: {
    action: 'submit' | 'skip' | 'generate'
    batchId: string
    answers: InterviewAnswer[]
  }) => void
}
```

### Layout Drawing

```
┌──────────────────────────────────┐
│ Interview          Q 2/4         │
├──────────────────────────────────┤
│ "Tell us about your project..."  │
├──────────────────────────────────┤
│ ┌──────────────────────────────┐ │
│ │ Question text                │ │
│ │                              │ │
│ │ ○ Option A                   │ │
│ │ ● Option B  (selected)       │ │
│ │ ○ Option C                   │ │
│ │ ○ Other: [___________]       │ │
│ └──────────────────────────────┘ │
├──────────────────────────────────┤
│ [← Previous]          [Next →]   │
├──────────────────────────────────┤
│ [Skip questions]  [Generate now] │
└──────────────────────────────────┘
```

### Logic

- 逐题展示, Previous/Next 导航
- 支持单选 (radio)、多选 (checkbox)、文本输入
- "Other" 选项支持自由文本输入
- 三种操作: submit (提交答案), skip (跳过批次), generate (立即生成)
- 批次状态非 'active' 时为只读模式

---

## 6. WorkbenchPanel

**文件:** `packages/web/src/components/custom/WorkbenchPanel.tsx` (192 lines)

### Props

```typescript
interface WorkbenchPanelProps {
  sessionId: string
  appMode?: boolean
  onAppModeChange?: (next: boolean) => void
  previewMode?: 'live' | 'build'
  onPreviewModeChange?: (next: 'live' | 'build') => void
  onBuildFromDoc?: () => void
  buildDisabled?: boolean
  previewVersion?: number | null
  productDocVersion?: number | null
  activeTab: WorkbenchTab  // 'preview' | 'code' | 'product-doc'
  onTabChange: (tab: WorkbenchTab) => void
  pages?: PageInfo[]
  selectedPageId?: string | null
  onSelectPage?: (pageId: string) => void
  previewHtml?: string | null
  previewUrl?: string | null
  buildPreviewUrl?: string | null
  isRefreshing?: boolean
  isExporting?: boolean
  onRefresh?: () => void
  onRefreshPage?: (pageId: string) => void
  onExport?: () => void
  aestheticScore?: AestheticScore | null
  buildState?: BuildState | null
  onBuildRetry?: () => void
  onBuildCancel?: () => void
  onBuildPageSelect?: (page: string) => void
  selectedBuildPage?: string | null
}
```

### Layout Drawing

```
┌──────────────────────────────────────┐
│ Tab bar (h-14)                       │
│ [Preview ⓥ] [Code ⓥ] [Product Doc ⓥ]│
├──────────────────────────────────────┤
│                                      │
│   (show/hide, not unmount)           │
│                                      │
│   PreviewPanel  (when preview)       │
│   CodePanel     (when code)          │
│   ProductDocPanel (when product-doc) │
│                                      │
└──────────────────────────────────────┘
```

### Logic

- Tab 容器, 在 Preview / Code / Product Doc 面板间切换
- 使用 CSS show/hide (非 unmount) 以保留状态
- 将所有预览相关 props 传递给 PreviewPanel

---

## 7. PreviewPanel

**文件:** `packages/web/src/components/custom/PreviewPanel.tsx` (882 lines)

### Props

```typescript
interface PreviewPanelProps {
  sessionId?: string
  appMode?: boolean
  onAppModeChange?: (next: boolean) => void
  previewMode?: 'live' | 'build'
  onPreviewModeChange?: (next: 'live' | 'build') => void
  htmlContent?: string
  previewUrl?: string | null
  buildPreviewUrl?: string | null
  onRefresh?: () => void
  onExport?: () => void
  isRefreshing?: boolean
  isExporting?: boolean
  aestheticScore?: AestheticScore | null
  buildState?: BuildState | null
  onBuildRetry?: () => void
  onBuildCancel?: () => void
  onBuildPageSelect?: (page: string) => void
  selectedBuildPage?: string | null
  pages?: PageInfo[]
  selectedPageId?: string | null
  onSelectPage?: (pageId: string) => void
  onRefreshPage?: (pageId: string) => void
}
```

### Layout Drawing

```
┌──────────────────────────────────────────┐
│ Tabs: [Preview] [Data]                   │
│ ┌──────────────────────────────────────┐ │
│ │ Toolbar:                             │ │
│ │ [Preview|Data] "Preview" [BuildBadge]│ │
│ │ [Live|Build] [App|Static] [↻] [⬇]   │ │
│ └──────────────────────────────────────┘ │
├──────────────────────────────────────────┤
│ [BuildStatusIndicator] (conditional)     │
│ [PageSelector] (if multi-page)           │
├──────────────────────────────────────────┤
│ ┌──────────────────────────────────────┐ │
│ │  ┌─ PhoneFrame (scaled) ──────────┐ │ │
│ │  │  ┌─ iframe ──────────────────┐ │ │ │
│ │  │  │                           │ │ │ │
│ │  │  │   430px × 932px           │ │ │ │
│ │  │  │   (9:19.5 ratio)          │ │ │ │
│ │  │  │                           │ │ │ │
│ │  │  │   srcDoc (live) or        │ │ │ │
│ │  │  │   src (build URL)         │ │ │ │
│ │  │  │                           │ │ │ │
│ │  │  └───────────────────────────┘ │ │ │
│ │  └────────────────────────────────┘ │ │
│ └──────────────────────────────────────┘ │
├──────────────────────────────────────────┤
│ ▸ Aesthetic Score (Collapsible)          │
│   ┌──────────────────────────────────┐   │
│   │ AestheticScoreCard               │   │
│   └──────────────────────────────────┘   │
└──────────────────────────────────────────┘
```

### Logic

- **ResizeObserver** 自动缩放 PhoneFrame (0.6–1.0)
- **App Mode Runtime:** 向 iframe 注入 JS 运行时, 拦截表单输入、导航点击和状态变化, 通过 postMessage 与父窗口通信
- **Build 预览:** 在实时 HTML 预览和构建输出 URL 之间切换
- **状态持久化:** 将 app state 和美学评分展开状态保存到 localStorage
- **导航拦截:** App 模式下拦截 iframe 的 `ic_nav` 消息实现页面间导航

---

## 8. VersionPanel

**文件:** `packages/web/src/components/custom/VersionPanel.tsx` (808 lines)

### Props

```typescript
interface VersionPanelProps {
  sessionId?: string
  sessionTitle?: string | null
  selectedPageId?: string | null
  selectedPageTitle?: string | null
  activeTab: VersionTab  // 'preview' | 'code' | 'product-doc'
  isCollapsed: boolean
  onToggleCollapse: () => void
}
```

### Layout Drawing

```
Expanded (w-80):                    Collapsed (w-14):
┌────────────────────────┐         ┌──────┐
│ [icon] Title    [◀ ▶]  │         │ [▶]  │
├────────────────────────┤         │      │
│ Context Card           │         │ [📄]  │
│ ┌────┬────┬────┐       │         │  3   │
│ │ v3 │ 2s │ 1d │       │         │      │
│ └────┴────┴────┘       │         └──────┘
├────────────────────────┤
│ VersionTimeline        │
│ ┌──────────────────┐   │
│ │ ★ Pinned         │   │
│ │  • v3 (current)  │   │
│ ├──────────────────┤   │
│ │ History          │   │
│ │  • v3 ●──        │   │
│ │  • v2 ○──        │   │
│ │  • v1 ○──        │   │
│ └──────────────────┘   │
└────────────────────────┘

Dialogs (overlay):
┌─ Preview Dialog ──────┐  ┌─ Doc Dialog ──────────┐
│ PhoneFrame + iframe    │  │ ReactMarkdown content  │
└────────────────────────┘  └────────────────────────┘
┌─ Rollback AlertDialog ┐  ┌─ PinnedLimitDialog ───┐
│ Confirm rollback?      │  │ Unpin one to continue  │
└────────────────────────┘  └────────────────────────┘
```

### Logic

- 根据 `activeTab` 适配内容: 页面版本 / 快照 / 产品文档历史
- 使用 `usePageVersions`, `useSnapshots`, `useProductDocHistory` hooks 获取数据
- 使用 `useVersionPin` 处理 pin/unpin 操作及冲突解决 (PinnedLimitDialog)
- Preview dialog: 加载页面版本 HTML 并在 PhoneFrame 中显示
- Doc dialog: 加载产品文档历史内容并用 ReactMarkdown 渲染
- Rollback: 确认后通过 API 执行快照回滚

---

## 9. VersionTimeline

**文件:** `packages/web/src/components/custom/VersionTimeline.tsx` (400 lines)

### Props

```typescript
interface VersionTimelineProps {
  type: 'page' | 'snapshot' | 'product-doc'
  versions: Array<PageVersion | ProjectSnapshot | ProductDocHistory>
  currentId?: string | number | null
  actions?: VersionTimelineAction[]  // 'view' | 'diff' | 'rollback' | 'pin'
  isLoading?: boolean
  emptyMessage?: string
  actionState?: VersionTimelineActionState | null
  onView?: (item: PageVersion | ProductDocHistory) => void
  onDiff?: (item: ProductDocHistory) => void
  onRollback?: (item: ProjectSnapshot) => void
  onPin?: (item: ...) => void
  onUnpin?: (item: ...) => void
}
```

### Layout Drawing

```
┌──────────────────────────┐
│ ★ Pinned                 │
│  ┌─────────────────────┐ │
│  │ ● v3 [Current][Pin] │ │
│  │   "Added hero..."   │ │
│  │   [View] [Unpin]    │ │
│  └─────────────────────┘ │
├──────────────────────────┤
│ History                  │
│  ┌─────────────────────┐ │
│  │ ○ v2 [Released]     │ │
│  │   "Initial layout"  │ │
│  │   [View] [Pin]      │ │
│  ├─────────────────────┤ │
│  │ ○ v1                │ │
│  │   "First draft"     │ │
│  │   [View] [Rollback] │ │
│  └─────────────────────┘ │
└──────────────────────────┘
```

### Logic

- ScrollArea 包含两组: Pinned versions 和 Version history
- 每项显示时间线圆点、标题、徽章 (Current/Pinned/Released/source)、描述、元信息
- 操作按钮: View / Compare / Rollback / Pin/Unpin

---

## 10. EventList / EventItem

**文件:**
- `packages/web/src/components/EventFlow/EventList.tsx`
- `packages/web/src/components/EventFlow/EventItem.tsx`

### EventList Props

```typescript
{ events, isLoading?, emptyMessage?, className?, displayMode?, onDisplayModeChange? }
```

### Layout Drawing

```
┌──────────────────────────┐
│ [Phase|Stream] [Time ▾]  │
├──────────────────────────┤
│ ScrollArea (virtualized) │
│ ┌──────────────────────┐ │
│ │ ● agent_start        │ │
│ │   "Orchestrator"     │ │
│ ├──────────────────────┤ │
│ │ ● tool_call          │ │
│ │   "generate_html"    │ │
│ ├──────────────────────┤ │
│ │ ▸ generation_progress│ │
│ │   60% ████████░░     │ │
│ └──────────────────────┘ │
└──────────────────────────┘
```

### Logic

- Toolbar: 模式切换 (phase/streaming) + 时间过滤
- 使用 `useVirtualList` 虚拟列表优化性能
- EventItem 使用 `React.memo`, 映射 30+ 事件类型到标题、状态和徽章
- Tool 事件内联渲染, 其他使用 CollapsibleEvent 包装

---

## 11. 小型组件一览

| 组件 | 文件 | 尺寸 | 布局 | 用途 |
|---|---|---|---|---|
| **PageSelector** | `PageSelector.tsx` | 54 lines | 水平滚动按钮行 | 多页面切换 (≤1 页时隐藏) |
| **DataTab** | `DataTab.tsx` | Large | State/Events/Records 分区 + JSON viewer | 检查 iframe app-mode 数据 |
| **AestheticScoreCard** | `AestheticScoreCard.tsx` | Card | Gauge + 2列维度条 + 建议列表 | 显示美学评分 |
| **BuildStatusIndicator** | `BuildStatusIndicator.tsx` | Card | 进度条 + 状态 + 页面选择器 | 显示构建进度/结果 |
| **ImageThumbnail** | `ImageThumbnail.tsx` | 20×20 | 缩略图 + hover overlay + 删除按钮 | ChatInput 中的附件预览 |
| **AssetThumbnail** | `AssetThumbnail.tsx` | 24×24 | 缩略图 + 类型徽章 + 操作 | ChatMessage 中的资产预览 |
| **AssetTypeSelector** | `AssetTypeSelector.tsx` | Dialog | 2×2 网格 (logo/style_ref/background/product_image) | 上传前选择资产类型 |
| **PageMentionPopover** | `PageMentionPopover.tsx` | Popover | 固定位置过滤列表 | @mention 自动补全 |
| **TaskCard** | `TaskCard.tsx` | Card | 状态 + 标题 + 进度条 + token 分解 | 单任务展示 |
| **TaskCardList** | `TaskCardList.tsx` | List | 排序 + 虚拟化 TaskCard 列表 | 任务总览 |

---

## 12. Hooks 详解

### useChat (1292 lines)

**文件:** `packages/web/src/hooks/useChat.ts`

**输入:** `{ sessionId?, initialMessages?, messages?, setMessages?, onPreview?, onTabChange?, onPageSelect?, onSessionCreated? }`

**输出:** `{ messages, isStreaming, connectionState, error, assets, addAsset, removeAsset, getAssetById, uploadAsset, sendMessage, handleInterviewAction, stopStream, clearThread }`

**核心逻辑:** SSE 流式传输 (EventSource + fetch fallback), interview batch 处理, 资产上传, 产品文档事件, 构建事件, 页面事件。通过 CustomEvent 分发: `product-doc-event`, `page-event`, `aesthetic-score-event`, `build-event`, `multipage-decision-event`, `sitemap-event`。

### useSSE (412 lines)

**文件:** `packages/web/src/hooks/useSSE.ts`

**输出:** `{ events, isConnected, isLoading, isHistoryLoading, error, connectionState, connect, disconnect, clearEvents }`

**核心逻辑:** 事件去重 (via keys), requestAnimationFrame 批量刷新, 分页历史加载, 自动重连, 事件标准化。

### useSession (718 lines)

**文件:** `packages/web/src/hooks/useSession.ts`

**输出:** `{ session, messages, versions, isLoading, error, refresh, setMessages, setVersions, setSession }`

**核心逻辑:** 从 API 加载 session detail / messages / versions。解析消息中的 interview payloads (INTERVIEW_ANSWERS tags), 协调 interview summaries, 从 localStorage 应用存储的 interview batches, 应用 pending messages, 从 session events API 恢复 interview events。

### usePlan (258 lines)

**文件:** `packages/web/src/hooks/usePlan.ts`

**输出:** `{ plan, setPlan, updateTaskStatus, handleEvent, progress, tokenUsage }`

**核心逻辑:** 管理 plan 状态 (tasks with statuses), 处理 plan_created/plan_updated/task_* 事件, 按 task 和 agent 跟踪 token 使用, 计算进度百分比。

### useVersionPin

**文件:** `packages/web/src/hooks/useVersionPin.ts`

**输出:** `{ pin, unpin, isLoading }`

**核心逻辑:** 处理页面版本、快照和产品文档历史的 pin/unpin。409 时返回冲突信息 (pinned_limit_exceeded)。

### useAestheticScore

**文件:** `packages/web/src/hooks/useAestheticScore.ts`

**输出:** `{ score: AestheticScore | null }`

**核心逻辑:** 监听 useChat 分发的 `aesthetic-score-event` CustomEvent。按 session 持久化评分到 localStorage。

### useBuildStatus

**文件:** `packages/web/src/hooks/useBuildStatus.ts`

**输出:** `{ build: BuildState, isLoading, error, refresh, startBuild, cancelBuild, selectedPage, selectPage }`

**核心逻辑:** 监听 `build-event` CustomEvent。管理构建生命周期 (idle → pending → building → success/failed)。轮询构建状态 API。提供 startBuild/cancelBuild 操作。

### usePreviewBridge

**文件:** `packages/web/src/hooks/usePreviewBridge.ts`

**核心逻辑:** 监听 iframe 的 `instant-coffee:update` postMessage 事件。提供 state / events / records 数据给 DataTab。

---

## 13. 数据流总结

```
1. Chat 流:
   ChatInput → ChatPanel.onSendMessage → useChat.sendMessage
   → SSE stream → messages 更新 → ChatMessage 渲染响应
   (可选: InterviewWidget / disambiguation / action links)

2. Preview 流:
   useChat 接收 preview 事件 → ProjectPage.onPreview 回调
   → 设置 previewHtml/previewUrl → WorkbenchPanel → PreviewPanel → iframe

3. Multi-page 流:
   usePages 管理页面列表 → PageSelector 导航
   → loadPagePreview 获取 HTML → PreviewPanel 显示

4. App Mode 流:
   PreviewPanel 注入运行时脚本到 iframe
   → iframe 通过 postMessage 发送 state/events/records
   → usePreviewBridge 捕获 → DataTab 展示

5. Version 流:
   usePageVersions / useSnapshots / useProductDocHistory
   → VersionTimeline 展示 → pin/rollback/preview 操作

6. Build 流:
   useChat 分发 build-event CustomEvent → useBuildStatus 捕获
   → BuildStatusIndicator 显示进度
   → 成功后构建预览 URL → PreviewPanel 切换到 build 模式

7. Aesthetic Scoring 流:
   useChat 分发 aesthetic-score-event → useAestheticScore 捕获
   → PreviewPanel 在 Collapsible 中显示 AestheticScoreCard
```
