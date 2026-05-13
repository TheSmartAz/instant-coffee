# Project Breakdown Index

> Current status note (2026-05-13): this directory is a historical roadmap and phase breakdown archive. It is useful for intent and acceptance criteria, but it is not authoritative for the current code layout or mounted API surface. Use `README.md`, `CLAUDE.md`, and `docs/project-summary.md` for the current implementation snapshot. Current backend runtime is centered on `packages/backend/app/engine`, `packages/backend/app/services`, and the embedded `packages/agent` engine; the old `agents`/`planner`/`executor`/`graph` backend layout is no longer present.

## Overview

This document provides an overview of all development phases organized by category (Frontend, Backend, Database). The project is organized into **spec versions**.

**Archived latest roadmap label**: v1.0 - Generation Reliability + Dialogue Intelligence + Frontend Upgrade + Deployment Export + Analytics

---

## Archived Version 1.0 Roadmap: Generation Reliability + Dialogue Intelligence + Frontend Upgrade + Deployment Export + Analytics

**Last Updated**: 2026-02-13 (Breakdown created)

### Database Phases (v10)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| D1 | Cross-Session Memory + Analytics Schema | P0 | Medium | ✅ | - | B8, B11 |

### Backend Phases (v10)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| B1 | Exact Token Calculation (tiktoken) | P0 | Medium | ✅ | - | B2, B5 |
| B2 | Structured HTML Generation Tool | P0 | High | ⚠️ | B1 | B3 |
| B3 | Atomic Multi-file Operations | P0 | High | ⚠️ | B2 | - |
| B4 | Provider Fallback Chain | P0 | Medium | ✅ | - | - |
| B5 | Structured Compaction | P1 | High | ⚠️ | B1 | - |
| B6 | AskUser Timeout + Graceful Degradation | P0 | Medium | ✅ | - | B7 |
| B7 | Interview Progress Indicator | P1 | Low | ⚠️ | B6 | F3 |
| B8 | Cross-Session Memory | P0 | High | ⚠️ | D1 | - |
| B9 | Richer Context Injection | P1 | Medium | ✅ | - | - |
| B10 | One-Click Deployment Service | P0 | High | ⚠️ | F2 | F4 |
| B11 | Analytics Service | P0 | High | ⚠️ | D1 | F6 |

### Frontend Phases (v10)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| F1 | Zustand State Management | P0 | High | ✅ | - | F2 |
| F2 | Split ProjectPage | P0 | High | ⚠️ | F1 | B10, F4 |
| F3 | Interview Progress Indicator UI | P1 | Low | ⚠️ | B7 | - |
| F4 | Deploy Button UI | P0 | Medium | ⚠️ | F2, B10 | F5 |
| F5 | QR Code Sharing | P1 | Low | ⚠️ | F4 | - |
| F6 | Data Tab Dashboard | P0 | High | ⚠️ | B11 | - |

### Output Phases (v10)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| O1 | Analytics Tracking Script Template | P0 | Medium | ⚠️ | B11 | - |

### v10 Dependency Graph

```
Wave 1 - Start Immediately (no dependencies):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
D1 (Database Schema)
B1 (Token Calculation)
B4 (Provider Fallback)
B6 (AskUser Timeout)
F1 (Zustand)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Wave 2 - After D1:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B8 (Cross-Session Memory - DB dependent)
B11 (Analytics Service - DB dependent)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Wave 3 - After B1:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B2 (Structured HTML Tool)
B5 (Structured Compaction)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Wave 4 - After B2:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B3 (Atomic Batch Operations)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Wave 5 - After F1:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
F2 (Split ProjectPage)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Wave 6 - After F2:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B10 (Deploy Service)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Wave 7 - After B10:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
F4 (Deploy Button UI)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Wave 8 - After B11:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
F6 (Data Tab Dashboard)
O1 (Analytics Script)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Historical Parallel Development Notes (v10)

Original planning note: this roadmap suggested **3 Claude Code instances in parallel**:

1. **Agent Reliability Agent**: B1 → B2 → B3 → B4 → B5
2. **Frontend Architecture Agent**: F1 → F2 → F4 → F5
3. **Dialogue & Intelligence Agent**: B6 → B7 → B8 → B9

Or alternatively:

1. **Backend Agent**: B1 → B2 → B3 → B4 → B5 → B6 → B7 → B9 → B10 → B11
2. **Frontend Agent**: F1 → F2 → F3 → F4 → F5 → F6
3. **Database Agent**: D1 (standalone)

**Critical Path**: D1 → B8 → (nothing blocks) or F1 → F2 → B10 → F4
**Independent Work**: B1, B4, B6, F1 (can start immediately)

---

## Archived Version 0.9 Roadmap: Soul Agentic Loop — LangGraph → Tool-Calling Loop Refactor

**Last Updated**: 2026-02-07 (Breakdown created)

### Backend Phases (v09)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| B1 | Contract Freeze & Tool Foundation (✅ Complete) | P0 | Medium | ✅ | - | B2, B3, B5 |
| B2 | Core Tools (8 Generation Tools) (✅ Complete) | P0 | High | ⚠️ | B1 | B5 |
| B3 | Interview & Ask User Tool | P0 | High | ⚠️ | B1, B2 | B4, B5 |
| B4 | Context Management (Soul) | P0 | High | ⚠️ | B3 | B5 |
| B5 | Agentic Loop Core | P0 | High | ⚠️ | B1, B2, B3, B4 | B7 |
| B6 | LLM Layer Simplification (✅ Complete) | P1 | Medium | ✅ | - | - |
| B7 | API Integration & LangGraph Cleanup | P0 | Medium | ⚠️ | B5 | F1 |

### Frontend Phases (v09)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| F1 | Product Doc Update Card | P1 | Low | ⚠️ | B7 | - |

### v09 Dependency Graph

```
Wave 1 - Start Immediately (no dependencies):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B1 (Contract Freeze & Tool Foundation)
B6 (LLM Layer Simplification)

Wave 2 - After B1:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B2 (Core Tools)

Wave 3 - After B1, B2:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B3 (Interview & Ask User Tool)

Wave 4 - After B3:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B4 (Context Management)

Wave 5 - After B1, B2, B3, B4:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B5 (Agentic Loop Core)

Wave 6 - After B5:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B7 (API Integration & LangGraph Cleanup)

Wave 7 - After B7:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
F1 (Product Doc Update Card)
```

### Historical Parallel Development Notes (v09)

You can run **2 Claude Code instances in parallel**:

1. **Soul System Agent**: B1 → B2 → B3 → B4 → B5 → B7
2. **LLM Cleanup Agent**: B6 (independent, can start immediately)

After B7 completes:
3. **Frontend Agent**: F1

**Critical Path**: B1 → B2 → B3 → B4 → B5 → B7
**Independent Work**: B6 (can be done anytime)

---

## Archived Version 0.8 Roadmap: Run-Centric Backend Refactor + App Data Layer

**Last Updated**: 2026-02-06 (D1 complete, D2 complete, B1 complete, B2 complete, B3 complete, B4 complete, B5 complete, B6 complete, B7 complete, B8 complete, F1 complete)

### Database Phases (v08)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| D1 | Run Data Layer (✅ Complete) | P0 | Medium | ✅ | - | B1, B2 |
| D2 | App Data PG Schema (✅ Complete) | P0 | High | ✅ | - | B7, B8 |

### Backend Phases (v08)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| B1 | Run Service + State Machine + CRUD API (✅ Complete) | P0 | High | ⚠️ | D1 | B3, B4 |
| B2 | Event Layer Upgrade (✅ Complete) | P0 | Medium | ⚠️ | D1 | B4 |
| B3 | Orchestration Run Integration (✅ Complete) | P0 | High | ⚠️ | B1 | B5, B6 |
| B4 | Chat Compatibility Adapter (✅ Complete) | P0 | Medium | ⚠️ | B1, B2 | - |
| B5 | Tool Policy Hooks (✅ Complete) | P1 | Medium | ⚠️ | B3 | - |
| B6 | Verify Gate (✅ Complete) | P0 | High | ⚠️ | B3 | - |
| B7 | App Data API (✅ Complete) | P0 | Medium | ⚠️ | D2 | F1, B8 |
| B8 | Generation Integration with App Data (✅ Complete) | P0 | Medium | ⚠️ | D2 | - |

### Frontend Phases (v08)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| F1 | Data Tab Frontend Overhaul (✅ Complete) | P0 | High | ⚠️ | B7 | - |

### v08 Dependency Graph

```
Wave 1 - Start Immediately (no dependencies):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
D1 (Run Data Layer ✅)
D2 (App Data PG Schema ✅)

Wave 2 - After D1:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B1 (Run Service + State Machine + CRUD API ✅)
B2 (Event Layer Upgrade ✅)

Wave 2b - After D2:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B7 (App Data API ✅)
B8 (Generation Integration with App Data ✅)

Wave 3 - After B1:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B3 (Orchestration Run Integration ✅)

Wave 3b - After B1, B2:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B4 (Chat Compatibility Adapter ✅)

Wave 4 - After B3:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B5 (Tool Policy Hooks ✅)
B6 (Verify Gate ✅)

Wave 5 - After B7:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
F1 (Data Tab Frontend Overhaul ✅)
```

### v08 Migration Phases Mapping

| Migration | Phases | Description |
|-----------|--------|-------------|
| M1 | D1, D2 | Database: Run table + App Data PG schemas |
| M2 | B1, B2 | Run Service + Event Layer |
| M3 | B3, B5, B6 | Orchestration integration + Tool Policy + Verify Gate |
| M4 | B4 | Chat compatibility adapter (last to merge) |
| M5 | B7, B8, F1 | App Data API + Generation integration + Data Tab UI |

### Historical Parallel Development Notes (v08)

You can run **3 Claude Code instances in parallel**:

1. **Run System Agent**: D1 → B1 → B2 → B3 → B5 → B6 → B4
2. **App Data Agent**: D2 → B7 → B8
3. **Frontend Agent**: F1 (after B7 completes)

**Critical Path (Run System)**: D1 → B1 → B3 → B6
**Critical Path (App Data)**: D2 → B7 → F1
**Independent Tracks**: Run System and App Data can be developed fully in parallel

---

## Archived Version 0.7 Roadmap: LangGraph 编排 + React SSG 多文件产物 + 场景旅程能力 + 组件一致性 + Mobile Shell 自动修复

**Last Updated**: 2026-02-05 (F4 build status UI complete with build SSE stream; build preview hosting endpoints added; B7 aesthetic scoring complete; F3 aesthetic score display complete with metadata preload; B2 scene/journey capabilities complete; B3 component registry node complete; backend deps locked with uv; B4 React SSG build pipeline complete; B8 API endpoints complete; O1 React SSG template complete; F1 asset upload UI complete; F2 data tab scene classification complete; chat attachments 10MB)

### Database Phases (v07)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| D1 | Graph State Schema Extension (✅ Complete) | P0 | Low | ✅ | - | - |

### Backend Phases (v07)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| B1 | LangGraph Orchestration Skeleton (✅ Complete) | P0 | High | ✅ | - | B2, B3, B4, B5, B6, B7, B8 |
| B2 | Scene/Journey Capabilities (✅ Complete) | P0 | Medium | ✅ | - | B3 |
| B3 | Component Registry Node (✅ Complete) | P0 | High | ⚠️ | B1, B2 | B4 |
| B4 | React SSG Build Pipeline (✅ Complete) | P0 | Very High | ⚠️ | O1 | B8 |
| B5 | Mobile Shell Auto-fix (✅ Complete) | P0 | Medium | ✅ | - | - |
| B6 | Asset Registry Service (✅ Complete) | P0 | Medium | ✅ | - | B8 |
| B7 | Aesthetic Scoring (✅ Complete) | P1 | High | ✅ | - | - |
| B8 | API Endpoints (✅ Complete) | P0 | Medium | ⚠️ | B1, B6 | F1, F2, F3, F4 |

### Frontend Phases (v07)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| F1 | Asset Upload UI (✅ Complete) | P0 | Medium | ✅ | - | - |
| F2 | Data Tab Scene Classification (✅ Complete) | P0 | Medium | ✅ | - | - |
| F3 | Aesthetic Score Display (✅ Complete) | P1 | Medium | ⚠️ | B7 | - |
| F4 | Build Status UI (✅ Complete) | P0 | Low | ⚠️ | B8 | - |

### Output Phases (v07)

| Phase ID | Name | Priority | Complexity | Parallel? | Depends On | Blocks |
|----------|------|----------|------------|-----------|------------|--------|
| O1 | React SSG Template Project (✅ Complete) | P0 | Very High | ✅ | - | B4 |

### v07 Dependency Graph

```
Wave 1 - Start Immediately (no dependencies):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
O1 (React SSG Template Project ✅)
D1 (Graph State Schema Extension ✅)
B1 (LangGraph Orchestration Skeleton ✅)
F1 (Asset Upload UI ✅)
F2 (Data Tab Scene Classification ✅)
B5 (Mobile Shell Auto-fix ✅)
B6 (Asset Registry Service ✅)

Wave 2 - After O1:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B4 (React SSG Build Pipeline ✅)

Wave 3 - After B1 (LangGraph Skeleton):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B2 (Scene/Journey Capabilities ✅)
B8 (API Endpoints ✅)

Wave 4 - After B1, B2:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B3 (Component Registry Node ✅)

Wave 5 - After B3:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
(continues in B4 pipeline)

Wave 6 - After B7 (Backend):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
F3 (Aesthetic Score Display ✅)

Wave 7 - After B8 (API):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
F4 (Build Status UI ✅)
```

### v07 Migration Phases Mapping

| Migration | Phases | Description |
|-----------|--------|-------------|
| M1 | B1, B2, B3 | LangGraph Orchestration + Scene Detection + Component Registry |
| M2 | O1, B4 | React SSG Template + Build Pipeline |
| M3 | B5, B6 | Mobile Shell + Asset Registry |
| M4 | B7, F3 | Aesthetic Scoring + Display |
| M5 | B8, F1, F2, F4 | API Endpoints + Frontend UI |

### Historical Parallel Development Notes (v07)

You can run **4 Claude Code instances in parallel**:

1. **Frontend Agent**: F1 → F2 → F3 → F4 (can start with F1, F2)
2. **Backend Agent**: B5 → B6 (✅) → B1 (✅) → B2 (✅) → B3 (✅) → B4 (✅) → B8 → B7
3. **Template/Output Agent**: O1 (standalone, blocks B4, ✅ done)
4. **Database Agent**: D1 (standalone)

**Critical Path (v07)**: O1 → B4 → B8 → F4

**Independent Work (v07)**: B2 ✅, B3 ✅, B4 ✅, B5 ✅, B6 ✅, B7 ✅, B8 ✅, F1 🚧, F2 ✅, F3 ✅, F4 ✅, D1 ✅, O1 ✅

---

## Archived Version 0.6 Roadmap: Skills 编排 + Orchestrator 路由 + 多模型路由 + 数据传递 + 风格参考 + 移动端约束

**Last Updated**: 2026-02-05 (B7 Aesthetic Scoring planned; O1 complete)

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

### Historical Parallel Development Notes (v06)

You can run **3 Claude Code instances in parallel**:

1. **Frontend Agent**: F1 → F2 → F3 → F4
2. **Backend Agent**: B8 → B1 → B4 → B3 → B2 → B5 → B6 → B7
3. **Database Agent**: D1

**Critical Path (v06)**: B1 → B4 → B2 → B5 → O1

**Independent Work (v06)**: F1, F2, F3, F4, D1, B8

---

## Archived Version 0.5 Roadmap: (Placeholder)

| Version | Spec | Status | Key Features |
|---------|------|--------|--------------|
| v0.5 | spec-05.md | ✅ Complete | Version management, Responses API |

---

## Archived Version 0.4 Roadmap: Multi-Page Generation + Product Doc + Workbench (Complete ✅)

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

## Archived Version 0.3 Roadmap: Agent LLM Calling + Tools System (Complete ✅)

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

## Archived Version 0.2 Roadmap: Web Frontend + Planner (Complete ✅)

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

## Archived Version 0.1 Roadmap: CLI + Backend Core (Complete ✅)

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
│   ├── v10 - Generation Reliability + Dialogue Intelligence + Frontend Upgrade + Deployment + Analytics
│   │   ├── database/
│   │   │   └── v10-phase-d1-memory-analytics-schema.md
│   │   ├── backend/
│   │   │   ├── v10-phase-b1-token-calculation.md
│   │   │   ├── v10-phase-b2-structured-html-tool.md
│   │   │   ├── v10-phase-b3-atomic-batch-operations.md
│   │   │   ├── v10-phase-b4-provider-fallback.md
│   │   │   ├── v10-phase-b5-structured-compaction.md
│   │   │   ├── v10-phase-b6-askuser-timeout.md
│   │   │   ├── v10-phase-b7-interview-progress.md
│   │   │   ├── v10-phase-b8-cross-session-memory.md
│   │   │   ├── v10-phase-b9-context-injection.md
│   │   │   ├── v10-phase-b10-deploy-service.md
│   │   │   └── v10-phase-b11-analytics-service.md
│   │   ├── frontend/
│   │   │   ├── v10-phase-f1-zustand-state.md
│   │   │   ├── v10-phase-f2-split-projectpage.md
│   │   │   ├── v10-phase-f3-interview-progress-ui.md
│   │   │   ├── v10-phase-f4-deploy-button.md
│   │   │   ├── v10-phase-f5-qr-code.md
│   │   │   └── v10-phase-f6-data-tab-dashboard.md
│   │   └── output/
│   │       └── v10-phase-o1-analytics-script.md
│   │
│   ├── v09 - Soul Agentic Loop (LangGraph → Tool-Calling Loop)
│   │   ├── backend/
│   │   │   ├── v09-phase-b1-tool-foundation.md
│   │   │   ├── v09-phase-b2-core-tools.md
│   │   │   ├── v09-phase-b3-interview-ask-user.md
│   │   │   ├── v09-phase-b4-context-management.md
│   │   │   ├── v09-phase-b5-agentic-loop.md
│   │   │   ├── v09-phase-b6-llm-simplification.md
│   │   │   └── v09-phase-b7-api-integration-cleanup.md
│   │   └── frontend/
│   │       └── v09-phase-f1-product-doc-update-card.md
│   │
│   ├── v08 - Run-Centric Backend Refactor + App Data Layer
│   │   ├── database/
│   │   │   ├── v08-phase-d1-run-data-layer.md
│   │   │   └── v08-phase-d2-app-data-pg-schema.md
│   │   ├── backend/
│   │   │   ├── v08-phase-b1-run-service.md
│   │   │   ├── v08-phase-b2-event-layer-upgrade.md
│   │   │   ├── v08-phase-b3-orchestration-run-integration.md
│   │   │   ├── v08-phase-b4-chat-compat-adapter.md
│   │   │   ├── v08-phase-b5-tool-policy-hooks.md
│   │   │   ├── v08-phase-b6-verify-gate.md
│   │   │   ├── v08-phase-b7-app-data-api.md
│   │   │   └── v08-phase-b8-generation-integration.md
│   │   └── frontend/
│   │       └── v08-phase-f1-data-tab-overhaul.md
│   │
│   ├── e2e/
│   │   └── v06-e2e-test-plan.md
│   │
│   ├── v07 - LangGraph 编排 + React SSG + 场景旅程 + 组件一致性 + Mobile Shell
│   │   ├── database/
│   │   │   └── v07-phase-d1-graph-state.md
│   │   ├── backend/
│   │   │   ├── v07-phase-b1-langgraph-orchestration.md
│   │   │   ├── v07-phase-b2-scene-journey.md
│   │   │   ├── v07-phase-b3-component-registry.md
│   │   │   ├── v07-phase-b4-react-ssg-build.md
│   │   │   ├── v07-phase-b5-mobile-shell.md
│   │   │   ├── v07-phase-b6-asset-registry.md
│   │   │   ├── v07-phase-b7-aesthetic-scoring.md
│   │   │   └── v07-phase-b8-api-endpoints.md
│   │   ├── frontend/
│   │   │   ├── v07-phase-f1-asset-upload.md
│   │   │   ├── v07-phase-f2-data-tab-scene.md
│   │   │   ├── v07-phase-f3-aesthetic-score-display.md
│   │   │   └── v07-phase-f4-build-status.md
│   │   └── output/
│   │       └── v07-phase-o1-react-ssg-template.md
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

## Quick Start Commands for v0.8

```bash
# Database Developer
cat docs/phases/database/v08-phase-d1-run-data-layer.md
cat docs/phases/database/v08-phase-d2-app-data-pg-schema.md

# Backend Developer (Run System)
cat docs/phases/backend/v08-phase-b1-run-service.md
cat docs/phases/backend/v08-phase-b2-event-layer-upgrade.md
cat docs/phases/backend/v08-phase-b3-orchestration-run-integration.md
cat docs/phases/backend/v08-phase-b4-chat-compat-adapter.md
cat docs/phases/backend/v08-phase-b5-tool-policy-hooks.md
cat docs/phases/backend/v08-phase-b6-verify-gate.md

# Backend Developer (App Data)
cat docs/phases/backend/v08-phase-b7-app-data-api.md
cat docs/phases/backend/v08-phase-b8-generation-integration.md

# Frontend Developer
cat docs/phases/frontend/v08-phase-f1-data-tab-overhaul.md
```

## Quick Start Commands for v0.7

```bash
# Template/Output Developer
cat docs/phases/output/v07-phase-o1-react-ssg-template.md

# Database Developer
cat docs/phases/database/v07-phase-d1-graph-state.md

# Backend Developer
cat docs/phases/backend/v07-phase-b1-langgraph-orchestration.md
cat docs/phases/backend/v07-phase-b2-scene-journey.md
cat docs/phases/backend/v07-phase-b3-component-registry.md
cat docs/phases/backend/v07-phase-b4-react-ssg-build.md
cat docs/phases/backend/v07-phase-b5-mobile-shell.md
cat docs/phases/backend/v07-phase-b6-asset-registry.md
cat docs/phases/backend/v07-phase-b7-aesthetic-scoring.md
cat docs/phases/backend/v07-phase-b8-api-endpoints.md

# Frontend Developer
cat docs/phases/frontend/v07-phase-f1-asset-upload.md
cat docs/phases/frontend/v07-phase-f2-data-tab-scene.md
cat docs/phases/frontend/v07-phase-f3-aesthetic-score-display.md
cat docs/phases/frontend/v07-phase-f4-build-status.md

# E2E Test Plan (from v06)
cat docs/phases/e2e/v06-e2e-test-plan.md
```

---

## Quick Start Commands for v0.9

```bash
# Soul System Developer (Critical Path)
cat docs/phases/backend/v09-phase-b1-tool-foundation.md
cat docs/phases/backend/v09-phase-b2-core-tools.md
cat docs/phases/backend/v09-phase-b3-interview-ask-user.md
cat docs/phases/backend/v09-phase-b4-context-management.md
cat docs/phases/backend/v09-phase-b5-agentic-loop.md
cat docs/phases/backend/v09-phase-b7-api-integration-cleanup.md

# LLM Cleanup Developer (Independent)
cat docs/phases/backend/v09-phase-b6-llm-simplification.md

# Frontend Developer (After B7)
cat docs/phases/frontend/v09-phase-f1-product-doc-update-card.md
```

---

## Quick Start Commands for v1.0

```bash
# Database Developer
cat docs/phases/database/v10-phase-d1-memory-analytics-schema.md

# Backend Developer (Generation Reliability)
cat docs/phases/backend/v10-phase-b1-token-calculation.md
cat docs/phases/backend/v10-phase-b2-structured-html-tool.md
cat docs/phases/backend/v10-phase-b3-atomic-batch-operations.md
cat docs/phases/backend/v10-phase-b4-provider-fallback.md
cat docs/phases/backend/v10-phase-b5-structured-compaction.md

# Backend Developer (Dialogue Intelligence)
cat docs/phases/backend/v10-phase-b6-askuser-timeout.md
cat docs/phases/backend/v10-phase-b7-interview-progress.md
cat docs/phases/backend/v10-phase-b8-cross-session-memory.md
cat docs/phases/backend/v10-phase-b9-context-injection.md

# Backend Developer (Deployment & Analytics)
cat docs/phases/backend/v10-phase-b10-deploy-service.md
cat docs/phases/backend/v10-phase-b11-analytics-service.md

# Frontend Developer
cat docs/phases/frontend/v10-phase-f1-zustand-state.md
cat docs/phases/frontend/v10-phase-f2-split-projectpage.md
cat docs/phases/frontend/v10-phase-f3-interview-progress-ui.md
cat docs/phases/frontend/v10-phase-f4-deploy-button.md
cat docs/phases/frontend/v10-phase-f5-qr-code.md
cat docs/phases/frontend/v10-phase-f6-data-tab-dashboard.md

# Output Developer
cat docs/phases/output/v10-phase-o1-analytics-script.md
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
| v0.6 | spec-06.md | ✅ Complete | Skills, Orchestrator, Multi-model, Data Protocol, Style Ref |
| v0.7 | spec-07.md | ✅ Complete | LangGraph, React SSG, Scene Capabilities, Component Registry |
| v0.8 | spec-08.md | ✅ Complete | Run-Centric Backend, App Data Layer, Verify Gate, Tool Policy |
| v0.9 | spec-09.md | ✅ Complete | Soul Agentic Loop, Tool Registry, Interview V2, LangGraph Removal |
| v1.0 | spec-10.md | ⏳ Planned | Generation Reliability, Dialogue Intelligence, Frontend Upgrade, Deployment, Analytics |

---

**Document Version**: v8.0
**Last Updated**: 2026-02-13
**Total Phases (v10)**: 21 (1 Database, 11 Backend, 6 Frontend, 1 Output)
**Current Spec**: v1.0 - Generation Reliability + Dialogue Intelligence + Frontend Upgrade + Deployment Export + Analytics
