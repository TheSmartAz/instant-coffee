# Phase v05-F3: API Client 扩展 - 新增 API 端点

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Low
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: v05-F1, v05-F2, v05-F4

## Goal

扩展 API Client，添加所有新的 REST API 端点支持，包括快照、历史版本、事件查询等。

## Detailed Tasks

### Task 1: ProjectSnapshot API

**Description**: 添加快照相关的 API 方法

**Implementation Details**:
- [ ] getSnapshots(sessionId) - 获取快照列表
- [ ] getSnapshot(snapshotId) - 获取单个快照
- [ ] createSnapshot(sessionId, label) - 手动创建快照
- [ ] rollbackToSnapshot(sessionId, snapshotId) - 回滚
- [ ] pinSnapshot(snapshotId) - Pin
- [ ] unpinSnapshot(snapshotId) - Unpin

**Files to modify/create**:
- `packages/web/src/api/client.ts`

**Acceptance Criteria**:
- [ ] 所有快照 API 正确实现
- [ ] 请求/响应类型正确
- [ ] 错误处理完整

---

### Task 2: ProductDoc History API

**Description**: 添加产品文档历史相关的 API 方法

**Implementation Details**:
- [ ] getProductDocHistory(sessionId) - 获取历史列表
- [ ] getProductDocHistoryVersion(sessionId, historyId) - 获取单个历史
- [ ] pinProductDocHistory(sessionId, historyId) - Pin
- [ ] unpinProductDocHistory(sessionId, historyId) - Unpin

**Files to modify/create**:
- `packages/web/src/api/client.ts`

**Acceptance Criteria**:
- [ ] 所有历史 API 正确实现
- [ ] 类型定义正确

---

### Task 3: PageVersion API 扩展

**Description**: 扩展页面版本相关的 API 方法

**Implementation Details**:
- [ ] getPageVersions(pageId) - 已有，添加 include_released 参数
- [ ] previewPageVersion(pageId, versionId) - 预览版本 (新增)
- [ ] pinPageVersion(pageId, versionId) - Pin (新增)
- [ ] unpinPageVersion(pageId, versionId) - Unpin (新增)
- [ ] 移除或标记 rollbackPageVersion 为废弃

**Files to modify/create**:
- `packages/web/src/api/client.ts`

**Acceptance Criteria**:
- [ ] 新增 API 正确实现
- [ ] 旧 rollback API 标记废弃

---

### Task 4: Session Events API

**Description**: 添加历史事件查询的 API 方法

**Implementation Details**:
- [ ] getSessionEvents(sessionId, sinceSeq, limit) - 获取历史事件
- [ ] 支持增量查询
- [ ] 返回按 seq 排序的事件列表

**Files to modify/create**:
- `packages/web/src/api/client.ts`

**Acceptance Criteria**:
- [ ] 事件查询 API 正确实现
- [ ] sinceSeq 过滤正确

---

### Task 5: TypeScript 类型定义

**Description**: 为所有新 API 添加类型定义

**Implementation Details**:
- [ ] ProjectSnapshot 类型
- [ ] ProductDocHistory 类型
- [ ] PageVersion 扩展类型
- [ ] SessionEvent 类型
- [ ] API 请求/响应类型

**Files to modify/create**:
- `packages/web/src/types/index.ts`
- `packages/web/src/types/events.ts`

**Acceptance Criteria**:
- [ ] 所有类型正确定义
- [ ] 导出/导入正确

## Technical Specifications

### API Client 方法

```typescript
// ProjectSnapshot
interface SnapshotAPI {
  getSnapshots(sessionId: string): Promise<Snapshot[]>;
  getSnapshot(snapshotId: string): Promise<Snapshot>;
  createSnapshot(sessionId: string, label?: string): Promise<Snapshot>;
  rollbackToSnapshot(sessionId: string, snapshotId: string): Promise<RollbackResult>;
  pinSnapshot(snapshotId: string): Promise<Snapshot>;
  unpinSnapshot(snapshotId: string): Promise<Snapshot>;
}

// ProductDocHistory
interface ProductDocHistoryAPI {
  getHistory(sessionId: string): Promise<ProductDocHistory[]>;
  getHistoryVersion(sessionId: string, historyId: number): Promise<ProductDocHistory>;
  pinHistory(sessionId: string, historyId: number): Promise<ProductDocHistory>;
  unpinHistory(sessionId: string, historyId: number): Promise<ProductDocHistory>;
}

// PageVersion
interface PageVersionAPI {
  getVersions(pageId: string, includeReleased?: boolean): Promise<PageVersion[]>;
  previewVersion(pageId: string, versionId: number): Promise<PageVersionPreview>;
  pinVersion(pageId: string, versionId: number): Promise<PageVersion>;
  unpinVersion(pageId: string, versionId: number): Promise<PageVersion>;
  // rollbackVersion - 已移除
}

// SessionEvents
interface EventsAPI {
  getSessionEvents(sessionId: string, sinceSeq?: number, limit?: number): Promise<SessionEvent[]>;
}
```

### 类型定义

```typescript
// 版本管理基础类型
interface VersionMetadata {
  is_pinned: boolean;
  is_released: boolean;
  source: 'auto' | 'manual' | 'rollback';
  created_at: string;
  available: boolean;
}

// ProjectSnapshot
interface ProjectSnapshot extends VersionMetadata {
  id: string;
  session_id: string;
  snapshot_number: number;
  label: string | null;
  page_count: number;
}

// ProductDocHistory
interface ProductDocHistory extends VersionMetadata {
  id: number;
  product_doc_id: string;
  version: number;
  content: string;
  structured: Record<string, unknown>;
  change_summary: string;
}

// PageVersion
interface PageVersion extends VersionMetadata {
  id: number;
  page_id: string;
  version: number;
  description: string;
  fallback_used: boolean;
  previewable: boolean;
}

// SessionEvent
interface SessionEvent {
  id: number;
  session_id: string;
  seq: number;
  type: string;
  payload: Record<string, unknown>;
  source: 'session' | 'plan' | 'task';
  created_at: string;
}
```

## Testing Requirements

- [ ] 单元测试: API 方法正确构造请求
- [ ] 单元测试: 响应正确解析
- [ ] 类型测试: 类型检查通过
- [ ] 集成测试: API 调用成功

## Notes & Warnings

1. **向后兼容**: 保持现有 API 方法不变
2. **类型安全**: 确保 TypeScript 类型正确
3. **错误处理**: 统一错误处理格式
4. **废弃标记**: rollbackPageVersion 应标记为 @deprecated
