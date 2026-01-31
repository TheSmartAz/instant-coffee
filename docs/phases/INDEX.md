# Project Breakdown Index

## Overview

This document provides an overview of all development phases organized by category (Frontend, Backend, Database). The project is organized into **spec versions** with v01 for CLI features and v02 for Web features.

**Latest Version**: v0.3 - Agent LLM Calling + Tools System

---

## Version 0.3: Agent LLM Calling + Tools System

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

### v03 Dependency Graph

```
Wave 1 (Can start immediately):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B4 (Agent Prompts)       ✅ Complete
B9 (Error Handling)      ✅ Complete
B1 (LLM Client)          ✅ Complete
B2 (Tools System)        ✅ Complete
B3 (BaseAgent)           ✅ Complete (LLM calls + events + token tracking)
F2 (Token Cost Display)  ✅ Complete

Wave 2 (After B4 completes):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B5 (InterviewAgent)      ✅ Complete
B6 (GenerationAgent)     ✅ Complete (Depends on: B2, B3, B4)
B7 (RefinementAgent)     ✅ Complete

Wave 4 (After B5-B7 complete):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B8 (Tool Event Integration) ✅ Complete

Wave 5 (After B8 completes):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
F1 (Event Display)       ✅ Complete

v0.3 Complete! 🎉
```

---

## Version 0.2: Web Frontend + Planner

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

---

## Version 0.1: CLI + Backend Core

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

---

## Phase File Locations

```
docs/
├── v03-summary.md (v0.3 implementation progress)
├── phases/
│   ├── INDEX.md (this file)
│   │
│   ├── v03 - Agent LLM Calling + Tools
│   ├── backend/
│   │   ├── v03-phase-b1-llm-client.md
│   │   ├── v03-phase-b2-tools-system.md
│   │   ├── v03-phase-b3-base-agent-enhancement.md
│   │   ├── v03-phase-b4-agent-prompts.md
│   │   ├── v03-phase-b5-interview-agent.md
│   │   ├── v03-phase-b6-generation-agent.md
│   │   ├── v03-phase-b7-refinement-agent.md
│   │   ├── v03-phase-b8-tool-event-integration.md ✅
│   │   └── v03-phase-b9-error-handling-retry.md
│   └── frontend/
│       ├── v03-phase-f1-event-display.md ✅
│       └── v03-phase-f2-token-cost-display.md ✅
│
├── v02 - Web Frontend + Planner
│   ├── database/
│   │   └── v02-phase-d1-plan-task-schema.md
│   ├── backend/
│   │   ├── v02-phase-b1-event-protocol.md
│   │   ├── v02-phase-b2-planner-service.md
│   │   ├── v02-phase-b3-parallel-executor.md
│   │   └── v02-phase-b4-task-control-api.md
│   └── frontend/
│       ├── v02-phase-f1-web-skeleton.md
│       ├── v02-phase-f2-sse-event-flow.md
│       ├── v02-phase-f2-implementation.md
│       ├── v02-phase-f3-todo-panel.md
│       ├── v02-phase-f3-implementation.md
│       ├── v02-phase-f4-task-card-view.md
│       ├── v02-phase-f4-implementation.md
│       ├── v02-phase-f5-failure-handling-ui.md
│       ├── v02-phase-f5-implementation.md
│       └── v02-phase-f5-testing-guide.md
│
└── v01 - CLI + Backend Core
    ├── database/
    │   └── v01-phase-d1-core-schema.md
    ├── backend/
    │   ├── v01-phase-b1-chat-api-agents.md
    │   ├── v01-phase-b2-session-management.md
    │   ├── v01-phase-b3-token-tracking.md
    │   └── v01-phase-b4-export-service.md
    └── frontend/
        ├── v01-phase-f1-cli-framework.md
        ├── v01-phase-f2-chat-command.md
        ├── v01-phase-f3-history-export.md
        └── v01-phase-f4-stats-command.md
```

---

## Development Strategy for v0.3

### Parallel Development Opportunities

**Wave 1 - Start Immediately:**
- ~~B4: Agent Prompts (Backend)~~ ✅ Complete
- ~~B9: Error Handling (Backend)~~ ✅ Complete
- ~~B3: BaseAgent Enhancement (Backend)~~ ✅ Complete (LLM calls + events + token tracking)
- ~~F2: Token Cost Display (Frontend)~~ ✅ Complete

**Wave 2 - After B4:**
- B5: InterviewAgent (Backend) ✅ Complete
- B6: GenerationAgent (Backend) ✅ Complete
- B7: RefinementAgent (Backend) ✅ Complete

**Wave 4 - After B5-B7:**
- B8: Tool Event Integration (Backend) ✅ Complete

**Wave 5 - After B8:**
- F1: Event Display Enhancement (Frontend) ⏳ Pending

### Critical Path (v0.3)

```
F1 (Event Display)
```

### Estimated Duration (v0.3)

Assuming **3 developers working in parallel**:
- **Total Duration**: ~6-8 days (limited by critical path)

### Per-Developer Tracks

**Developer 1 (LLM Core):**
1. B1: LLM Client Layer
2. B3: BaseAgent Enhancement
3. B5: InterviewAgent

**Developer 2 (Tools & Agents):**
1. B2: Tools System
2. B4: Agent Prompts
3. B6: GenerationAgent
4. B7: RefinementAgent

**Developer 3 (Events & Frontend):**
1. B9: Error Handling ✅ Complete
2. F2: Token Cost Display ✅ Complete
3. B8: Tool Event Integration ✅ Complete
4. F1: Event Display Enhancement ✅ Complete

---

## Quick Start Commands

### For v0.3 Development:

```bash
# Developer 1 - LLM Core
cat docs/phases/backend/v03-phase-b1-llm-client.md
cat docs/phases/backend/v03-phase-b3-base-agent-enhancement.md
cat docs/phases/backend/v03-phase-b5-interview-agent.md

# Developer 2 - Tools & Agents
cat docs/phases/backend/v03-phase-b2-tools-system.md
cat docs/phases/backend/v03-phase-b4-agent-prompts.md
cat docs/phases/backend/v03-phase-b6-generation-agent.md
cat docs/phases/backend/v03-phase-b7-refinement-agent.md

# Developer 3 - Events & Frontend
cat docs/phases/backend/v03-phase-b9-error-handling-retry.md
cat docs/phases/frontend/v03-phase-f2-token-cost-display.md
cat docs/phases/backend/v03-phase-b8-tool-event-integration.md
cat docs/phases/frontend/v03-phase-f1-event-display.md
```

---

## Version Compatibility

| Version | Spec | Status | Key Features |
|---------|------|--------|--------------|
| v0.1 | spec-01.md | ✅ Complete | CLI, Backend Core, Database |
| v0.2 | spec-02.md | ✅ Complete | Web Frontend, Planner, Executor |
| v0.3 | spec-03.md | ✅ Complete | LLM Calling, Tools, Real Agents |

---

**Document Version**: v2.0
**Last Updated**: 2026-01-31
**Total Phases**: 32 (3 Database, 24 Backend, 5 Frontend)
**Current Spec**: v0.3 - Agent LLM Calling + Tools System (11 phases)
