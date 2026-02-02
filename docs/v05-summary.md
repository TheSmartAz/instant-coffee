# Version 0.5 Implementation Summary

## Overview

**Version**: v0.5 - Unified Version Management + Responses API + Stability Fixes
**Status**: Complete
**Start Date**: 2026-02-02
**Completion Date**: 2026-02-02

## Implementation Progress

### Database Phases

| Phase ID | Name | Status | Completed Date |
|----------|------|--------|----------------|
| v05-D1 | Database Model Expansion - Version Management | Complete | 2026-02-02 |

### Backend Phases

| Phase ID | Name | Status | Completed Date |
|----------|------|--------|----------------|
| v05-B1 | ProjectSnapshot Service | Complete | 2026-02-02 |
| v05-B2 | ProductDoc History Service | Complete | 2026-02-02 |
| v05-B3 | PageVersion Service | Complete | 2026-02-02 |
| v05-B4 | EventStore Service | Complete | 2026-02-02 |
| v05-B5 | Responses API Migration | Complete | 2026-02-02 |
| v05-B6 | Stability Fixes | Complete | 2026-02-02 |

### Frontend Phases

| Phase ID | Name | Status | Completed Date |
|----------|------|--------|----------------|
| v05-F1 | VersionPanel Unified Version UI | Complete | 2026-02-02 |
| v05-F2 | ProductDoc Diff UI | Complete | 2026-02-02 |
| v05-F3 | API Client Expansion | Complete | 2026-02-02 |
| v05-F4 | Event Recovery + SSE Merge | Complete | 2026-02-02 |

---

## Completed Phases Details

### v05-D1: Database Model Expansion - Version Management

**Implementation Date**: 2026-02-02

**Files Modified/Created**:
- `packages/backend/app/db/models.py` - Added versioning enums, ProductDocHistory, ProjectSnapshot, SessionEvent, and PageVersion fields
- `packages/backend/app/db/migrations.py` - Added v05 migration helpers, SQLite rebuild for page_versions, and data backfills
- `packages/backend/app/db/__init__.py` - Exported new models and migration helper
- `packages/backend/app/services/product_doc.py` - Increment ProductDoc version on updates

**Features Implemented**:
- ProductDoc version field with session+version unique constraint
- ProductDocHistory table with versioning metadata and created_at index
- ProjectSnapshot tables (snapshot, doc, pages) with cascade delete
- PageVersion fields for source/pinned/released/fallback tracking and nullable html
- SessionEvent table for persistent event storage
- Idempotent data backfills for ProductDocHistory and PageVersion defaults
- SQLite-safe rebuild of page_versions to drop NOT NULL on html

**Acceptance Criteria Met**:
- [x] ProductDoc.version exists with default 1
- [x] Existing ProductDoc rows backfilled to version 1
- [x] ProductDoc version increments on updates
- [x] ProductDocHistory table created with constraints and index
- [x] ProjectSnapshot tables created with constraints and index
- [x] PageVersion new fields added with default backfill
- [x] html column allows NULL for released cleanup
- [x] SessionEvent table created with session+seq index

### v05-B3: PageVersion Service

**Implementation Date**: 2026-02-02

**Files Modified/Created**:
- `packages/backend/app/services/page_version.py` - Preview/pin/unpin/retention + rollback removal
- `packages/backend/app/api/pages.py` - Preview + pin/unpin endpoints + released handling
- `packages/backend/app/schemas/page.py` - Expanded version payload fields
- `packages/backend/app/api/sessions.py` - PageVersion rollback returns 410 for index-page sessions
- `packages/backend/tests/test_page_services.py` - Preview + retention tests
- `packages/backend/tests/test_pages_api.py` - Preview 410 + pin/unpin limit tests
- `packages/web/src/pages/ProjectPage.tsx` - Session rollback routed to ProjectSnapshot
- `packages/web/src/components/custom/VersionPanel.tsx` - Removed page rollback UI flow
- `packages/web/src/hooks/usePageVersions.ts` - Removed page rollback hook

**Features Implemented**:
- Version preview endpoint with released/410 handling
- Version list includes source/pinned/released/available/previewable flags
- Pin/Unpin with per-page limit (2) and retention interaction
- Retention policy keeps latest 5 auto + up to 2 pinned + current version; releases/prunes others
- PageVersion rollback deprecated (410); ProjectSnapshot rollback remains supported

**Acceptance Criteria Met**:
- [x] 预览返回完整 HTML 内容
- [x] Released 版本不可预览
- [x] 预览不影响当前页面
- [x] 不存在版本返回 404
- [x] 版本列表包含完整状态信息
- [x] Released 版本可选择性显示
- [x] Available 状态正确计算
- [x] Pin/Unpin 正常工作 + 超限提示
- [x] 保留规则清理 released payload
- [x] 回滚端点拒绝请求（410）

### v05-B6: Stability Fixes

**Implementation Date**: 2026-02-02

**Files Modified/Created**:
- `packages/backend/app/agents/generation.py` - HTML strict retry + fallback tracking
- `packages/backend/app/generators/mobile_html.py` - Fallback excerpt helper
- `packages/backend/app/services/page_version.py` - Persist fallback fields + fallback stats
- `packages/backend/app/api/chat.py` - Request-disconnect abort handling
- `packages/backend/app/api/sessions.py` - Fallback diagnostics API
- `packages/backend/app/executor/parallel.py` - Timeout cleanup + abort handling + trace IDs
- `packages/backend/app/services/task.py` - Timeout cleanup service + status handling
- `packages/backend/app/db/models.py` - Added TaskStatus.TIMEOUT
- `packages/backend/app/config.py` - Task timeout configuration
- `packages/backend/app/exceptions.py` - Tracked error types
- `packages/web/src/types/events.ts`, `packages/web/src/types/plan.ts` - New task statuses
- `packages/web/src/components/TaskCard/TaskCard.tsx` - Timeout/aborted UI states
- `packages/web/src/components/TaskCard/TaskCardList.tsx` - Status ordering
- `packages/web/src/components/Todo/TodoItem.tsx` - Timeout/aborted UI states
- `packages/web/src/components/Todo/TodoPanel.tsx` - Timeout indicator
- `packages/web/src/hooks/usePlan.ts` - Timeout status mapping + progress calc

**Features Implemented**:
- Strict HTML extraction retry (max 3) with lower temperature and hard prompts
- Fallback tracking: `fallback_used` and `fallback_excerpt` persisted to PageVersion
- Fallback diagnostics API: `GET /api/sessions/{session_id}/fallbacks`
- Request disconnect aborts active plans + cancels executor tasks
- Timeout cleanup loop for stale in-progress tasks (default 30m)
- Error tracing via trace_id in task error messages
- Frontend UI/type alignment for `timeout` and `aborted` statuses

**Acceptance Criteria Met**:
- [x] HTML 抽取失败时自动重试（更严格提示 + 降温）
- [x] fallback_used 与 fallback_excerpt 持久化并可诊断
- [x] 请求取消触发 abort，in_progress 不会卡死
- [x] 超时任务自动标记 timeout 并记录原因
- [x] 错误日志包含 trace_id

### v05-B1: ProjectSnapshot Service

**Implementation Date**: 2026-02-02

**Files Modified/Created**:
- `packages/backend/app/services/project_snapshot.py` - Snapshot service create/list/get/rollback/pin/retention
- `packages/backend/app/executor/parallel.py` - Auto snapshot on successful plan completion
- `packages/backend/app/api/snapshots.py` - Snapshot REST API routes
- `packages/backend/app/api/__init__.py` - Router registration
- `packages/backend/app/main.py` - Router inclusion
- `packages/backend/tests/test_project_snapshot_service.py` - Snapshot service unit tests

**Features Implemented**:
- Snapshot create/list/get with per-session snapshot_number auto increment
- Snapshot capture of ProductDoc + page HTML payloads
- Rollback creates new ProductDocHistory + PageVersion records and new rollback snapshot
- Pin/unpin with 2-item pinned limit and conflict handling
- Retention policy: keep 5 auto + up to 2 pinned, release others and prune payloads
- Auto snapshot creation on plan completion (only when all tasks succeed)

**Acceptance Criteria Met**:
- [x] 创建快照时生成唯一 snapshot_number
- [x] 快照包含当前 ProductDoc 和所有 Pages 的冻结内容
- [x] 快照列表返回可用/释放状态
- [x] 创建/回滚流程事务保护（失败回滚）
- [x] Plan 全部成功时自动生成快照
- [x] Plan 有失败页面时不生成快照
- [x] Pin 超限返回 409 Conflict

### v05-B5: Responses API Migration

**Implementation Date**: 2026-02-02

**Files Modified/Created**:
- `packages/backend/app/llm/openai_client.py` - Added Responses API create/stream/tool calling, delta + usage parsing, tool output continuation
- `packages/backend/app/config.py` - Added `OPENAI_API_MODE`, DMXAPI base/key env fallbacks
- `packages/backend/app/agents/base.py` - Switched LLM calls to Responses with chat.completions fallback
- `packages/backend/app/agents/interview.py` - Streamed interview calls
- `packages/backend/app/agents/refinement.py` - Streamed refinement calls
- `packages/backend/app/planner/openai_planner.py` - Responses endpoint support for planner
- `packages/backend/tests/test_responses_api.py` - Responses API unit coverage

**Features Implemented**:
- Unified Responses API usage for non-stream, stream, and tool calling
- Streaming delta parsing from `response.output_text.delta`
- Tool-call parsing + local tool execution + responses continuation
- Usage mapping to TokenUsage with raw usage capture
- Config switch for Responses vs chat.completions (compat layer retained)
- DMXAPI-compatible base_url/api_key env fallbacks

**Acceptance Criteria Met**:
- [x] responses_create 返回完整 LLMResponse
- [x] responses_stream 正确 yield delta
- [x] responses_with_tools 解析 tool-call 事件并执行工具
- [x] Usage 统计正确映射 + raw 保存
- [x] SSE 事件格式保持不变（前端无需修改）

### v05-B2: ProductDoc History Service

**Implementation Date**: 2026-02-02

**Files Modified/Created**:
- `packages/backend/app/services/product_doc.py` - History creation/query/pin/unpin/retention + version diff helpers
- `packages/backend/app/api/product_doc.py` - History list/detail/pin/unpin endpoints
- `packages/backend/app/schemas/product_doc.py` - History response schemas
- `packages/backend/app/exceptions.py` - PinnedLimitExceeded exception
- `packages/backend/app/services/project_snapshot.py` - Apply retention policy after rollback history creation

**Features Implemented**:
- ProductDoc update auto-creates history records with version increment
- History list/detail APIs with include_released filter and metadata
- Pin/Unpin with max 2 pinned entries and 409 conflict on limit
- Retention policy keeps 5 latest auto versions + up to 2 pinned, others marked released (content retained)
- Diff metadata helper available (backend returns two versions, frontend diffs)

**Acceptance Criteria Met**:
- [x] ProductDoc 更新时自动创建历史记录
- [x] Version 号正确递增
- [x] Source 正确设置
- [x] 历史列表按版本倒序
- [x] Released 版本默认过滤
- [x] Pin/Unpin 限制与 409 返回
- [x] Retention policy 应用并保留 content

### v05-B4: EventStore Service

**Implementation Date**: 2026-02-02

**Files Modified/Created**:
- `packages/backend/app/services/event_store.py` - SessionEvent persistence, seq generation, structured filtering
- `packages/backend/app/events/types.py` - Structured/excluded event type lists
- `packages/backend/app/api/chat.py` - EventStore integration for SSE + commit on stream end
- `packages/backend/app/api/events.py` - Session events REST API
- `packages/backend/app/api/__init__.py` - Router registration
- `packages/backend/app/main.py` - Router inclusion
- `packages/backend/app/events/emitter.py` - Safer event type logging

**Features Implemented**:
- Persist structured SSE events into `session_events` with per-session seq
- Whitelist-based storage with explicit exclusion of delta/thinking/ping
- Per-session in-process lock to avoid seq collisions
- Session events query with since_seq/limit + pagination flags
- Chat SSE integration that persists events without blocking stream on failures

**Acceptance Criteria Met**:
- [x] 事件成功写入 session_events 表
- [x] Seq 在 session 内单调递增
- [x] Delta 事件不被存储
- [x] 并发写入不会导致 seq 重复
- [x] 历史事件按 seq 顺序返回
- [x] since_seq 正确过滤
- [x] SSE 发送不被数据库错误阻塞

### v05-F3: API Client Expansion

**Implementation Date**: 2026-02-02

**Files Modified/Created**:
- `packages/web/src/api/client.ts` - Added REST API methods for snapshots, product doc history, page versions (preview/pin/unpin), and session events
- `packages/web/src/types/index.ts` - Added v05 versioning types (ProjectSnapshot, ProductDocHistory, PageVersionRecord, responses)
- `packages/web/src/types/events.ts` - Added SessionEvent types and response shape

**Features Implemented**:
- ProjectSnapshot list/get/create/rollback/pin/unpin client methods
- ProductDoc history list/get/pin/unpin client methods
- PageVersion list with include_released, preview, pin/unpin, rollback marked deprecated
- Session events query with since_seq and limit

**Acceptance Criteria Met**:
- [x] All snapshot APIs implemented
- [x] ProductDoc history APIs implemented
- [x] PageVersion APIs expanded (preview/pin/unpin + include_released)
- [x] Session events query implemented
- [x] Type definitions added and exported

### v05-F4: Event Recovery + SSE Merge

**Implementation Date**: 2026-02-02

**Files Modified/Created**:
- `packages/web/src/hooks/useSSE.ts` - Historical event loading, merge/dedupe, and plan replay
- `packages/web/src/hooks/useSession.ts` - Interview batch reconstruction from session events
- `packages/web/src/hooks/useChat.ts` - Interview state rehydration from recovered messages
- `packages/web/src/components/custom/InterviewWidget.tsx` - Restore active question on refresh
- `packages/web/src/components/custom/ChatMessage.tsx` - Render historical interview batches
- `packages/web/src/components/EventFlow/EventList.tsx` - Time filters + restored history display
- `packages/web/src/components/EventFlow/EventItem.tsx` - New event type rendering
- `packages/web/src/types/events.ts` - Extended event typing (interview/version/snapshot)
- `packages/web/src/pages/ExecutionPage.tsx` - Pass sessionId to SSE hook
- `packages/web/src/pages/ProjectPage.tsx` - Pass sessionId to SSE hook

**Features Implemented**:
- Historical events fetched on load and merged with realtime SSE (seq-aware ordering + dedupe)
- History replayed into plan handler so EventList/Task UI restore on refresh
- Interview batches reconstructed from `interview_question`/`interview_answer` events
- Interview widget shows historical Q&A and restores current question index
- Event list supports time filtering and history display
- Delta/thinking/ping remain realtime-only and are not recovered

**Acceptance Criteria Met**:
- [x] 历史事件在页面加载时自动获取
- [x] 事件按正确顺序排列并去重
- [x] 刷新后 Interview 问答可见（有 interview 事件时）
- [x] 刷新后事件列表可见（历史 + 实时合并）
- [x] Delta 刷新后不恢复

**Notes / Deviations**:
- Interview 恢复依赖后端发出 `interview_question`/`interview_answer` 事件；缺少时仅保留 localStorage 回填。

### v05-F2: ProductDoc Diff UI

**Implementation Date**: 2026-02-02

**Files Modified/Created**:
- `packages/web/src/components/custom/VersionDiffSelector.tsx` - Version picker with current/released/pinned metadata and duplicate protection
- `packages/web/src/components/custom/MarkdownDiffViewer.tsx` - Markdown diff rendering with side-by-side/unified modes
- `packages/web/src/hooks/useProductDocDiff.ts` - Parallel loading for selected versions
- `packages/web/src/components/custom/ProductDocPanel.tsx` - Compare button + dialog integration
- `packages/web/package.json` - Added diff dependency

**Features Implemented**:
- Version comparison dialog embedded in ProductDoc panel
- Left/right version selection with current + released versions included
- Line-level diff rendering with added/removed highlights
- View mode toggle (side-by-side/unified) with localStorage persistence
- Parallel loading of diff contents with error/loading states

**Acceptance Criteria Met**:
- [x] 两个选择框独立工作
- [x] 版本列表正确加载（含 released）
- [x] 相同版本被禁用
- [x] Diff 正确显示
- [x] 添加/删除清晰可辨
- [x] 两种视图正常工作

### v05-F1: VersionPanel Unified Version UI

**Implementation Date**: 2026-02-02

**Files Modified/Created**:
- `packages/web/src/components/custom/VersionPanel.tsx` - Rebuilt into 3-tab unified version manager with preview/rollback/pin flows
- `packages/web/src/components/custom/VersionTimeline.tsx` - Unified timeline list with status badges + actions
- `packages/web/src/components/custom/PinnedLimitDialog.tsx` - Pin conflict resolution dialog
- `packages/web/src/hooks/useSnapshots.ts` - Snapshot list hook
- `packages/web/src/hooks/useProductDocHistory.ts` - ProductDoc history list hook
- `packages/web/src/hooks/useVersionPin.ts` - Shared pin/unpin + conflict handling hook
- `packages/web/src/hooks/usePageVersions.ts` - Added includeReleased support
- `packages/web/src/pages/ProjectPage.tsx` - VersionPanel props updated

**Features Implemented**:
- Unified VersionPanel with Preview / Code / Product Doc tabs (independent state)
- PageVersion timeline with preview + pin/unpin (released/unavailable disabled)
- ProjectSnapshot timeline with rollback + pin/unpin and confirmation dialog
- ProductDocHistory timeline with view + pin/unpin; modal viewer for historical doc content
- Pinned limit handling (409) with selection dialog to release + pin
- Status badges for pinned/released/source with tooltips

**Acceptance Criteria Met**:
- [x] 三个 Tab 正确展示 + 状态不丢失
- [x] 版本列表统一展示 + 元数据/状态清晰
- [x] View 预览入口展示 HTML（Released 禁用）
- [x] Snapshot 回滚入口 + 确认对话框 + 刷新列表
- [x] Pin/Unpin 支持三类版本 + 超限处理对话框
- [x] 状态标识样式统一 + Tooltip

**Notes / Deviations**:
- ProductDoc “Diff” 动作为占位提示（由 v05-F2 实现完整 diff UI）。
- Released 状态标签区分了“已释放(可用)”与“历史不可用(不可用)”，以反映 available 字段。
