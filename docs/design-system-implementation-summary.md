# Design System Implementation Summary

> Historical/current mix note (2026-05-13): this summary records earlier web design-system work. Verify current component files in `packages/web/src/components/ui` and current layout in `docs/frontend_design/project_page.md`.

更新时间：2026-01-31

## 完成情况概览

### Phase 1: Foundation
- ✅ 已完成（项目基础、设计 tokens、核心 shadcn 组件）

### Phase 2: Additional shadcn Components
- ✅ 已完成（textarea/select/slider/label/switch/dialog/alert-dialog/toast/sonner/dropdown-menu/tabs/badge/skeleton）

### Phase 3: Custom Components
- ✅ 已完成（PhoneFrame / ProjectCard / ChatMessage / ChatInput / VersionTimeline / ChatPanel / PreviewPanel / VersionPanel）

### Phase 4: Page Layouts
- ✅ 已完成（Routing + HomePage / ProjectPage / SettingsPage）

### Phase 5: State Management & API Integration
- ✅ 已完成基础接入（API client + hooks + 页面接入）
- ✅ Preview/Version 数据流已补全（支持 preview_html / preview_url）
- ✅ SSE 事件消费与执行流组件已实现（布局整合属于 F3 扩展内容）

### Phase 6: Polish & Optimization
- 🟡 部分完成（基础 loading/error/toast/animations/a11y/离线提示已落地，仍需系统性完善）

---

## 关键实现摘要

### API 与 Hooks
- 新增 `packages/web/src/api/client.ts`：统一请求与错误处理
- 新增 hooks：`useProjects` / `useSession` / `useChat` / `useSettings`
- 新增类型：`packages/web/src/types/index.ts`
- 新增 `useSSE`（执行流事件消费）：`packages/web/src/hooks/useSSE.ts`

### Preview/Version 数据流
- 预览支持两类来源：
  - `preview_html`（优先使用，使用 `srcDoc` 渲染）
  - `preview_url`（次优先，使用 `iframe src` 渲染）
- 数据流路径：
  1) 初始 session 拉取预览（`useSession` → `ProjectPage`）
  2) SSE / chat 结果更新预览（`useChat` → `ProjectPage`）
  3) 版本选择与回滚时更新预览（`VersionPanel` → `ProjectPage`）

### 页面状态
- HomePage：从 `/api/sessions` 拉取项目列表；支持创建
- ProjectPage：从 `/api/sessions/:id` + `/messages` + `/versions` 拉取数据
- SettingsPage：从 `/api/settings` 拉取并更新

### Phase 6 已落地项（基础）
- Toast 全局提示与错误反馈（`<Toaster />` + action 错误触发）
- 离线提示横幅（online/offline 监听）
- 基础动画（ChatMessage 进入动画）
- 基础可访问性（键盘可点击 ProjectCard、按钮 aria-label、设置页 aria-current）
- Version 回滚加载态与 skeleton 占位
- Chat 列表 skeleton 与空状态提示
- Preview 刷新/导出按钮加载态与提示
- Settings 页面 skeleton + 保存成功提示
- 页面级淡入动画（Home / Project / Settings）
- ProjectCard 图片 lazy loading
- Chat/Event/Task 列表虚拟滚动（窗口化渲染）

### SSE 执行流（Phase F2）
- 事件类型定义：`packages/web/src/types/events.ts`
- SSE 连接与重连：`packages/web/src/hooks/useSSE.ts`
- 执行流 UI：`packages/web/src/components/EventFlow/*`
- ProjectPage 集成 Events Tab：`packages/web/src/pages/ProjectPage.tsx`

### Todo 面板（Phase F3）
- Plan 类型：`packages/web/src/types/plan.ts`
- Plan 状态管理：`packages/web/src/hooks/usePlan.ts`
- Todo 组件：`packages/web/src/components/Todo/*`
- 执行流布局：`packages/web/src/components/Layout/MainContent.tsx`
- 执行流页面：`packages/web/src/pages/ExecutionPage.tsx`
- Task actions 已接入 API：`packages/web/src/api/client.ts`

### Task Card 视图（Phase F4）
- TaskCard 组件：`packages/web/src/components/TaskCard/TaskCard.tsx`
- AgentActivity 组件：`packages/web/src/components/TaskCard/AgentActivity.tsx`
- ToolCallLog 组件：`packages/web/src/components/TaskCard/ToolCallLog.tsx`
- TaskCardList 组件：`packages/web/src/components/TaskCard/TaskCardList.tsx`

---

## 仍需补齐（建议顺序）

1) Phase 6：系统性完善 loading/error/animations/a11y/perf（含更完整的 loading/error 状态覆盖）
2) F4 Task Card 视图（根据 `docs/phases/frontend/v02-phase-f4-*`）
3) Preview/Version 后端字段确认（若 versions 返回 preview_url/preview_html，可直接对接）

---

## 关联文件（新增/关键修改）

- `packages/web/src/api/client.ts`
- `packages/web/src/types/index.ts`
- `packages/web/src/hooks/useProjects.ts`
- `packages/web/src/hooks/useSession.ts`
- `packages/web/src/hooks/useChat.ts`
- `packages/web/src/hooks/useSettings.ts`
- `packages/web/src/components/custom/PreviewPanel.tsx`
- `packages/web/src/components/custom/ChatMessage.tsx`
- `packages/web/src/components/custom/ProjectCard.tsx`
- `packages/web/src/components/custom/VersionPanel.tsx`
- `packages/web/src/components/custom/VersionTimeline.tsx`
- `packages/web/src/pages/HomePage.tsx`
- `packages/web/src/pages/ProjectPage.tsx`
- `packages/web/src/App.tsx`
- `packages/web/src/hooks/useOnlineStatus.ts`
- `packages/web/src/components/custom/ChatPanel.tsx`
- `packages/web/src/hooks/useSSE.ts`
- `packages/web/src/types/events.ts`
- `packages/web/src/components/EventFlow/EventList.tsx`
- `packages/web/src/components/EventFlow/EventItem.tsx`
- `packages/web/src/components/EventFlow/StatusIcon.tsx`
- `packages/web/src/components/EventFlow/ProgressBar.tsx`
- `packages/web/src/components/EventFlow/CollapsibleEvent.tsx`
- `packages/web/src/types/plan.ts`
- `packages/web/src/hooks/usePlan.ts`
- `packages/web/src/components/Todo/TodoItem.tsx`
- `packages/web/src/components/Todo/TodoPanel.tsx`
- `packages/web/src/components/Todo/index.ts`
- `packages/web/src/components/Layout/MainContent.tsx`
- `packages/web/src/pages/ExecutionPage.tsx`
- `packages/web/src/components/TaskCard/TaskCard.tsx`
- `packages/web/src/components/TaskCard/AgentActivity.tsx`
- `packages/web/src/components/TaskCard/ToolCallLog.tsx`
- `packages/web/src/components/TaskCard/TaskCardList.tsx`
- `packages/web/src/components/TaskCard/index.ts`
- `packages/web/src/hooks/useVirtualList.ts`
- `packages/web/src/pages/SettingsPage.tsx`
