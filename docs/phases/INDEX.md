# Project Breakdown Index

## Overview

This document provides an overview of all development phases organized by category (Frontend, Backend, Database). The project has been broken down into **9 phases** that can be developed in parallel by different agents or team members.

## Database Phases

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| D1       | Core Schema Design | P0 | Low | ✅ | - | B1, B2, B3, B4 |

## Backend Phases

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| B1       | Chat API & Agent Orchestration | P0 | High | ⚠️ | D1 | F2, B2 |
| B2       | Session & History Management | P0 | Medium | ⚠️ | D1, B1 | F3 |
| B3       | Token Tracking & Stats Service | P1 | Low | ⚠️ | D1 | F4 |
| B4       | Export Service | P0 | Low | ⚠️ | D1, B2 | F3 |

## Frontend Phases

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| F1       | CLI Framework Setup | P0 | Low | ✅ | - | F2, F3, F4 |
| F2       | Chat Command Implementation | P0 | High | ⚠️ | F1, B1 | - |
| F3       | History & Export Commands | P0 | Medium | ⚠️ | F1, B2, B4 | - |
| F4       | Stats Command Implementation | P1 | Low | ⚠️ | F1, B3 | - |

## Dependency Graph

```
Wave 1 (Can start immediately):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
D1 (Database Schema)    ✅ No dependencies
F1 (CLI Framework)      ✅ No dependencies

Wave 2 (After D1 completes):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B1 (Chat API)           ⚠️ Depends on: D1
B3 (Token Tracking)     ⚠️ Depends on: D1

Wave 3 (After B1 completes):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B2 (Session Mgmt)       ⚠️ Depends on: D1, B1
F2 (Chat Command)       ⚠️ Depends on: F1, B1

Wave 4 (After B2 completes):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B4 (Export Service)     ⚠️ Depends on: D1, B2

Wave 5 (After B3, B4 complete):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
F3 (History/Export)     ⚠️ Depends on: F1, B2, B4
F4 (Stats Command)      ⚠️ Depends on: F1, B3

Dependency Tree:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
D1 (Database Schema)
 ├─> B1 (Chat API & Agents)
 │    ├─> B2 (Session Management)
 │    │    └─> B4 (Export Service)
 │    │         └─> F3 (History & Export Commands)
 │    └─> F2 (Chat Command)
 │
 └─> B3 (Token Tracking)
      └─> F4 (Stats Command)

F1 (CLI Framework)
 ├─> F2 (Chat Command)
 ├─> F3 (History & Export Commands)
 └─> F4 (Stats Command)
```

## Development Strategy

### Critical Path (Must complete in order)

The **critical path** that blocks other work:

```
D1 → B1 → B2 → B4 → F3
```

This is the longest dependency chain and determines minimum project duration.

### Wave 1 - Start Immediately (No Dependencies)

**Can begin development RIGHT NOW:**

- **D1: Core Database Schema**
  - Priority: P0
  - Complexity: Low
  - Description: Design and implement SQLite schema with all 4 tables
  - Estimated Duration: 1-2 days
  - Files: `packages/backend/app/db/`

- **F1: CLI Framework Setup**
  - Priority: P0
  - Complexity: Low
  - Description: Set up TypeScript CLI with Commander.js, utilities, and API client
  - Estimated Duration: 1-2 days
  - Files: `packages/cli/src/`

**Impact**: These two phases block all other work, so start them immediately!

### Wave 2 - After Wave 1 (After D1 completes)

**Can begin after D1 is done:**

- **B1: Chat API & Agent Orchestration**
  - Priority: P0
  - Complexity: High
  - Description: Build FastAPI app, 3 agents (Interview, Generation, Refinement), and orchestration
  - Estimated Duration: 4-5 days
  - Files: `packages/backend/app/agents/`, `packages/backend/app/api/chat.py`

- **B3: Token Tracking & Stats Service**
  - Priority: P1
  - Complexity: Low
  - Description: Track token usage and provide statistics
  - Estimated Duration: 1-2 days
  - Files: `packages/backend/app/services/token_tracker.py`

**Parallel Work**: B1 and B3 can be developed in parallel since they don't depend on each other.

### Wave 3 - After Wave 2 (After B1 completes)

**Can begin after B1 is done:**

- **B2: Session & History Management**
  - Priority: P0
  - Complexity: Medium
  - Description: Session CRUD, message storage, version control, filesystem operations
  - Estimated Duration: 2-3 days
  - Files: `packages/backend/app/services/session.py`, `message.py`, `version.py`

- **F2: Chat Command Implementation**
  - Priority: P0
  - Complexity: High
  - Description: Interactive chat loop with progress displays for all 3 agent phases
  - Estimated Duration: 3-4 days
  - Files: `packages/cli/src/commands/chat.ts`
  - Note: Also requires F1 to be complete

**Parallel Work**: B2 and F2 can be developed in parallel.

### Wave 4 - After Wave 3 (After B2 completes)

**Can begin after B2 is done:**

- **B4: Export Service**
  - Priority: P0
  - Complexity: Low
  - Description: Export HTML to filesystem
  - Estimated Duration: 1 day
  - Files: `packages/backend/app/services/export.py`

### Wave 5 - Final Commands (After B3, B4 complete)

**Can begin after B3 and B4 are done:**

- **F3: History & Export Commands**
  - Priority: P0
  - Complexity: Medium
  - Description: List sessions, view details, rollback, export
  - Estimated Duration: 2-3 days
  - Files: `packages/cli/src/commands/history.ts`, `export.ts`, `rollback.ts`
  - Requires: F1, B2, B4

- **F4: Stats Command Implementation**
  - Priority: P1
  - Complexity: Low
  - Description: Display token usage statistics
  - Estimated Duration: 1 day
  - Files: `packages/cli/src/commands/stats.ts`
  - Requires: F1, B3

**Parallel Work**: F3 and F4 can be developed in parallel.

## Parallel Development Guide

You can run **3 Claude Code instances in parallel** for maximum efficiency:

### Agent 1: Database + Backend Core (Critical Path)

**Recommended sequence:**
1. Start with D1 (Database Schema) - 1-2 days
2. Then B1 (Chat API & Agents) - 4-5 days
3. Then B2 (Session Management) - 2-3 days
4. Then B4 (Export Service) - 1 day

**Total Duration**: ~9-11 days
**Priority**: Highest (blocks all other work)

### Agent 2: Frontend CLI (User Interface)

**Recommended sequence:**
1. Start with F1 (CLI Framework) - 1-2 days
2. Wait for B1, then F2 (Chat Command) - 3-4 days
3. Wait for B2 & B4, then F3 (History & Export) - 2-3 days

**Total Duration**: ~6-9 days
**Priority**: High (user-facing)

### Agent 3: Backend Services (Auxiliary Features)

**Recommended sequence:**
1. Wait for D1, then B3 (Token Tracking) - 1-2 days
2. Then F4 (Stats Command) - 1 day

**Total Duration**: ~2-3 days
**Priority**: Medium (P1 features)

## Estimated Timeline

Assuming **1 developer working full-time**:
- Sequential: ~15-20 days
- With 3 parallel agents: ~9-11 days (limited by critical path)

Assuming **3 developers working in parallel**:
- Total: ~9-11 days (limited by critical path: D1 → B1 → B2 → B4)

## Phase File Locations

```
docs/phases/
├── database/
│   └── v01-phase-d1-core-schema.md
│
├── backend/
│   ├── v01-phase-b1-chat-api-agents.md
│   ├── v01-phase-b2-session-management.md
│   ├── v01-phase-b3-token-tracking.md
│   └── v01-phase-b4-export-service.md
│
└── frontend/
    ├── v01-phase-f1-cli-framework.md
    ├── v01-phase-f2-chat-command.md
    ├── v01-phase-f3-history-export.md
    └── v01-phase-f4-stats-command.md
```

## Quick Start Commands

### For Developer 1 (Critical Path):
```bash
# Read the phases in order
cat docs/phases/database/v01-phase-d1-core-schema.md
cat docs/phases/backend/v01-phase-b1-chat-api-agents.md
cat docs/phases/backend/v01-phase-b2-session-management.md
cat docs/phases/backend/v01-phase-b4-export-service.md
```

### For Developer 2 (Frontend):
```bash
# Read the phases in order
cat docs/phases/frontend/v01-phase-f1-cli-framework.md
cat docs/phases/frontend/v01-phase-f2-chat-command.md
cat docs/phases/frontend/v01-phase-f3-history-export.md
```

### For Developer 3 (Auxiliary):
```bash
# Read the phases in order
cat docs/phases/backend/v01-phase-b3-token-tracking.md
cat docs/phases/frontend/v01-phase-f4-stats-command.md
```

## Testing Strategy

### Per-Phase Testing
Each phase document includes:
- Unit test requirements
- Integration test requirements
- E2E test requirements (where applicable)

### Integration Testing Checkpoints

**After Wave 2 completes (D1 + B1):**
- Test: Database operations with agent API calls
- Test: Complete interview → generation flow

**After Wave 3 completes (+ B2 + F2):**
- Test: Full CLI chat experience end-to-end
- Test: Session persistence and continuation

**After Wave 5 completes (All phases):**
- Test: Complete user journey (chat → history → export → stats)
- Test: All commands work together seamlessly

## Notes & Best Practices

### Communication Between Agents

When working in parallel:
- **Share database schema** immediately after D1 completes
- **Share API contracts** from B1 to frontend developers
- **Document data models** for consistency
- **Use the same coding standards** across all phases

### Handling Blockers

If a developer is blocked:
1. Check the dependency graph
2. Work on tests for current phase
3. Start documentation
4. Review and improve existing phases
5. Help with code review on other phases

### Code Review Strategy

- **D1 review**: Critical - all backend depends on this
- **B1 review**: Critical - agents are complex, review carefully
- **F1 review**: Important - sets standards for all CLI commands
- **Other phases**: Standard review process

---

**Document Version**: v1.0
**Last Updated**: 2025-01-30
**Total Phases**: 9 (1 Database, 4 Backend, 4 Frontend)
**Estimated Duration**: 9-11 days (with 3 parallel developers)
