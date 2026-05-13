# Documentation Index

Last updated: 2026-05-13

## Current Guides

Use these documents for the current implementation:

- `../README.md`: project overview, quick start, environment variables, known current gaps.
- `../CLAUDE.md`: developer guide, architecture, route areas, test commands.
- `project-summary.md`: current implementation snapshot.
- `v10-summary.md`: status of the v1.0/v10 roadmap against the current codebase.
- `known_issue.md`: current known issues and resolved historical issues.
- `e2e-test-plan.md`: current backend/agent/web test plan.
- `frontend_design/project_page.md`: current ProjectPage layout and data flow.
- `run-agent-delivery-split.md`: current review lanes for run-agent delivery changes.

## Package Guides

- `../packages/backend/DEPENDENCIES.md`: backend dependency and test setup.
- `../packages/web/README.md`: web app routes, scripts, API client notes, e2e specs.

## Historical Planning Documents

These directories and files preserve product decisions, phase breakdowns, and earlier implementation plans. They are useful for intent and background, but not authoritative for current file layout, mounted APIs, or runtime behavior:

- `spec/`
- `phases/`
- `implementation-plan.md`
- `implementation-plan-cli-first.md`
- `vibe-coding-mobile-product-plan.md`
- `v03-summary.md` through `v09-summary.md`
- `dmxapi-responses-migration-plan.md`
- `code-generation-agents-analysis.md`

When a historical document conflicts with a current guide, follow the current guide and confirm against code.

## Maintenance Rule

Keep `docs/project-summary.md` as the canonical architecture and route inventory. When package layout, mounted routes, DB models, or runtime flows change, update that file first, then update only the short entry-point summaries that need to point readers there.
