# Phase F3: History & Export Commands

## Metadata

- **Category**: Frontend (CLI)
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: F1 (CLI Framework), B2 (Session Management), B4 (Export Service)
  - **Blocks**: None

## Goal

Implement history viewing, session continuation, rollback, and export commands with formatted output and interactive selection.

## Detailed Tasks

### Task 1: Implement History Command

**Description**: Build command to list all sessions with formatted table display.

**Implementation Details**:
- [ ] Create history command
- [ ] Fetch sessions from API
- [ ] Display as formatted table
- [ ] Show session ID, title, timestamps, version count
- [ ] Support pagination (--limit, --offset)
- [ ] Add filtering options (--date, --search)

**Files to modify/create**:
- `packages/cli/src/commands/history.ts`

**Acceptance Criteria**:
- [ ] Sessions are displayed in readable table format
- [ ] Most recent sessions appear first
- [ ] Timestamps are formatted in local timezone
- [ ] Pagination works correctly

---

### Task 2: Implement Session Detail View

**Description**: Build command to view detailed session information.

**Implementation Details**:
- [ ] Accept session ID as argument
- [ ] Fetch session details and messages
- [ ] Display conversation history
- [ ] Show version list with descriptions
- [ ] Highlight current version

**Files to modify/create**:
- `packages/cli/src/commands/history/detail.ts`

**Acceptance Criteria**:
- [ ] Full conversation is displayed
- [ ] Versions are listed with descriptions
- [ ] Current version is clearly marked
- [ ] Handles non-existent sessions gracefully

---

### Task 3: Implement Rollback Command

**Description**: Build command to rollback to previous versions.

**Implementation Details**:
- [ ] Accept session ID and version number
- [ ] Confirm with user before rollback
- [ ] Call rollback API
- [ ] Display success message with new preview URL
- [ ] Auto-open browser with rolled-back version

**Files to modify/create**:
- `packages/cli/src/commands/rollback.ts`

**Acceptance Criteria**:
- [ ] Rollback confirmation prompt works
- [ ] Successfully rolls back to specified version
- [ ] Preview URL is updated
- [ ] Browser opens with rolled-back version

---

### Task 4: Implement Export Command

**Description**: Build command to export sessions to filesystem.

**Implementation Details**:
- [ ] Accept session ID and optional output path
- [ ] Support exporting specific version (--version)
- [ ] Create output directory if needed
- [ ] Call export API
- [ ] Display success message with file path
- [ ] Optionally open exported file

**Files to modify/create**:
- `packages/cli/src/commands/export.ts`

**Acceptance Criteria**:
- [ ] Exports to specified directory
- [ ] Can export specific versions
- [ ] Creates directories if needed
- [ ] Displays absolute file path
- [ ] Handles permission errors

---

### Task 5: Implement Clean Command

**Description**: Build command to clean cache and temporary files.

**Implementation Details**:
- [ ] Clear temporary session data
- [ ] Optionally clear all sessions (--all flag)
- [ ] Confirm before destructive operations
- [ ] Display cleanup summary

**Files to modify/create**:
- `packages/cli/src/commands/clean.ts`

**Acceptance Criteria**:
- [ ] Safely cleans temporary data
- [ ] Confirmation prompt for --all flag
- [ ] Displays what was cleaned
- [ ] Doesn't delete user's exported files

## Technical Specifications

### History Command Output

```bash
$ instant-coffee history

最近的会话:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ID      | 标题            | 创建时间              | 最后修改            | 版本
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
abc123  | 活动报名页面     | 2025-01-30 14:15     | 2025-01-30 14:23   | v1
def456  | 个人作品集       | 2025-01-30 10:30     | 2025-01-30 10:45   | v2
ghi789  | 产品介绍页       | 2025-01-29 16:20     | 2025-01-29 16:35   | v0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

提示: 使用 instant-coffee chat --continue <ID> 继续会话
```

### Session Detail Output

```bash
$ instant-coffee history abc123

会话详情: 活动报名页面 (abc123)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

创建时间: 2025-01-30 14:15:22
最后修改: 2025-01-30 14:23:45

对话历史 (8 条消息):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[14:15] 你: 帮我做一个活动报名页面

[14:15] AI: 好的！我想了解几个细节：
           1️⃣ 活动类型是什么？...

[14:16] 你: 线下聚会，需要姓名电话和备注...
...

版本历史:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v1 (当前) | 调整了按钮大小        | 2025-01-30 14:23
v0        | 初始生成              | 2025-01-30 14:15
```

### Rollback Command

```bash
$ instant-coffee rollback abc123 v0

⚠️  确定要回滚到版本 v0 吗？这将更新当前版本。
   (当前版本: v1, 目标版本: v0)

? 继续? (y/N) y

✅ 已回滚到版本 v0
📂 预览: file:///Users/.../instant-coffee-output/index.html

(自动打开浏览器)
```

### Export Command

```bash
$ instant-coffee export abc123 --output ./my-website

✅ 已导出到: /Users/username/my-website/
   ├── index.html

会话: abc123 (活动报名页面)
版本: v1 (当前版本)
```

## Testing Requirements

- [ ] Test history listing with multiple sessions
- [ ] Test session detail view
- [ ] Test rollback with confirmation
- [ ] Test export to various paths
- [ ] Test clean command
- [ ] Test error handling (invalid session IDs)

## Notes & Warnings

- **Timestamps**: Display in user's local timezone
- **Confirmation**: Always confirm before destructive operations (rollback, clean --all)
- **Table Formatting**: Use chalk-table or similar for consistent table rendering
- **Long Titles**: Truncate long session titles for table display
- **Export Path**: Support both relative and absolute paths
- **Clean Command**: Be very careful not to delete user data
