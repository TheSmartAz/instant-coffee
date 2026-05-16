# Coding Agent Capability Snapshot

Last updated: 2026-05-16

## Current Capability

Instant Coffee now has a run-centric coding-agent loop that can:

- create and track run state through `/api/runs`;
- expose phase history, artifacts, review results, verification status, and project memory evidence in the Run Inspector;
- build a verification profile from run artifacts and memory notes;
- execute allowlisted verification commands from the backend;
- parse pytest, TypeScript, and ESLint failures into structured failure evidence with failure
  routing metadata for repair prompts and action audit flags;
- group routed verification failures in the Run Inspector by route/kind, including counts and
  route-specific fix hints;
- persist verification command results under run coordinator artifacts;
- request an automatic verification fix when the last verification run failed;
- persist each verification-fix attempt, including `running`, `passed`, `failed`, and `error` outcomes;
- rerun verification after a fix attempt and make the latest result visible to the UI.
- expose a verification audit trail for verification start/completion, automatic fix start/completion, and stale-attempt recovery.
- recover stale `running` verification-fix attempts so interrupted fixes do not block future retries.
- attach a change summary to each automatic verification-fix attempt, scoped to files newly changed during that attempt.
- run a Playwright-backed mobile visual smoke check against built static output when a build `dist_path` is available.
- persist visual verification status, quality score, screenshot path, errors, and warnings under run artifacts.
- expose non-HTML workspace files under the file tree `workspace/` folder so coding-agent file writes are visible alongside DB-backed HTML pages.
- build directly from agent-authored workspace React source when `src/App.tsx` or `src/pages/*.tsx` exists, falling back to the DB HTML path otherwise.
- request, resolve, and audit shell-command approvals through run-scoped events and the Run Inspector.

## Two-Layer Model

Instant Coffee separates the user's workflow intent from the agent's execution authority.

### Workflow Layer

The workflow layer describes what kind of conversation the user is having:

| Workflow | Purpose | Output |
| --- | --- | --- |
| Chat | Discuss, refine requirements, answer questions, update context, or request changes. | Assistant response, product-doc updates, run events, and optional generated artifacts. |
| Plan | Convert the request into a structured implementation path before code generation. | Plan-phase run events and task/step context for the execution layer. |

The workflow layer should not be treated as a safety switch. It decides whether the product is in a conversational or planning posture.

### Execution Layer

The execution layer controls how much authority the agent has when a run reaches implementation:

| Execution mode | API value | Behavior |
| --- | --- | --- |
| Plan only | `plan` | Stop after planning. Do not apply implementation changes. |
| Agent | `agent` | Execute with normal agent guardrails, review, build, verification, and fix opportunities. |
| Auto | `auto` | Execute the full run path with the highest local autonomy available to the product. |

The web UI exposes these modes as `Plan only`, `Agent`, and `Auto`. Backend schemas accept both `execution_mode` and the legacy `approval_mode` field, then mirror the normalized value across both names.

## Legacy YOLO Compatibility

Older clients may still send:

```json
{
  "approval_mode": "yolo"
}
```

The backend treats `yolo` as a legacy alias for `auto`. New clients should send:

```json
{
  "execution_mode": "auto"
}
```

Compatibility rules:

- `yolo` is accepted only as input compatibility.
- persisted run metrics and API responses normalize it to `auto`.
- unknown mode values fall back to `agent`.
- `approval_mode` remains a compatibility alias; `execution_mode` is the preferred product term.

## Safety Boundaries

Execution modes change local run behavior, not global trust boundaries.

- Plan-only runs must not write implementation changes.
- Agent and Auto runs still pass through the run coordinator, build/review phases, event persistence, and run-state tracking.
- Agent and Auto runs may request shell approval for commands that trip the shell safety guard.
- Plan-only runs block shell execution and file write tools instead of asking for approval.
- Verification and automatic verification-fix endpoints require the configured admin token.
- Backend verification runs only allowlisted commands.
- Automatic verification fixes are scoped to failed verification evidence and record a change summary.
- Verification and fix actions record a redacted action audit trail without prompt text, engine payloads, raw diffs, or command output.
- Automatic verification fixes pass through an acceptance gate: low/medium-risk passing fixes are accepted automatically; high-risk, sensitive, or non-passing fixes are blocked until admin resolution.
- Blocked fix gates include deterministic reviewer recommendations and can refresh those recommendations through an admin endpoint.
- The product should show `auto` as higher-autonomy execution, not as permission to bypass authentication, command allowlists, run cancellation, review evidence, or audit trails.

## API Surface

Run detail responses include:

- `verification.checks`: build and review-derived checks;
- `verification.checks[]` may include a `visual` check with a deterministic quality score and screenshot path;
- `verification.profile`: recommended verification commands, risk flags, and memory keys;
- `verification.last_run`: the most recent command-level verification result;
- `verification.last_run.commands[].failures[]`: structured command failures, including safe
  `route`, `kind`, and `fix_hint` fields for UI grouping and fix prompts when available;
- `verification.fix_attempts`: automatic verification-fix attempts and their evidence;
- `verification.fix_attempts[].change_summary`: file count, changed file paths, risk level, risk flags, captured timestamp, and the verification status linked to the attempted fix;
- `verification.fix_attempts[].gate`: acceptance status, decision, reasons, deterministic reviewer recommendation, and optional admin resolution timestamp;
- `verification.audit_trail`: ordered verification/fix/recovery events with status, timestamps, attempt number, command count, failure count, and risk flags;
- `verification.action_audit_trail`: redacted command/edit/agent/visual action events with status, command metadata, duration, file count, risk level, and timestamps;
- `context.memory`: project memory categories used to shape verification.

Mutation endpoints:

- `POST /api/runs/{run_id}/approvals/{approval_id}`
  - Resolves a live shell approval request with `{ "approved": true | false }`.
  - Requires the run to still be active and the approval request to still be pending.
  - Records `shell_approval_resolved` in the run timeline.
- `POST /api/runs/{run_id}/verification`
  - Requires admin token.
  - Runs the verification profile and stores `artifacts.verification_run`.
  - If the latest build artifact has `dist_path`, runs the mobile visual smoke check and stores `artifacts.visual_verification`.
- `POST /api/runs/{run_id}/fix-verification`
  - Requires admin token.
  - Requires a failed `verification.last_run`.
  - Rejects concurrent fix requests for the same run.
  - Persists a `running` fix attempt before calling the engine.
  - Calls the existing engine orchestrator with a failure-focused fix prompt.
  - Reruns verification and updates `artifacts.verification_run`.
  - Captures a diff-style change summary from the worktree baseline around the fix attempt, without exposing raw diff content.
  - Records action-audit events for prompt preparation, agent execution, verification rerun commands, and edit summary, without exposing prompt text or engine payload.
  - Evaluates a fix gate and blocks high-risk or non-passing fixes from being considered accepted.
  - Returns a normal run response even when the fix attempt records an `error`, so the UI can show saved evidence.
  - Marks stale `running` attempts as `stale_error` before retrying when they exceed the recovery timeout.
- `POST /api/runs/{run_id}/fix-verification/{attempt_number}/gate`
  - Requires admin token.
  - Approves or rejects a blocked automatic-fix gate with `{ "approved": true | false }`.
  - Rejects gates that are already resolved so duplicate admin actions do not rewrite a decision.
  - Records a redacted gate-resolution action event.
- `POST /api/runs/{run_id}/fix-verification/{attempt_number}/gate/review`
  - Requires admin token.
  - Refreshes the deterministic reviewer recommendation for a fix gate.
  - Records a redacted reviewer action event.

## Verification Commands

The backend runner only executes allowlisted commands:

- `PYTHONPATH=.:../agent/src python -m pytest -q` in `packages/backend`
- `npm run lint` in `packages/web`
- `npm run build` in `packages/web`
- `npx playwright test` in `packages/web`, only when the verification profile includes it

Unknown commands are skipped and recorded as skipped results.

## Visual Verification

Visual verification is intentionally a smoke gate, not a full design judge. It opens the built
static page in a 390x844 mobile viewport with Playwright, captures `mobile.png`, and checks:

- page file exists and loads;
- body text is not blank;
- layout has mobile-sized area;
- console and page errors are clean;
- visible touch targets are at least 44x44px.

The score is deterministic from these checks with a small warning penalty. The service skips
cleanly when no `dist_path` is available or Playwright is not installed.

## Project File Visibility

The build runner now supports two compatible source paths:

- `workspace`: if the session workspace contains React source such as `src/App.tsx` or
  `src/pages/*.tsx`, the builder copies the React SSG template, overlays workspace `src/`,
  `public/`, and safe root config files, writes a prerender manifest when needed, and builds
  that source directly.
- `html`: if no workspace React source exists, the builder keeps the existing DB HTML
  `HTML -> React -> static build` path.

Direct coding-agent writes to non-HTML workspace files are surfaced in the file tree under
`workspace/`, so users can inspect the actual project files that drove source-mode builds.

## Maturity Gaps

The loop is usable, but not yet a fully mature coding agent. The next maturity layer should add:

- replacing the deterministic reviewer recommendation with an LLM-backed reviewer agent that uses the same redaction and gate contract;
- route-specific fix policies beyond the current pytest, ESLint, TypeScript, build, Playwright,
  and runner labels;
- deeper action audit coverage for normal build/review/generation phases outside the verification-fix loop;
- dependency-aware source-mode builds for agent-authored `package.json` changes, with package
  allowlists and clear install/audit evidence;
- a real provider/browser dogfood scenario that intentionally fails verification, runs automatic fix,
  and proves the final verification passes outside mocked API tests.

## Acceptance Evidence

The current M1-M5 closeout is verified by:

- backend targeted tests for run API, memory, review, coordinator, verification runner, and verification fix;
- an API-level dogfood test that fails verification, runs automatic fix, records change summary,
  accepts the low/medium-risk fix gate, and proves final verification passes without leaking raw
  prompt, engine, failure, or command-output details;
- Run Inspector Playwright coverage for streamed run state, grouped verification failure routes,
  fix-verification requests, deterministic gate review, and admin gate approval refresh;
- an opt-in real-provider smoke that creates a durable chat run and executes run verification,
  while intentionally avoiding automatic fix attempts against the live worktree;
- a second, doubly gated real-provider dogfood path can invoke automatic verification fix when
  the real verification run fails, requiring explicit acknowledgement that the live worktree may
  be edited;
- web lint;
- web production build.

Known non-blocking warning: Vite reports an existing chunk-size warning for a large generated bundle.
