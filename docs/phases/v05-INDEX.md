# Project Breakdown Index - v0.5

## Overview

本索引文档组织 **Spec v0.5** 的所有开发阶段，按类别 (Frontend、Backend、Database) 分类，支持多团队并行开发。

## Frontend Phases

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| v05-F1 | VersionPanel 统一版本管理 UI (Complete) | P0 | High | ⚠️ | v05-B1, v05-B2, v05-B3 | - |
| v05-F2 | ProductDoc Diff UI (Complete) | P1 | Medium | ⚠️ | v05-B2 | - |
| v05-F3 | API Client 扩展 (Complete) | P0 | Low | ✅ | - | v05-F1, v05-F2, v05-F4 |
| v05-F4 | 事件恢复与 SSE 合并 (Complete) | P0 | High | ⚠️ | v05-B4, v05-F3 | - |

## Backend Phases

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| v05-B1 | ProjectSnapshot 服务 (Complete) | P0 | High | ⚠️ | v05-D1 | v05-F1 |
| v05-B2 | ProductDoc 历史服务 (Complete) | P0 | Medium | ⚠️ | v05-D1 | v05-F1, v05-F2 |
| v05-B3 | PageVersion 服务 (Complete) | P0 | Medium | ⚠️ | v05-D1 | v05-F1 |
| v05-B4 | EventStore 服务 (Complete) | P0 | High | ⚠️ | v05-D1 | v05-F4 |
| v05-B5 | Responses API 迁移 (Complete) | P0 | High | ✅ | - | v05-B6 |
| v05-B6 | 稳定性修复 (Complete) | P0 | Medium | ✅ | - | - |

## Database Phases

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| v05-D1 | 数据库模型扩展 - 版本管理体系 (Complete) | P0 | Medium | ✅ | - | v05-B1, v05-B2, v05-B3, v05-B4 |

## Dependency Graph

```
v05-D1 (数据库模型扩展)
 ├─> v05-B1 (ProjectSnapshot 服务) ─┐
 ├─> v05-B2 (ProductDoc 历史) ───────┤
 ├─> v05-B3 (PageVersion 服务) ──────┼─> v05-F1 (VersionPanel)
 └─> v05-B4 (EventStore 服务) ───────┘       └─> v05-F2 (ProductDoc Diff)
                                            │
v05-B5 (Responses API) ─> v05-B6 (稳定性)   │
                                            │
v05-F3 (API Client) ─┬──────────────────────┘
                     └─> v05-F4 (事件恢复, Complete) <─┘
```

## Development Strategy

### Wave 1 - 立即开始 (无依赖):

```
v05-D1: 数据库模型扩展 (Complete)
v05-B5: Responses API 迁移 (Complete)
v05-B6: 稳定性修复 (Complete)
v05-F3: API Client 扩展 (Complete)
```

### Wave 2 - D1 和 F3 完成后:

```
v05-B1: ProjectSnapshot 服务 (Complete)
v05-B2: ProductDoc 历史服务 (Complete)
v05-B3: PageVersion 服务 (Complete)
v05-B4: EventStore 服务 (Complete)
```

### Wave 3 - B1-B4 完成后:

```
v05-F1: VersionPanel 统一版本管理 UI (Complete)
v05-F2: ProductDoc Diff UI (Complete)
v05-F4: 事件恢复与 SSE 合并 (Complete)
```

## Parallel Development Guide

可运行 **3 个并行开发团队**:

### 1. Database Team
- 负责: v05-D1
- 工作内容: 数据库表结构、迁移脚本、回填数据
- 交付物: 可用的数据库模型

### 2. Backend Team
- Wave 1: v05-B5 (Responses API) + v05-B6 (稳定性)
- Wave 2: v05-B1, v05-B2, v05-B3, v05-B4 (并行)
- 工作内容: 服务层、API 端点、业务逻辑
- 交付物: 可用的 REST API

### 3. Frontend Team
- Wave 1: v05-F3 (API Client) (Complete)
- Wave 2: 等待 Backend API
- Wave 3: v05-F1 (Complete), v05-F2 (Complete), v05-F4 (Complete)
- 工作内容: UI 组件、Hooks、状态管理
- 交付物: 可用的用户界面

## Critical Path

关键路径影响整体交付:

```
v05-D1 → v05-B1/v05-B2/v05-B3 → v05-F1 (Complete)
```

这是最长依赖链，需要优先关注。

## Phase Summary

| Category | Count | P0 | P1 |
|----------|-------|-----|----|
| Database | 1 | 1 | 0 |
| Backend | 6 | 6 | 0 |
| Frontend | 4 | 3 | 1 |
| **Total** | **11** | **10** | **1** |

## Migration Steps

根据 Spec v0.5 Section 10:

### M1: 版本管理与数据迁移
- v05-D1: 数据库模型扩展

### M2: Responses API 切换
- v05-B5: Responses API 迁移

### M3: 事件与任务稳定性
- v05-B4: EventStore 服务
- v05-B6: 稳定性修复

### M4: 前端 UI 更新
- v05-F1: VersionPanel (Complete)
- v05-F2: ProductDoc Diff (Complete)
- v05-F4: 事件恢复 (Complete)

## Quick Links

- **数据库阶段**: `docs/phases/v05-database/`
- **后端阶段**: `docs/phases/v05-backend/`
- **前端阶段**: `docs/phases/v05-frontend/`
- **阶段总结**: `docs/v05-summary.md`
- **原始规格**: `docs/spec/spec-05.md`
