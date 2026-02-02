# Phase v05-F2: ProductDoc Diff UI - 产品文档对比

## Metadata

- **Category**: Frontend
- **Priority**: P1 (Important)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v05-B2
  - **Blocks**: None

## Goal

实现 ProductDoc 任意两版本的 Markdown 内容对比功能，支持版本选择和并排/统一 diff 展示。

## Detailed Tasks

### Task 1: 版本选择器

**Description**: 创建用于选择两个对比版本的选择器

**Implementation Details**:
- [ ] 创建 VersionDiffSelector 组件
- [ ] 两个下拉选择框 (左版本 / 右版本)
- [ ] 加载 ProductDocHistory 列表
- [ ] 显示版本号和 change_summary
- [ ] 支持选择 "当前版本"
- [ ] 防止选择相同版本

**Files to modify/create**:
- `packages/web/src/components/custom/VersionDiffSelector.tsx` (新建)

**Acceptance Criteria**:
- [ ] 两个选择框独立工作
- [ ] 版本列表正确加载
- [ ] 相同版本被禁用或提示

---

### Task 2: Markdown Diff 渲染

**Description**: 实现两版本 Markdown 内容的 diff 渲染

**Implementation Details**:
- [ ] 选择 diff 库 (如 react-diff-viewer 或 diff2html)
- [ ] 创建 MarkdownDiffViewer 组件
- [ ] 支持并排视图 (side-by-side)
- [ ] 支持统一视图 (unified)
- [ ] 高亮显示差异行
- [ ] 添加/删除行用不同颜色标识

**Files to modify/create**:
- `packages/web/src/components/custom/MarkdownDiffViewer.tsx` (新建)

**Acceptance Criteria**:
- [ ] Diff 正确显示
- [ ] 添加/删除清晰可辨
- [ ] 两种视图正常工作

---

### Task 3: 版本内容加载

**Description**: 加载指定版本的内容进行对比

**Implementation Details**:
- [ ] 创建 useProductDocDiff hook
- [ ] 调用 GET /api/sessions/{id}/product-doc/history/{history_id}
- [ ] 并行加载两个版本内容
- [ ] 处理加载状态
- [ ] 处理错误状态

**Files to modify/create**:
- `packages/web/src/hooks/useProductDocDiff.ts` (新建)

**Acceptance Criteria**:
- [ ] 两版本并行加载
- [ ] 加载状态正确显示
- [ ] 错误正确处理

---

### Task 4: Diff 视图切换

**Description**: 实现并排/统一 diff 视图切换

**Implementation Details**:
- [ ] 添加视图切换按钮
- [ ] 并排视图: 左右两栏对比
- [ ] 统一视图: 上下对比
- [ ] 记住用户偏好 (localStorage)
- [ ] 响应式适配

**Files to modify/create**:
- `packages/web/src/components/custom/MarkdownDiffViewer.tsx`

**Acceptance Criteria**:
- [ ] 两种视图正确切换
- [ ] 用户偏好正确保存
- [ ] 移动端适配

---

### Task 5: ProductDocPanel 集成

**Description**: 将 Diff 功能集成到 ProductDocPanel

**Implementation Details**:
- [ ] 在 ProductDocPanel 添加 "Compare" 按钮
- [ ] 点击打开 Diff 模态框或抽屉
- [ ] 传递当前版本和历史版本列表
- [ ] Diff 完成后关闭并返回

**Files to modify/create**:
- `packages/web/src/components/custom/ProductDocPanel.tsx`

**Acceptance Criteria**:
- [ ] Compare 按钮正确打开 Diff
- [ ] Diff 在模态框/抽屉中显示
- [ ] 操作流畅

---

### Task 6: Released 版本 Diff

**Description**: 确保 Released 版本也可参与对比

**Implementation Details**:
- [ ] 版本选择器包含 released 版本
- [ ] Released 版本标识清晰
- [ ] Released 版本内容正确加载
- [ ] Diff 正常工作

**Files to modify/create**:
- `packages/web/src/components/custom/VersionDiffSelector.tsx`

**Acceptance Criteria**:
- [ ] Released 版本可选
- [ ] 标识清晰
- [ ] Diff 正常工作

## Technical Specifications

### 组件结构

```tsx
<ProductDocPanel>
  {/* 现有内容 */}
  <Button onClick={openDiff}>Compare Versions</Button>

  <DiffModal isOpen={showDiff} onClose={closeDiff}>
    <VersionDiffSelector
      versions={history}
      left={leftVersion}
      right={rightVersion}
      onChange={setVersions}
    />
    <MarkdownDiffViewer
      leftContent={leftContent}
      rightContent={rightContent}
      viewMode={viewMode} // 'side-by-side' | 'unified'
    />
  </DiffModal>
</ProductDocPanel>
```

### API 调用

```typescript
const useProductDocDiff = (sessionId: string) => {
  const loadVersion = (historyId: number) =>
    api.get(`/sessions/${sessionId}/product-doc/history/${historyId}`);

  const loadDiff = (leftId: number, rightId: number) =>
    Promise.all([
      loadVersion(leftId),
      loadVersion(rightId)
    ]);

  return { loadDiff, ... };
};
```

### 类型定义

```typescript
interface DiffVersion {
  id: number;
  version: number;
  content: string;
  change_summary: string;
  is_released: boolean;
  is_pinned: boolean;
}

interface DiffProps {
  left: DiffVersion;
  right: DiffVersion;
  viewMode?: 'side-by-side' | 'unified';
}
```

## Testing Requirements

- [ ] 组件测试: 版本选择器
- [ ] 组件测试: Diff 渲染
- [ ] 组件测试: 视图切换
- [ ] 集成测试: Diff 功能完整流程
- [ ] E2E 测试: Released 版本 Diff

## Notes & Warnings

1. **Released 仍可查看**: ProductDocHistory released 后仍保留内容，可 diff
2. **性能考虑**: 大文档 diff 可能较慢，考虑分页或懒加载
3. **Markdown 渲染**: Diff 后可能需要重新渲染 Markdown
4. **移动端**: 并排视图在移动端可能自动切换到统一视图
