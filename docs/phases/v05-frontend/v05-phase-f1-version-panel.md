# Phase v05-F1: VersionPanel 统一版本管理 UI

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v05-B1, v05-B2, v05-B3
  - **Blocks**: None

## Goal

重构 VersionPanel 组件，统一展示三类版本 (PageVersion, ProjectSnapshot, ProductDocHistory)，支持预览、回滚、Pin 等操作。

## Detailed Tasks

### Task 1: VersionPanel 三 Tab 结构

**Description**: 创建三个独立的 Tab 展示不同版本类型

**Implementation Details**:
- [ ] 创建 Preview Tab (PageVersion timeline)
- [ ] 创建 Code Tab (ProjectSnapshot timeline)
- [ ] 创建 Product Doc Tab (ProductDocHistory timeline)
- [ ] 实现 Tab 切换逻辑
- [ ] 保持状态在 Tab 间切换时不丢失

**Files to modify/create**:
- `packages/web/src/components/custom/VersionPanel.tsx`

**Acceptance Criteria**:
- [ ] 三个 Tab 正确展示
- [ ] Tab 切换流畅
- [ ] 各 Tab 独立状态管理

---

### Task 2: 版本列表组件

**Description**: 创建统一的版本列表展示组件

**Implementation Details**:
- [ ] 创建 VersionTimeline 组件
- [ ] 支持显示版本元数据 (version, source, created_at)
- [ ] 显示可用性状态 (available, is_pinned, is_released)
- [ ] 版本项操作按钮 (Preview, View, Pin, Unpin, Rollback)
- [ ] Released 版本置灰处理
- [ ] Pinned 版本高亮显示

**Files to modify/create**:
- `packages/web/src/components/custom/VersionTimeline.tsx` (新建)

**Acceptance Criteria**:
- [ ] 版本列表正确展示
- [ ] 状态标识清晰
- [ ] 操作按钮根据状态显示/隐藏

---

### Task 3: PageVersion 预览功能

**Description**: 实现 PageVersion 预览入口和展示

**Implementation Details**:
- [ ] 添加 View 按钮到版本项
- [ ] 点击后调用 GET /api/pages/{page_id}/versions/{version_id}/preview
- [ ] 在 PreviewPanel 或模态框中展示预览
- [ ] Released 版本禁用预览
- [ ] 预览不改变当前页面内容

**Files to modify/create**:
- `packages/web/src/components/custom/VersionPanel.tsx`
- `packages/web/src/components/custom/PreviewPanel.tsx`

**Acceptance Criteria**:
- [ ] View 按钮正确触发预览
- [ ] 预览显示完整 HTML
- [ ] Released 版本无法预览
- [ ] 预览不影响当前页面

---

### Task 4: ProjectSnapshot 回滚入口

**Description**: 实现从快照回滚的功能

**Implementation Details**:
- [ ] 仅在 Code Tab (ProjectSnapshot) 显示 Rollback 按钮
- [ ] 点击后调用 POST /api/sessions/{id}/snapshots/{snapshot_id}/rollback
- [ ] 回滚前显示确认对话框
- [ ] 显示将恢复的快照信息
- [ ] 回滚成功后刷新页面状态
- [ ] 回滚后显示新生成的 rollback 快照

**Files to modify/create**:
- `packages/web/src/components/custom/VersionPanel.tsx`

**Acceptance Criteria**:
- [ ] Rollback 按钮仅在 Code Tab 显示
- [ ] 确认对话框显示正确信息
- [ ] 回滚成功后状态更新
- [ ] 生成新的 rollback 快照

---

### Task 5: Pin/Unpin 功能

**Description**: 实现三类版本的 Pin/Unpin 操作

**Implementation Details**:
- [ ] 添加 Pin 按钮到版本项
- [ ] Pinned 版本显示 Unpin 按钮
- [ ] 调用对应 Pin API
  - PageVersion: POST /api/pages/{page_id}/versions/{version_id}/pin
  - ProjectSnapshot: POST /api/sessions/{id}/snapshots/{snapshot_id}/pin
  - ProductDocHistory: POST /api/sessions/{id}/product-doc/history/{history_id}/pin
- [ ] 处理 pinned 超限错误 (409 Conflict)
- [ ] 超限时显示选择对话框

**Files to modify/create**:
- `packages/web/src/components/custom/VersionPanel.tsx`
- `packages/web/src/hooks/useVersionPin.ts` (新建)

**Acceptance Criteria**:
- [ ] Pin 操作正确调用 API
- [ ] Pinned 状态正确更新
- [ ] 超限时显示选择对话框
- [ ] 对话框选择后正确执行释放和 Pin

---

### Task 6: Pin 冲突对话框

**Description**: 创建 Pin 超限时选择释放的对话框

**Implementation Details**:
- [ ] 创建 PinnedLimitDialog 组件
- [ ] 显示当前已 pinned 的版本列表
- [ ] 用户选择要释放的版本
- [ ] 确认后先 Unpin 选中的版本
- [ ] 然后 Pin 新版本
- [ ] 处理错误和重试

**Files to modify/create**:
- `packages/web/src/components/custom/PinnedLimitDialog.tsx` (新建)

**Acceptance Criteria**:
- [ ] 对话框显示当前 pinned 列表
- [ ] 选择释放后正确执行操作
- [ ] 错误正确处理

---

### Task 7: 状态标识样式

**Description**: 统一版本状态的视觉标识

**Implementation Details**:
- [ ] Released 状态: 置灰 + "历史不可用" 标签
- [ ] Pinned 状态: 高亮/图标 + "已固定" 标签
- [ ] Available 状态: 默认显示
- [ ] Source 标识: auto/manual/rollback 图标或标签
- [ ] Tooltip 显示状态说明

**Files to modify/create**:
- `packages/web/src/components/custom/VersionPanel.tsx`
- `packages/web/src/components/custom/VersionTimeline.tsx`

**Acceptance Criteria**:
- [ ] 状态清晰可识别
- [ ] 样式一致
- [ ] Tooltip 提供说明

## Technical Specifications

### 组件结构

```tsx
<VersionPanel>
  <Tabs>
    <Tab label="Preview">
      <VersionTimeline
        versions={pageVersions}
        type="page"
        actions={['view', 'pin']}
      />
    </Tab>
    <Tab label="Code">
      <VersionTimeline
        versions={snapshots}
        type="snapshot"
        actions={['rollback', 'pin']}
      />
    </Tab>
    <Tab label="Product Doc">
      <VersionTimeline
        versions={productDocHistory}
        type="productDoc"
        actions={['view', 'diff', 'pin']}
      />
    </Tab>
  </Tabs>
</VersionPanel>
```

### API 调用

```typescript
// 新增 hooks
const useSnapshots = (sessionId: string) => {...}
const useProductDocHistory = (sessionId: string) => {...}
const usePageVersions = (pageId: string) => {...} // 扩展
const useVersionPin = () => {...}
```

### 类型定义

```typescript
interface VersionItem {
  id: string | number;
  version: number;
  source: 'auto' | 'manual' | 'rollback';
  is_pinned: boolean;
  is_released: boolean;
  created_at: string;
  available: boolean;
}

interface PageVersionItem extends VersionItem {
  description: string;
  previewable: boolean;
}

interface SnapshotItem extends VersionItem {
  snapshot_number: number;
  label: string | null;
  page_count: number;
}

interface ProductDocHistoryItem extends VersionItem {
  change_summary: string;
}
```

## Testing Requirements

- [ ] 组件测试: Tab 切换
- [ ] 组件测试: 版本列表渲染
- [ ] 组件测试: Pin/Unpin 操作
- [ ] 集成测试: 预览功能
- [ ] 集成测试: 回滚功能
- [ ] E2E 测试: 完整版本管理流程

## Notes & Warnings

1. **回滚仅限快照**: 只有 Code Tab 的 ProjectSnapshot 可以回滚
2. **预览不影响当前**: 预览不修改当前页面内容
3. **Pin 限制**: 三类版本各自独立计算 2 个 pinned 限制
4. **Released 清空**: Released 版本可能无法预览 (html 已清空)
