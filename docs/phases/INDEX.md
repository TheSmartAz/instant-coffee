# Project Breakdown Index

## Overview

This document provides an overview of all development phases organized by category (Frontend, Backend, Database). The project is organized into **spec versions** with v01 for CLI features and v02 for Web features.

**Latest Version**: v0.4 - Multi-Page Generation + Product Doc + Workbench

---

## Version 0.4: Multi-Page Generation + Product Doc + Workbench

### Database Phases (v04)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| D1 | ProductDoc & Page Schema (✅ Complete) | P0 | Medium | ✅ | - | B1-B10, F1-F7 |

### Backend Phases (v04)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| B1 | ProductDoc Service (✅ Complete) | P0 | Medium | ⚠️ | D1 | B3, B5, B7, F1 |
| B2 | Page & PageVersion Service (✅ Complete) | P0 | Medium | ⚠️ | D1 | B5, B6, B7, F2, F3 |
| B3 | ProductDoc Agent (✅ Complete) | P0 | High | ⚠️ | B1 | B5, B8 |
| B4 | Sitemap Agent & AutoMultiPageDecider (✅ Complete) | P0 | High | ⚠️ | D1, B1 | B5, B6 |
| B5 | Orchestrator Update (✅ Complete) | P0 | High | ⚠️ | B1, B2, B3, B4 | B8 |
| B6 | GenerationAgent Update (✅ Complete) | P0 | Medium | ⚠️ | B2, B4 | B7, B8 |
| B7 | RefinementAgent Update (✅ Complete) | P0 | Medium | ⚠️ | B2, B6 | B8 |
| B8 | Files API (Code Tab Backend) (✅ Complete) | P1 | Medium | ⚠️ | B2, B1 | F3 |
| B9 | Chat API Update (✅ Complete) | P0 | Medium | ⚠️ | B5 | F6 |
| B10 | Export Service Update (✅ Complete) | P1 | Medium | ⚠️ | B2, B8 | - |

### Frontend Phases (v04)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| F1 | ProductDocPanel Component (✅ Complete) | P0 | Medium | ⚠️ | B1 | F4 |
| F2 | PreviewPanel Multi-Page Enhancement (✅ Complete) | P0 | Medium | ⚠️ | B2 | F4 |
| F3 | CodePanel Component (✅ Complete) | P1 | Medium | ⚠️ | B8 | F4 |
| F4 | WorkbenchPanel (Three-Tab Container) (✅ Complete) | P0 | Medium | ⚠️ | F1, F2, F3 | F5, F7 |
| F5 | VersionPanel Update for Page Mode (✅ Complete) | P0 | Low | ⚠️ | F2, F4 | F7 |
| F6 | Chat & Event Integration (✅ Complete) | P0 | Medium | ⚠️ | B9 | F7 |
| F7 | ProjectPage Layout Update (✅ Complete) | P0 | Medium | ⚠️ | F4, F5, F6 | - |

### v04 Dependency Graph

```
Wave 1 - Start Immediately (no dependencies):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
D1 (ProductDoc & Page Schema)

Wave 2 - After D1:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B1 (ProductDoc Service)
B2 (Page & PageVersion Service)
B4 (Sitemap Agent & AutoMultiPageDecider)

Wave 3 - After B1:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B3 (ProductDoc Agent) (✅)
B8 (Files API) (✅)
F1 (ProductDocPanel)

Wave 4 - After B2:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B6 (GenerationAgent Update) (✅)
F2 (PreviewPanel Multi-Page)

Wave 5 - After B3, B4:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B5 (Orchestrator Update) (✅)

Wave 6 - After B5, B6:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B7 (RefinementAgent Update) (✅)
B9 (Chat API Update) (✅)

Wave 7 - After B8:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
F3 (CodePanel)

Wave 8 - After F1, F2, F3:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
F4 (WorkbenchPanel)

Wave 9 - After F4, B9 (✅):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
F5 (VersionPanel Update) (✅)
F6 (Chat & Event Integration) (✅)

Wave 10 - After F5, F6 (✅):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
F7 (ProjectPage Layout Update) (✅)

Parallel Track - After B2, B8:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B10 (Export Service Update) (✅)
```

### Critical Path (v0.4)

```
D1 → B1 → B3 → B5 → B9 → F6 → F7
          ↓
D1 → B2 → B6 → B7
          ↓
D1 → B4 ─┘

Longest Path: D1 → B1 → B3 → B5 → B9 → F6 → F7
```

### Parallel Development Guide

You can run **3+ Claude Code instances in parallel**:

1. **Database Agent**: D1 first
2. **Backend Agent 1 (ProductDoc)**: B1 → B3 → B5 (part) → B9
3. **Backend Agent 2 (Pages)**: B2 → B6 → B7 → B10
4. **Backend Agent 3 (Sitemap/Files)**: B4 → B8
5. **Frontend Agent**: F1, F2, F3 (wait for backend) → F4 → F5, F6 → F7

### Wave-by-Wave Execution Plan

| Wave | Database | Backend | Frontend |
|------|----------|---------|----------|
| 1 | D1 (✅) | - | - |
| 2 | - | B1 (✅), B2 (✅), B4 (✅) | - |
| 3 | - | B3 (✅), B8 (✅) | F1 (✅) |
| 4 | - | B6 (✅) | F2 (✅) |
| 5 | - | B5 (✅) | - |
| 6 | - | B7 (✅), B9 (✅) | - |
| 7 | - | B10 (✅) | F3 (✅) |
| 8 | - | - | F4 (✅) |
| 9 | - | - | F5 (✅), F6 (✅) |
| 10 | - | - | F7 (✅) |

---

## Version 0.3: Agent LLM Calling + Tools System (Complete ✅)

### Backend Phases (v03)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| B1 | LLM Client Layer | P0 | High | ✅ | - | B3, B5-B7 |
| B2 | Tools System | P0 | Medium | ✅ | - | B5-B7, B8 |
| B3 | BaseAgent Enhancement | P0 | Medium | ⚠️ | B1 | B5-B7 |
| B4 | Agent Prompts | P0 | Low | ✅ | - | B5-B7 |
| B5 | InterviewAgent Implementation | P0 | Medium | ⚠️ | B3, B4 | - |
| B6 | GenerationAgent Implementation | P0 | High | ⚠️ | B2, B3, B4 | - |
| B7 | RefinementAgent Implementation | P0 | Medium | ⚠️ | B2, B3, B4 | - |
| B8 | Tool Event Integration | P0 | Medium | ⚠️ | B3, B5-B7 | F1 |
| B9 | Error Handling & Retry | P1 | Medium | ✅ | B1 | - |

### Frontend Phases (v03)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Status |
|----------|------|----------|------------|-----------|------------|--------|
| F1 | Event Display Enhancement | P1 | Medium | ⚠️ | B8 | ✅ Complete |
| F2 | Token Cost Display | P1 | Low | ✅ | - | ✅ Complete |

**v0.3 Status: Complete ✅**

---

## Version 0.2: Web Frontend + Planner (Complete ✅)

### Database Phases (v02)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| D1 | Plan & Task Schema | P0 | Medium | ✅ | - | B1-B4 |

### Backend Phases (v02)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| B1 | Event Protocol | P0 | Medium | ✅ | - | F2, B2-B4 |
| B2 | Planner Service | P0 | High | ⚠️ | B1 | B3 |
| B3 | Parallel Executor | P0 | High | ⚠️ | B1, B2 | B4 |
| B4 | Task Control API | P0 | Medium | ⚠️ | B1, B3 | F3-F5 |

### Frontend Phases (v02)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| F1 | Web Skeleton | P0 | Low | ✅ | - | F2-F5 |
| F2 | SSE Event Flow | P0 | Medium | ⚠️ | B1 | - |
| F3 | Todo Panel | P0 | Medium | ⚠️ | F1, B4 | - |
| F4 | Task Card View | P0 | High | ⚠️ | F1, B4 | - |
| F5 | Failure Handling UI | P0 | Medium | ⚠️ | F1, B4 | - |

**v0.2 Status: Complete ✅**

---

## Version 0.1: CLI + Backend Core (Complete ✅)

### Database Phases (v01)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| D1 | Core Schema Design | P0 | Low | ✅ | - | B1-B4 |

### Backend Phases (v01)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| B1 | Chat API & Agent Orchestration | P0 | High | ⚠️ | D1 | F2, B2 |
| B2 | Session & History Management | P0 | Medium | ⚠️ | D1, B1 | F3 |
| B3 | Token Tracking & Stats Service | P1 | Low | ⚠️ | D1 | F4 |
| B4 | Export Service | P0 | Low | ⚠️ | D1, B2 | F3 |

### Frontend Phases (v01)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| F1 | CLI Framework Setup | P0 | Low | ✅ | - | F2-F4 |
| F2 | Chat Command Implementation | P0 | High | ⚠️ | F1, B1 | - |
| F3 | History & Export Commands | P0 | Medium | ⚠️ | F1, B2, B4 | - |
| F4 | Stats Command Implementation | P1 | Low | ⚠️ | F1, B3 | - |

**v0.1 Status: Complete ✅**

---

## Phase File Locations

```
docs/
├── phases/
│   ├── INDEX.md (this file)
│   │
│   ├── v04 - Multi-Page + ProductDoc + Workbench
│   │   ├── database/
│   │   │   └── v04-phase-d1-product-doc-page-schema.md
│   │   ├── backend/
│   │   │   ├── v04-phase-b1-product-doc-service.md
│   │   │   ├── v04-phase-b2-page-service.md
│   │   │   ├── v04-phase-b3-product-doc-agent.md
│   │   │   ├── v04-phase-b4-sitemap-agent.md
│   │   │   ├── v04-phase-b5-orchestrator-update.md
│   │   │   ├── v04-phase-b6-generation-agent-update.md
│   │   │   ├── v04-phase-b7-refinement-agent-update.md
│   │   │   ├── v04-phase-b8-files-api.md
│   │   │   ├── v04-phase-b9-chat-api-update.md
│   │   │   └── v04-phase-b10-export-service-update.md
│   │   └── frontend/
│   │       ├── v04-phase-f1-product-doc-panel.md
│   │       ├── v04-phase-f2-preview-panel-multipage.md
│   │       ├── v04-phase-f3-code-panel.md
│   │       ├── v04-phase-f4-workbench-panel.md
│   │       ├── v04-phase-f5-version-panel-update.md
│   │       ├── v04-phase-f6-chat-event-integration.md
│   │       └── v04-phase-f7-project-page-update.md
│   │
│   ├── v03 - Agent LLM Calling + Tools (Complete ✅)
│   │   └── ...
│   │
│   ├── v02 - Web Frontend + Planner (Complete ✅)
│   │   └── ...
│   │
│   └── v01 - CLI + Backend Core (Complete ✅)
│       └── ...
```

---

## Quick Start Commands for v0.4

```bash
# Database Developer
cat docs/phases/database/v04-phase-d1-product-doc-page-schema.md

# Backend Developer 1 (ProductDoc)
cat docs/phases/backend/v04-phase-b1-product-doc-service.md
cat docs/phases/backend/v04-phase-b3-product-doc-agent.md
cat docs/phases/backend/v04-phase-b9-chat-api-update.md

# Backend Developer 2 (Pages)
cat docs/phases/backend/v04-phase-b2-page-service.md
cat docs/phases/backend/v04-phase-b6-generation-agent-update.md
cat docs/phases/backend/v04-phase-b7-refinement-agent-update.md
cat docs/phases/backend/v04-phase-b10-export-service-update.md

# Backend Developer 3 (Sitemap/Files)
cat docs/phases/backend/v04-phase-b4-sitemap-agent.md
cat docs/phases/backend/v04-phase-b5-orchestrator-update.md
cat docs/phases/backend/v04-phase-b8-files-api.md

# Frontend Developer
cat docs/phases/frontend/v04-phase-f1-product-doc-panel.md
cat docs/phases/frontend/v04-phase-f2-preview-panel-multipage.md
cat docs/phases/frontend/v04-phase-f3-code-panel.md
cat docs/phases/frontend/v04-phase-f4-workbench-panel.md
cat docs/phases/frontend/v04-phase-f5-version-panel-update.md
cat docs/phases/frontend/v04-phase-f6-chat-event-integration.md
cat docs/phases/frontend/v04-phase-f7-project-page-update.md
```

---

## Version Compatibility

| Version | Spec | Status | Key Features |
|---------|------|--------|--------------|
| v0.1 | spec-01.md | ✅ Complete | CLI, Backend Core, Database |
| v0.2 | spec-02.md | ✅ Complete | Web Frontend, Planner, Executor |
| v0.3 | spec-03.md | ✅ Complete | LLM Calling, Tools, Real Agents |
| v0.4 | spec-04.md | ✅ Complete | Multi-Page, Product Doc, Workbench |

---

**Document Version**: v3.1
**Last Updated**: 2026-02-02
**Total Phases (v04)**: 18 (1 Database, 10 Backend, 7 Frontend)
**Current Spec**: v0.4 - Multi-Page Generation + Product Doc + Workbench
**v04 Progress**: 18/18 complete (✅ All phases done)
