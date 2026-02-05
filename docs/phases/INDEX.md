# Project Breakdown Index

## Overview

This document provides an overview of all development phases organized by category (Frontend, Backend, Database). The project is organized into **spec versions**.

**Latest Version**: v0.6 - Skills 编排 + Orchestrator 路由 + 多模型路由 + 数据传递 + 风格参考 + 移动端约束

---

## Version 0.6: Skills 编排 + Orchestrator 路由 + 多模型路由 + 数据传递 + 风格参考 + 移动端约束

**Last Updated**: 2026-02-03 (B7 Aesthetic Scoring planned; O1 complete)

### Database Phases (v06)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| D1 | Session Metadata Extension (✅ Complete) | P0 | Low | ✅ | - | - |

### Backend Phases (v06)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| B1 | Skills Registry + Profiles + Guardrails (✅ Complete) | P0 | Medium | ✅ | - | B2, B3, B4 |
| B2 | Orchestrator Routing + Style/Guardrail Injection (✅ Complete) | P0 | High | ⚠️ | B1 | B5, B6, B7 |
| B3 | Style Reference Service (✅ Complete) | P0 | High | ⚠️ | B1 | B7 |
| B4 | Product Doc Tiers (✅ Complete) | P0 | Medium | ⚠️ | B1 | B2 |
| B5 | Data Protocol Generation (✅ Complete) | P0 | High | ⚠️ | B1, B2 | O1 |
| B6 | Multi-model Routing (✅ Complete) | P0 | High | ⚠️ | B2, B3 | - |
| B7 | Aesthetic Scoring (⏳ Planned) | P0 | Medium | ⚠️ | B3, B6 | - |
| B8 | API: Chat Image Upload (✅ Complete) | P0 | Low | ✅ | - | - |

### Frontend Phases (v06)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| F1 | Data Tab UI (✅ Complete) | P0 | Medium | ✅ | - | - |
| F2 | Image Upload & @Page Support (✅ Complete) | P0 | High | ✅ | - | F4 |
| F3 | Preview Message Bridge (✅ Complete) | P0 | Low | ✅ | - | - |
| F4 | Page Mention Component (✅ Complete) | P0 | Medium | ⚠️ | F2 | - |

### Output/Generated Phases (v06)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| O1 | Data Store Scripts (✅ Complete) | P0 | Medium | ⚠️ | B5 | - |

### v06 Dependency Graph

```
Wave 1 - Start Immediately (no dependencies):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
D1 (Session Metadata Extension)
F1 (Data Tab UI ✅)
F2 (Image Upload & @Page Support ✅)
F3 (Preview Message Bridge ✅)
B8 (API: Chat Image Upload)

Wave 2 - After Wave 1:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B1 (Skills Registry + Profiles + Guardrails ✅)
F4 (Page Mention Component ✅)

Wave 3 - After B1:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B4 (Product Doc Tiers ✅)
B3 (Style Reference Service ✅)

Wave 4 - After B1, B4:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B2 (Orchestrator Routing + Style/Guardrail Injection ✅)

Wave 5 - After B2, B3:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B5 (Data Protocol Generation ✅)
B6 (Multi-model Routing ✅)

Wave 6 - After B3, B6:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B7 (Aesthetic Scoring ⏳)

Wave 7 - After B5:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
O1 (Data Store Scripts ✅)
```

### v06 Migration Phases Mapping

| Migration | Phases | Description |
|-----------|--------|-------------|
| M1 | B1, B2, B4 | Skill Registry + Orchestrator Routing |
| M2 | B4 | Document Tiers & Structured Output |
| M3 | F2, F4, B3, B8 | Style Reference + @Page |
| M4 | F1, F3, B5, O1 | Data Protocol & Data Tab |
| M5 | B6, B7 | Multi-model Routing + Aesthetic Scoring |

### Parallel Development Guide (v06)

You can run **3 Claude Code instances in parallel**:

1. **Frontend Agent**: F1 → F2 → F3 → F4
2. **Backend Agent**: B8 → B1 → B4 → B3 → B2 → B5 → B6 → B7
3. **Database Agent**: D1

**Critical Path (v06)**: B1 → B4 → B2 → B5 → O1

**Independent Work (v06)**: F1, F2, F3, F4, D1, B8

---

## Version 0.5: (Placeholder)

| Version | Spec | Status | Key Features |
|---------|------|--------|--------------|
| v0.5 | spec-05.md | ✅ Complete | Version management, Responses API |

---

## Version 0.4: Multi-Page Generation + Product Doc + Workbench (Complete ✅)

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

**v0.4 Status: Complete ✅**

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
│   ├── e2e/
│   │   └── v06-e2e-test-plan.md
│   │
│   ├── v06 - Skills 编排 + Orchestrator 路由 + 多模型路由 + 数据传递 + 风格参考
│   │   ├── database/
│   │   │   └── v06-phase-d1-session-metadata.md
│   │   ├── backend/
│   │   │   ├── v06-phase-b1-skills-registry.md
│   │   │   ├── v06-phase-b2-orchestrator-routing.md
│   │   │   ├── v06-phase-b3-style-reference.md
│   │   │   ├── v06-phase-b4-product-doc-tiers.md
│   │   │   ├── v06-phase-b5-data-protocol.md
│   │   │   ├── v06-phase-b6-multi-model-routing.md
│   │   │   ├── v06-phase-b7-aesthetic-scoring.md
│   │   │   └── v06-phase-b8-chat-image-api.md
│   │   ├── frontend/
│   │   │   ├── v06-phase-f1-data-tab.md
│   │   │   ├── v06-phase-f2-image-upload-page.md
│   │   │   ├── v06-phase-f3-preview-bridge.md
│   │   │   └── v06-phase-f4-page-mention.md
│   │   └── output/
│   │       └── v06-phase-o1-data-store-scripts.md
│   │
│   ├── v04 - Multi-Page + ProductDoc + Workbench (Complete ✅)
│   │   └── ...
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

## Quick Start Commands for v0.6

```bash
# Database Developer
cat docs/phases/database/v06-phase-d1-session-metadata.md

# Backend Developer
cat docs/phases/backend/v06-phase-b1-skills-registry.md
cat docs/phases/backend/v06-phase-b2-orchestrator-routing.md
cat docs/phases/backend/v06-phase-b3-style-reference.md
cat docs/phases/backend/v06-phase-b4-product-doc-tiers.md
cat docs/phases/backend/v06-phase-b5-data-protocol.md
cat docs/phases/backend/v06-phase-b6-multi-model-routing.md
cat docs/phases/backend/v06-phase-b7-aesthetic-scoring.md
cat docs/phases/backend/v06-phase-b8-chat-image-api.md

# Frontend Developer
cat docs/phases/frontend/v06-phase-f1-data-tab.md
cat docs/phases/frontend/v06-phase-f2-image-upload-page.md
cat docs/phases/frontend/v06-phase-f3-preview-bridge.md
cat docs/phases/frontend/v06-phase-f4-page-mention.md

# Output/Generated Scripts
cat docs/phases/output/v06-phase-o1-data-store-scripts.md

# E2E Test Plan
cat docs/phases/e2e/v06-e2e-test-plan.md
```

---

## Version Compatibility

| Version | Spec | Status | Key Features |
|---------|------|--------|--------------|
| v0.1 | spec-01.md | ✅ Complete | CLI, Backend Core, Database |
| v0.2 | spec-02.md | ✅ Complete | Web Frontend, Planner, Executor |
| v0.3 | spec-03.md | ✅ Complete | LLM Calling, Tools, Real Agents |
| v0.4 | spec-04.md | ✅ Complete | Multi-Page, Product Doc, Workbench |
| v0.5 | spec-05.md | ✅ Complete | Version management, Responses API |
| v0.6 | spec-06.md | 🚧 In Progress | Skills, Orchestrator, Multi-model, Data Protocol, Style Ref |

---

**Document Version**: v4.0
**Last Updated**: 2026-02-03
**Total Phases (v06)**: 14 (1 Database, 8 Backend, 4 Frontend, 1 Output)
**Current Spec**: v0.6 - Skills 编排 + Orchestrator 路由 + 多模型路由 + 数据传递 + 风格参考
