# Instant Coffee - 版本管理扩展 (Spec v0.4-VC2)

**项目名称**: Instant Coffee (速溶咖啡)
**版本**: v0.4-VC2 - 统一保留规则 + 快照回滚 + Product Doc 对比
**日期**: 2026-02-02
**文档类型**: Technical Specification Document (TSD)

---

## 文档变更历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v0.4-VC2 | 2026-02-02 | 重写：以快照为唯一回滚入口；统一 5+2 保留规则；Product Doc 允许历史查看与对比 | Planning |

---

## 1. 范围与原则

**范围**
- ProjectSnapshot（项目级快照，唯一回滚入口）
- PageVersion（页面版本，预览可用，禁止回滚）
- ProductDocHistory（产品文档历史，允许查看与对比）
- 统一保留规则（5 自动 + 2 pinned）

**不在本规范内**
- Session 级旧版本（`Version`）的继续扩展；仅作为兼容层存在
- 任务/计划/事件的版本化

**核心原则**
1. **回滚只发生在 ProjectSnapshot**，其他版本仅用于查看/对比/预览。
2. **版本内容不可变**，仅新增，不修改历史内容。
3. **统一保留规则**：所有版本类型都遵循相同的“可用窗口”。
4. **历史不可用**：超出窗口的版本只保留 metadata，不提供预览/回滚。
5. **Product Doc 例外**：released 的 Product Doc 仍可查看内容，但不可回滚。

---

## 2. 数据模型

### 2.1 ProductDoc（补充）

```
ProductDoc
├── id            (UUID, PK)
├── session_id    (FK → Session.id, Unique)
├── version       (int, 自增)
├── content       (TEXT, Markdown)
├── structured    (JSON)
├── status        (enum: draft / confirmed / outdated)
├── created_at    (datetime)
└── updated_at    (datetime)
```

### 2.2 ProductDocHistory（新增）

```
ProductDocHistory
├── id             (int, PK, auto)
├── product_doc_id (FK → ProductDoc.id)
├── version        (int)
├── content        (TEXT, Markdown)
├── structured     (JSON)
├── change_summary (TEXT)
├── source         (enum: auto / manual / rollback)
├── is_pinned      (bool)
├── is_released    (bool)
├── released_at    (datetime, nullable)
├── created_at     (datetime)
```

**规则**
- Product Doc 每次更新时，将旧版本写入 History。
- released 的 Product Doc 仍保留 `content` 用于查看与对比（但不可回滚）。

### 2.3 PageVersion（扩展）

```
PageVersion
├── id             (int, PK, auto)
├── page_id        (FK → Page.id)
├── version        (int)
├── html           (TEXT, 可为空; released 时可清空)
├── description    (string)
├── source         (enum: auto / manual / rollback)
├── is_pinned      (bool)
├── is_released    (bool)
├── released_at    (datetime, nullable)
├── payload_pruned_at (datetime, nullable)
├── created_at     (datetime)
```

**规则**
- PageVersion 只支持预览，不允许回滚。
- released 的 PageVersion 仅保留 metadata（html 清空）。

### 2.4 ProjectSnapshot（新增）

```
ProjectSnapshot
├── id               (UUID, PK)
├── session_id       (FK → Session.id)
├── snapshot_number  (int, 自增, session 内唯一)
├── label            (string, 可选)
├── source           (enum: auto / manual / rollback)
├── is_pinned        (bool)
├── is_released      (bool)
├── released_at      (datetime, nullable)
├── created_at       (datetime)
```

```
ProjectSnapshotDoc
├── snapshot_id      (FK → ProjectSnapshot.id)
├── content          (TEXT, Markdown)
├── structured       (JSON)
├── global_style     (JSON)
├── design_direction (JSON)
├── product_doc_version (int)
```

```
ProjectSnapshotPage
├── snapshot_id   (FK → ProjectSnapshot.id)
├── page_id       (FK → Page.id)
├── slug          (string)
├── title         (string)
├── order_index   (int)
├── rendered_html (TEXT)
```

**规则**
- 快照内容为“冻结内容”，不依赖 PageVersion 是否可用。
- released 的快照只保留 metadata（不含 doc/page content）。

---

## 3. 版本与回滚语义

### 3.1 统一保留规则（5 自动 + 2 pinned）

对 **所有版本类型**（ProductDocHistory / PageVersion / ProjectSnapshot）：

1) 取最近 5 个 `source=auto` 为“可用”。
2) 取最多 2 个 `is_pinned=true` 为“可用”（无论新旧）。
3) 其余标记为 `is_released=true`（历史不可用）。

**Pinned 超限处理**
- 当已存在 2 个 pinned，再 pin 新版本时：返回冲突信息，前端弹窗让用户选择释放哪一个 pinned。

### 3.2 ProjectSnapshot 回滚（唯一回滚入口）

回滚到快照时：
1. 读取快照冻结内容（Product Doc + Pages HTML）。
2. **创建新的 Product Doc 版本与 ProductDocHistory**。
3. **为每个页面创建新的 PageVersion**（html 来自快照）。
4. 创建新的 ProjectSnapshot（source=rollback），记录本次回滚。

**说明**
- 回滚不会复用旧 version_id，而是生成新版本。
- 回滚生成的新版本 `source=auto`，计入 5 自动窗口。

### 3.3 页面版本行为

- PageVersion 仅用于预览和历史查看，不提供回滚。
- released 版本不可预览，仅显示 metadata。

### 3.4 Product Doc 历史查看与对比

- 支持查看任意历史版本内容（包括 released）。
- 支持 **任意两版本 Markdown 内容对比**。
- 不提供回滚入口。

---

## 4. API 设计

### 4.1 Product Doc 历史与对比

| 端点 | 方法 | 功能 |
|------|------|------|
| `GET /api/sessions/{id}/product-doc/history` | GET | 列表（metadata + 可用性） |
| `GET /api/sessions/{id}/product-doc/history/{history_id}` | GET | 获取单个历史内容（Markdown） |
| `POST /api/sessions/{id}/product-doc/history/{history_id}/pin` | POST | Pin 历史版本 |
| `POST /api/sessions/{id}/product-doc/history/{history_id}/unpin` | POST | Unpin 历史版本 |

**说明**
- diff 在前端完成：选择两个 history_id，拉取内容后做 Markdown diff。

### 4.2 快照接口（唯一回滚入口）

| 端点 | 方法 | 功能 |
|------|------|------|
| `GET /api/sessions/{id}/snapshots` | GET | 获取快照列表（含可用性） |
| `POST /api/sessions/{id}/snapshots/{snapshot_id}/rollback` | POST | 回滚到快照 |
| `POST /api/sessions/{id}/snapshots/{snapshot_id}/pin` | POST | Pin 快照 |
| `POST /api/sessions/{id}/snapshots/{snapshot_id}/unpin` | POST | Unpin 快照 |

**GET /snapshots 响应示例**
```json
{
  "snapshots": [
    {
      "id": "uuid",
      "snapshot_number": 7,
      "label": "修改首页后",
      "source": "auto",
      "is_pinned": false,
      "is_released": false,
      "created_at": "..."
    }
  ]
}
```

### 4.3 PageVersion 接口（仅预览）

| 端点 | 方法 | 功能 |
|------|------|------|
| `GET /api/pages/{page_id}/versions` | GET | 列表（含可用性） |
| `GET /api/pages/{page_id}/versions/{version_id}/preview` | GET | 预览指定版本（仅非 released） |
| `POST /api/pages/{page_id}/versions/{version_id}/pin` | POST | Pin 版本 |
| `POST /api/pages/{page_id}/versions/{version_id}/unpin` | POST | Unpin 版本 |

**说明**
- 不提供 PageVersion rollback 端点。

---

## 5. 前端与交互

### 5.1 VersionPanel

- **Preview Tab**: 页面模式（PageVersion timeline，仅预览）
- **Code Tab**: 项目模式（ProjectSnapshot timeline，支持回滚）
- **Product Doc Tab**: ProductDocHistory timeline（查看 + diff）

**统一状态标识**
- released：置灰 + “历史不可用”，隐藏预览/回滚按钮
- pinned：高亮标记

### 5.2 Product Doc Diff

- 两个下拉选择框（左/右版本）
- Diff 仅对 Markdown content
- released 的 Product Doc 仍可查看与 diff

### 5.3 Pin 冲突

- 当 pinned 超过 2 个：弹窗让用户选择释放哪一个 pinned
- 确认释放后，再执行新的 pin

---

## 6. DB 变更与迁移方案

### 6.1 Schema 变更清单

**新增 / 修改字段**
- `product_docs.version`（int, default=1）
- `page_versions` 新增：`source`, `is_pinned`, `is_released`, `released_at`, `payload_pruned_at`

**新增表**
- `product_doc_histories`
- `project_snapshots`
- `project_snapshot_docs`
- `project_snapshot_pages`

**建议约束 / 索引**
- `product_doc_histories`: Unique(`product_doc_id`, `version`)
- `project_snapshots`: Unique(`session_id`, `snapshot_number`)
- `project_snapshot_pages`: Index(`snapshot_id`, `page_id`)

### 6.2 数据迁移步骤（建议顺序）

1) **新增字段与表结构**  
   - 先建表/列，再进行数据回填，避免阻塞已有流程。

2) **回填 Product Doc 版本**  
   - 所有已有 `product_docs` 设 `version=1`。  
   - 对已有 `product_docs` 生成首条 `product_doc_histories`（version=1, source=auto）。

3) **回填 PageVersion 新字段**  
   - 已有 `page_versions` 统一设定：  
     - `source=auto`  
     - `is_pinned=false`  
     - `is_released=false`

4) **为每个 Session 生成初始 ProjectSnapshot（可选但推荐）**  
   - 对有 `product_doc` + `pages` 的 session：  
     - 取当前 ProductDoc + 每页 current PageVersion 生成快照  
     - `snapshot_number=1`, `source=auto`, `label=“Initial import”`

5) **执行第一次保留规则计算**  
   - 对每个 session、每个版本类型（ProductDocHistory / PageVersion / ProjectSnapshot）  
   - 根据 “5 自动 + 2 pinned” 规则标记 `is_released`  
   - 需要 payload 清理的执行清理（见 6.3）

### 6.3 Released 数据清理策略

**通用规则**  
- released = 仅保留 metadata，禁止预览/回滚。

**具体清理**
- PageVersion：清空 `html`，设置 `payload_pruned_at`  
- ProjectSnapshot：删除 `project_snapshot_pages.rendered_html` 与 `project_snapshot_docs` 内容  
- ProductDocHistory：**例外**，released 仍保留 `content`（可查看/对比），但不回滚

### 6.4 兼容层说明

- 现有 Session 级 `Version` 仅用于兼容旧流程，不再扩展。  
- 新版本体系以 PageVersion + Snapshot 为主；回滚只走 Snapshot。  
- 旧 API 返回值需补充 `is_released` / `is_pinned` / `source` 字段以支持前端状态展示。

---

## 7. 验收标准

1. 回滚只能在快照层完成；PageVersion/ProductDocHistory 无回滚入口。
2. 每类版本遵循 5 自动 + 2 pinned 规则；released 仅 metadata（Product Doc 例外可查看内容）。
3. Product Doc 支持任意两版本 Markdown diff。
4. 超出窗口的历史版本无法预览/回滚，并显示“历史不可用”。
