# Phase v05-D1: 数据库模型扩展 - 版本管理体系

## Metadata

- **Category**: Database
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: v05-B1, v05-B2, v05-B3, v05-B4

## Goal

扩展数据库模型以支持统一版本管理体系，包括 ProjectSnapshot、ProductDocHistory 和 PageVersion 扩展，实现 5 自动 + 2 pinned 的保留规则。

## Detailed Tasks

### Task 1: ProductDoc 模型扩展

**Description**: 为 ProductDoc 表添加 version 字段支持版本自增

**Implementation Details**:
- [ ] 添加 `version` 字段 (int, 默认 1)
- [ ] 添加版本唯一约束 (session_id, version)
- [ ] 为现有数据回填 version=1
- [ ] 添加迁移脚本

**Files to modify/create**:
- `packages/backend/app/db/models.py` - ProductDoc 模型
- `packages/backend/app/db/migrations.py` - 迁移脚本

**Acceptance Criteria**:
- [ ] ProductDoc.version 字段存在且默认值为 1
- [ ] 现有数据成功回填 version=1
- [ ] 新创建的 ProductDoc 自动递增 version

---

### Task 2: ProductDocHistory 新建

**Description**: 创建 ProductDocHistory 表用于存储产品文档历史版本

**Implementation Details**:
- [ ] 创建 ProductDocHistory 表
- [ ] 定义字段: id (PK auto), product_doc_id (FK), version, content (TEXT), structured (JSON), change_summary (TEXT)
- [ ] 添加 source 字段 (enum: auto/manual/rollback)
- [ ] 添加 is_pinned, is_released 字段
- [ ] 添加 released_at (nullable datetime)
- [ ] 添加 created_at 索引
- [ ] 创建 Unique(product_doc_id, version) 约束

**Files to modify/create**:
- `packages/backend/app/db/models.py` - ProductDocHistory 模型
- `packages/backend/app/db/migrations.py` - 迁移脚本

**Acceptance Criteria**:
- [ ] ProductDocHistory 表创建成功
- [ ] 外键关系正确建立
- [ ] 唯一约束生效
- [ ] 索引创建完成

---

### Task 3: ProjectSnapshot 系列表新建

**Description**: 创建项目快照相关表，作为唯一回滚入口

**Implementation Details**:
- [ ] 创建 ProjectSnapshot 表
  - id (UUID, PK)
  - session_id (FK)
  - snapshot_number (int, 自增)
  - label (string, nullable)
  - source (enum: auto/manual/rollback)
  - is_pinned, is_released (bool)
  - released_at (nullable datetime)
  - created_at
- [ ] 创建 ProjectSnapshotDoc 表 (1:1 关联)
  - snapshot_id (FK)
  - content, structured, global_style, design_direction (JSON)
  - product_doc_version (int)
- [ ] 创建 ProjectSnapshotPage 表
  - snapshot_id (FK), page_id (FK)
  - slug, title, order_index (int)
  - rendered_html (TEXT)
- [ ] 创建 Unique(session_id, snapshot_number) 约束
- [ ] 创建 Index(snapshot_id, page_id)

**Files to modify/create**:
- `packages/backend/app/db/models.py` - 快照模型
- `packages/backend/app/db/migrations.py` - 迁移脚本

**Acceptance Criteria**:
- [ ] 三张快照表创建成功
- [ ] 外键关系正确建立
- [ ] 唯一约束和索引生效

---

### Task 4: PageVersion 模型扩展

**Description**: 为 PageVersion 添加版本管理相关字段

**Implementation Details**:
- [ ] 添加 source 字段 (enum: auto/manual/rollback)
- [ ] 添加 is_pinned, is_released (bool)
- [ ] 添加 released_at (nullable datetime)
- [ ] 添加 payload_pruned_at (nullable datetime)
- [ ] 添加 fallback_used (bool)
- [ ] 添加 fallback_excerpt (TEXT, nullable)
- [ ] 回填现有数据: source=auto, is_pinned=false, is_released=false, fallback_used=false

**Files to modify/create**:
- `packages/backend/app/db/models.py` - PageVersion 模型
- `packages/backend/app/db/migrations.py` - 迁移脚本

**Acceptance Criteria**:
- [ ] PageVersion 新字段全部添加成功
- [ ] 现有数据成功回填默认值
- [ ] html 字段允许为空 (released 时可清空)

---

### Task 5: SessionEvent 新建

**Description**: 创建 SessionEvent 表用于持久化 SSE 结构化事件

**Implementation Details**:
- [ ] 创建 SessionEvent 表
  - id (int, PK, auto)
  - session_id (FK)
  - seq (int, 单调递增)
  - type (string)
  - payload (JSON)
  - source (enum: session/plan/task)
  - created_at (datetime)
- [ ] 创建 Index(session_id, seq)

**Files to modify/create**:
- `packages/backend/app/db/models.py` - SessionEvent 模型
- `packages/backend/app/db/migrations.py` - 迁移脚本

**Acceptance Criteria**:
- [ ] SessionEvent 表创建成功
- [ ] seq 索引创建成功
- [ ] 外键关系正确建立

---

### Task 6: 数据回填迁移

**Description**: 为现有数据生成初始历史记录和快照

**Implementation Details**:
- [ ] 为现有 ProductDoc 创建初始 ProductDocHistory (version=1, source=auto)
- [ ] 为现有 PageVersion 回填新字段默认值
- [ ] 为每个 session 生成初始 ProjectSnapshot (可选)
- [ ] 验证回填数据完整性

**Files to modify/create**:
- `packages/backend/app/db/migrations.py` - 数据回填迁移

**Acceptance Criteria**:
- [ ] 现有 ProductDoc 都有对应 History 记录
- [ ] 现有 PageVersion 字段回填完成
- [ ] 迁移可重复执行 (幂等性)

## Technical Specifications

### 表结构变更

#### ProductDoc 扩展
```sql
ALTER TABLE product_docs ADD COLUMN version INTEGER DEFAULT 1;
CREATE UNIQUE INDEX idx_product_doc_session_version ON product_docs(session_id, version);
```

#### ProductDocHistory
```sql
CREATE TABLE product_doc_histories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_doc_id UUID NOT NULL REFERENCES product_docs(id),
    version INTEGER NOT NULL,
    content TEXT,
    structured JSON,
    change_summary TEXT,
    source VARCHAR(10) NOT NULL DEFAULT 'auto' CHECK(source IN ('auto', 'manual', 'rollback')),
    is_pinned BOOLEAN DEFAULT FALSE,
    is_released BOOLEAN DEFAULT FALSE,
    released_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_doc_id, version)
);
```

#### ProjectSnapshot
```sql
CREATE TABLE project_snapshots (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions(id),
    snapshot_number INTEGER NOT NULL,
    label VARCHAR(255),
    source VARCHAR(10) NOT NULL DEFAULT 'auto' CHECK(source IN ('auto', 'manual', 'rollback')),
    is_pinned BOOLEAN DEFAULT FALSE,
    is_released BOOLEAN DEFAULT FALSE,
    released_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, snapshot_number)
);

CREATE TABLE project_snapshot_docs (
    snapshot_id UUID PRIMARY KEY REFERENCES project_snapshots(id) ON DELETE CASCADE,
    content TEXT,
    structured JSON,
    global_style JSON,
    design_direction JSON,
    product_doc_version INTEGER
);

CREATE TABLE project_snapshot_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id UUID NOT NULL REFERENCES project_snapshots(id) ON DELETE CASCADE,
    page_id UUID NOT NULL REFERENCES pages(id),
    slug VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    order_index INTEGER NOT NULL,
    rendered_html TEXT
);
CREATE INDEX idx_snapshot_page ON project_snapshot_pages(snapshot_id, page_id);
```

#### PageVersion 扩展
```sql
ALTER TABLE page_versions ADD COLUMN source VARCHAR(10) DEFAULT 'auto' CHECK(source IN ('auto', 'manual', 'rollback'));
ALTER TABLE page_versions ADD COLUMN is_pinned BOOLEAN DEFAULT FALSE;
ALTER TABLE page_versions ADD COLUMN is_released BOOLEAN DEFAULT FALSE;
ALTER TABLE page_versions ADD COLUMN released_at TIMESTAMP;
ALTER TABLE page_versions ADD COLUMN payload_pruned_at TIMESTAMP;
ALTER TABLE page_versions ADD COLUMN fallback_used BOOLEAN DEFAULT FALSE;
ALTER TABLE page_versions ADD COLUMN fallback_excerpt TEXT;
```

#### SessionEvent
```sql
CREATE TABLE session_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    type VARCHAR(100) NOT NULL,
    payload JSON,
    source VARCHAR(10) CHECK(source IN ('session', 'plan', 'task')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_session_event_seq ON session_events(session_id, seq);
```

### 保留规则数据约束

- 最多 5 个 source=auto 的非 released 版本
- 最多 2 个 is_pinned=true 的版本
- pinned 可与 auto 窗口重叠
- released 版本清空大字段内容

## Testing Requirements

- [ ] 单元测试: 模型字段验证
- [ ] 迁移测试: 新表创建成功
- [ ] 数据完整性测试: 外键约束验证
- [ ] 回填测试: 现有数据正确迁移

## Notes & Warnings

1. **版本不可变**: 历史记录创建后不可修改，只能新增
2. **级联删除**: ProjectSnapshot 删除时应级联删除关联的 Doc 和 Page
3. **seq 单调性**: SessionEvent.seq 必须保证单调递增，考虑数据库序列或锁
4. **JSON 字段**: SQLite JSON 操作需要特殊处理，使用 JSON_EXTRACT
5. **大字段清理**: released 版本的 html/content 清理需要后台任务支持
