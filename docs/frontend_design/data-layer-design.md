# App Data Layer 设计

## 背景

用户通过 Chat 创建 app 时，Generation Agent 会根据场景自动定义数据模型（如电商 app 的 Order/MenuItem/Customer）。用户在 Preview 中交互时，操作会写入对应的数据表。Data Tab 提供表格视图和看板视图来展示这些数据。

## 现状

### 已有

- `schemas/scenario.py` — Entity-Relationship 数据模型定义（per 产品类型）
- `services/data_protocol.py` — 注入 iframe JS 运行时
- `services/skills/contracts/*.json` — 按产品类型的 state contract
- `utils/product_doc.py` — 生成 `data-store.js` / `data-client.js`
- 前端 `usePreviewBridge` + `DataTab` — 通过 postMessage 读取 iframe 数据

### 缺失

- 服务端数据持久化（目前全部在 browser localStorage）
- 动态建表（data_model 定义了 Entity/Field 但未物化）
- CRUD API
- data_model 与 state_contract 未关联

---

## 存储方案：PostgreSQL Schema 隔离

### 部署环境

- **Railway** — 使用 Railway PostgreSQL 插件
- 系统表和 app 数据共用同一个 PG 实例

### 结构

```
PostgreSQL (Railway)
  ├── public schema (系统表)
  │     ├── sessions
  │     ├── messages
  │     ├── versions
  │     ├── pages
  │     ├── product_docs
  │     └── ...
  │
  ├── app_<session_id> schema (餐厅 app)
  │     ├── "Order"
  │     ├── "MenuItem"
  │     └── "Customer"
  │
  └── app_<session_id> schema (看板 app)
        ├── "Board"
        ├── "Column"
        └── "Task"
```

### 为什么用 PG Schema 而不是其他方案

| 维度 | Per-session SQLite | PG Schema 隔离 | 单表 JSONB |
|---|---|---|---|
| 动态建表 | 可以，但多文件管理 | `CREATE TABLE` 在 schema 内，干净 | 不需要建表，但查询弱 |
| 查询能力 | 基础 SQL | 窗口函数/CTE/JSONB 索引，Dashboard 聚合直接受益 | 需要应用层聚合 |
| 隔离 | 天然文件隔离 | `DROP SCHEMA CASCADE` 一键清理 | 需要 WHERE session_id = ... |
| 并发 | 写锁问题 | 无问题 | 无问题 |
| 部署 | Railway 不适合文件存储 | Railway PG 插件原生支持 | 同左 |
| 连接管理 | 每 session 一个连接 | 一个连接池，`SET search_path` 切换 | 同一个表 |

---

## 类型映射

```python
# data_model Entity field.type → PostgreSQL column type
TYPE_MAP = {
    "string": "TEXT",
    "number": "NUMERIC",
    "boolean": "BOOLEAN",
    "array": "JSONB",
    "object": "JSONB",
}
```

---

## 后端新增

### 1. `app/services/app_data_store.py` — 核心服务

```python
class AppDataStore:
    """管理 per-session 的 app 数据表"""

    async def create_schema(self, session_id: str) -> str:
        """创建 session 专属 schema"""

    async def create_tables(self, session_id: str, data_model: DataModel):
        """根据 data_model.entities 动态建表"""

    async def drop_schema(self, session_id: str):
        """删除 session 时清理 schema"""

    async def insert_record(self, session_id: str, table: str, data: dict) -> dict:
        """写入一条记录"""

    async def query_table(self, session_id: str, table: str,
                          limit: int = 50, offset: int = 0,
                          order_by: str = None) -> dict:
        """查询表数据（分页）"""

    async def get_table_stats(self, session_id: str, table: str) -> dict:
        """聚合统计（count, sum, group by 等）"""

    async def list_tables(self, session_id: str) -> list:
        """列出 schema 内所有表及其列定义"""
```

### 2. `app/api/data.py` — CRUD API

```
GET    /sessions/{id}/data/tables           列出所有表 + 列定义
GET    /sessions/{id}/data/{table}          查询表记录（分页）
POST   /sessions/{id}/data/{table}          写入记录
DELETE /sessions/{id}/data/{table}/{row_id} 删除记录
GET    /sessions/{id}/data/{table}/stats    聚合统计
```

### 3. 集成点

```
Generation 流程:
  GenerationAgent 生成 HTML
    → DataProtocolGenerator 注入 JS
    → AppDataStore.create_tables() 根据 data_model 建表  ← 新增

iframe JS Runtime:
  用户交互 → window.IC.cart.add() 等
    → 改为调 POST /sessions/{id}/data/{table}  ← 替代 localStorage
    → 同时 postMessage 通知父窗口（保持实时性）

Session 删除:
  DELETE /sessions/{id}
    → AppDataStore.drop_schema()  ← 新增清理
```

---

## 前端改动

### Data Tab 提升为顶级 Tab

```
WorkbenchPanel (改动前):
  [Preview] [Code] [Product Doc]
      ↓
  PreviewPanel 内部 toggle: [Preview | Data]

WorkbenchPanel (改动后):
  [Preview] [Code] [Product Doc] [Data]  ← 同级
```

### Data Tab 两种视图

```
┌──────────────────────────────────────────┐
│ [Table 视图] [Dashboard 视图]  toggle     │
├──────────────────────────────────────────┤
│                                          │
│  === Table 视图 ===                       │
│  ┌─ 表选择 ─────────────────────────┐    │
│  │ [Order] [MenuItem] [Customer]    │    │
│  └──────────────────────────────────┘    │
│  ┌──┬──────────┬────────┬──────────┐    │
│  │id│ items    │ total  │ status   │    │
│  ├──┼──────────┼────────┼──────────┤    │
│  │1 │ [...]    │ 128.00 │ pending  │    │
│  │2 │ [...]    │ 45.50  │ done     │    │
│  └──┴──────────┴────────┴──────────┘    │
│  [< 1 2 3 >]  共 45 条                   │
│                                          │
│  === Dashboard 视图 ===                   │
│  ┌──────────┐ ┌──────────┐              │
│  │ Orders   │ │ Revenue  │              │
│  │   45     │ │ ¥3,280   │              │
│  └──────────┘ └──────────┘              │
│  ┌──────────────────────────────┐       │
│  │ Status 分布 (饼图/柱状图)     │       │
│  └──────────────────────────────┘       │
│                                          │
└──────────────────────────────────────────┘
```

### 新增 Hook

```typescript
// hooks/useAppData.ts
function useAppData(sessionId: string) {
  return {
    tables,          // 表列表 + 列定义
    activeTable,     // 当前选中的表
    records,         // 当前表的记录（分页）
    stats,           // 当前表的聚合统计
    isLoading,
    selectTable,     // 切换表
    refreshTable,    // 刷新数据
    pagination,      // { page, pageSize, total }
  }
}
```

### 数据源切换

```
改动前:
  iframe postMessage → usePreviewBridge → DataTab (raw JSON)

改动后:
  iframe JS runtime → POST API → PostgreSQL
  Data Tab → GET API → 结构化表格/看板展示
  iframe postMessage → 仅用于实时通知 Data Tab 刷新
```

---

## Railway 部署注意

- Railway PostgreSQL 插件提供 `DATABASE_URL` 环境变量
- 连接数限制：Starter plan 约 20 连接，需要连接池（asyncpg pool 或 PgBouncer）
- 存储限制：Starter plan 1GB，app 数据量小，足够
- Schema 数量无硬限制，但建议定期清理已删除 session 的 schema
- Railway 无持久文件系统，确认 per-session SQLite 方案不可行，PG 是正确选择
