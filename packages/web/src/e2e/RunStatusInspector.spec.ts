/// <reference types="node" />

import { test, expect, type Page } from 'playwright/test'
import type { RunEventResponse, SessionRunDetail } from '../types'

const now = '2026-05-13T10:00:00.000Z'
const sessionId = 'run-ui-session'
const runId = 'run-abcdef1234567890'

const mockSettings = {
  model: 'gpt-4o-mini',
  available_models: [{ id: 'gpt-4o-mini', label: 'GPT-4o Mini' }],
}

function runDetail(overrides: Partial<SessionRunDetail> = {}): SessionRunDetail {
  return {
    run_id: runId,
    session_id: sessionId,
    status: 'failed',
    created_at: now,
    updated_at: now,
    started_at: now,
    finished_at: now,
    latest_error: { code: 'review_failed', message: 'Review found blocking issues' },
    metrics: null,
    checkpoint_thread: `${sessionId}:${runId}`,
    checkpoint_ns: null,
    waiting_reason: null,
    current_phase: 'review',
    phase_status: 'failed',
    phase_metadata: { phase: 'review', status: 'failed' },
    phase_history: [
      { phase: 'implement', status: 'completed' },
      { phase: 'build', status: 'completed' },
      { phase: 'review', status: 'failed', error: 'Review found blocking issues' },
    ],
    artifacts: { dist_path: 'dist/run-ui-session' },
    fix_attempts: 1,
    last_review: null,
    review_summary: {
      error_count: 1,
      warning_count: 0,
      build_status: 'success',
      generated_pages: ['index.html'],
    },
    review_issues: [
      {
        code: 'missing_button_label',
        severity: 'error',
        message: 'Primary action needs an accessible label.',
      },
    ],
    verification: {
      status: 'failed',
      passed: false,
      checks: [],
      evidence: [],
      summary: {},
      profile: {
        recommended_commands: [
          {
            name: 'backend targeted tests',
            command: 'PYTHONPATH=.:../agent/src python -m pytest -q',
            scope: 'backend',
          },
        ],
        risk_flags: ['verification_failed'],
        memory_keys: [],
      },
      last_run: {
        status: 'failed',
        passed: false,
        commands: [
          {
            name: 'backend targeted tests',
            command: 'PYTHONPATH=.:../agent/src python -m pytest -q',
            scope: 'backend',
            status: 'failed',
            exit_code: 1,
            duration_ms: 12,
            output_summary: '',
            failures: [
              {
                file: 'app/services/review.py',
                line: 88,
                source: 'pytest',
                route: 'pytest',
                kind: 'backend_test',
                fix_hint: 'Fix the failing Python test or the backend behavior it protects, then rerun backend tests.',
              },
              {
                file: 'app/services/run.py',
                line: 42,
                source: 'pytest',
                route: 'pytest',
                kind: 'backend_test',
                fix_hint: 'Fix the failing Python test or the backend behavior it protects, then rerun backend tests.',
              },
              {
                file: 'src/components/custom/RunInspector.tsx',
                line: 12,
                source: 'eslint',
                route: 'eslint',
                kind: 'frontend_lint',
                fix_hint: 'Fix the frontend lint violation, then rerun web lint.',
              },
            ],
          },
        ],
        risk_flags: ['verification_failed'],
      },
      fix_attempts: [],
      audit_trail: [],
      action_audit_trail: [],
    },
    heartbeat_at: now,
    ...overrides,
  }
}

const json = (body: unknown) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(body),
})

const eventStream = (events: unknown[]) => ({
  status: 200,
  contentType: 'text/event-stream',
  headers: { 'Cache-Control': 'no-cache' },
  body: `${events.map((event) => `data: ${typeof event === 'string' ? event : JSON.stringify(event)}`).join('\n\n')}\n\n`,
})

async function installEventSourceMock(page: Page) {
  await page.addInitScript(() => {
    type MockMessage = { data: string }
    type MockOpen = { type: 'open' }

    class MockEventSource {
      static instances: MockEventSource[] = []
      url: string
      readyState = 0
      onopen: ((event: MockOpen) => void) | null = null
      onmessage: ((event: MockMessage) => void) | null = null
      onerror: ((event: Event) => void) | null = null

      constructor(url: string) {
        this.url = url
        MockEventSource.instances.push(this)
        window.setTimeout(() => {
          this.readyState = 1
          this.onopen?.({ type: 'open' })
        }, 0)
      }

      close() {
        this.readyState = 2
      }

      emit(data: unknown) {
        this.onmessage?.({
          data: typeof data === 'string' ? data : JSON.stringify(data),
        })
      }
    }

    const controls = {
      emit(data: unknown) {
        const source = MockEventSource.instances.at(-1)
        if (!source) throw new Error('No EventSource instance')
        source.emit(data)
      },
      count() {
        return MockEventSource.instances.length
      },
    }

    Object.assign(window, {
      EventSource: MockEventSource,
      __runSse: controls,
    })
  })
}

async function setupProjectMocks(
  page: Page,
  options: {
    getRun: () => SessionRunDetail
    onCancel?: () => SessionRunDetail
    onResolveApproval?: (approved: boolean) => SessionRunDetail
    onFixVerification?: () => SessionRunDetail
    onReviewFixGate?: (attempt: number) => SessionRunDetail
    onResolveFixGate?: (attempt: number, approved: boolean) => SessionRunDetail
    runEvents?: RunEventResponse[]
    chatEvents?: unknown[]
    build?: unknown
  }
) {
  await page.route('**/api/settings', (route) => route.fulfill(json(mockSettings)))
  await page.route(`**/api/sessions/${sessionId}`, (route) =>
    route.fulfill(json({
      id: sessionId,
      title: 'Run UI Test Session',
      created_at: now,
      updated_at: now,
      current_version: 1,
    }))
  )
  await page.route(`**/api/sessions/${sessionId}/metadata`, (route) =>
    route.fulfill(json({ id: sessionId, aesthetic_scores: null }))
  )
  await page.route(`**/api/sessions/${sessionId}/messages**`, (route) =>
    route.fulfill(json({ messages: [] }))
  )
  await page.route(`**/api/sessions/${sessionId}/versions**`, (route) =>
    route.fulfill(json({ versions: [], current_version: 1 }))
  )
  await page.route(`**/api/sessions/${sessionId}/threads`, (route) =>
    route.fulfill(json({ threads: [{ id: 'thread-1', session_id: sessionId, title: 'Main', created_at: now, updated_at: now, message_count: 0 }] }))
  )
  await page.route(`**/api/sessions/${sessionId}/cost`, (route) =>
    route.fulfill(json({
      session_id: sessionId,
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
      cost_usd: 0,
      by_agent: {},
    }))
  )
  await page.route(`**/api/sessions/${sessionId}/pages`, (route) =>
    route.fulfill(json({ pages: [], total: 0 }))
  )
  await page.route(`**/api/sessions/${sessionId}/product-doc`, (route) =>
    route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Not found' }),
    })
  )
  await page.route(`**/api/sessions/${sessionId}/product-doc/history**`, (route) =>
    route.fulfill(json({ history: [], pinned_count: 0 }))
  )
  await page.route(`**/api/sessions/${sessionId}/snapshots**`, (route) =>
    route.fulfill(json({ snapshots: [] }))
  )
  await page.route(`**/api/sessions/${sessionId}/files`, (route) =>
    route.fulfill(json({ tree: [] }))
  )
  await page.route(`**/api/sessions/${sessionId}/build/status`, (route) =>
    route.fulfill(json(options.build ?? { status: 'idle', pages: [] }))
  )
  await page.route(`**/preview/${sessionId}/**`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/html',
      body: '<!doctype html><html><body><main>Build preview ready</main></body></html>',
    })
  )
  await page.route(`**/api/sessions/${sessionId}/events**`, (route) =>
    route.fulfill(json({ events: [], last_seq: 0, has_more: false }))
  )
  await page.route(/\/api\/runs\?/, (route) =>
    route.fulfill(json({ runs: [options.getRun()], total: 1 }))
  )
  await page.route(`**/api/runs/${runId}/events**`, (route) =>
    route.fulfill(json({ events: options.runEvents ?? [], last_seq: options.runEvents?.length ?? 0, has_more: false }))
  )
  await page.route(`**/api/runs/${runId}/approvals/*`, async (route) => {
    const body = route.request().postDataJSON() as { approved?: boolean }
    const detail = options.onResolveApproval?.(Boolean(body.approved)) ?? options.getRun()
    return route.fulfill(json(detail))
  })
  await page.route(`**/api/runs/${runId}/fix-verification`, (route) => {
    const detail = options.onFixVerification?.() ?? options.getRun()
    return route.fulfill(json(detail))
  })
  await page.route(`**/api/runs/${runId}/fix-verification/*/gate/review`, (route) => {
    const match = route.request().url().match(/\/fix-verification\/(\d+)\/gate\/review/)
    const attempt = match ? Number(match[1]) : 1
    const detail = options.onReviewFixGate?.(attempt) ?? options.getRun()
    return route.fulfill(json(detail))
  })
  await page.route(`**/api/runs/${runId}/fix-verification/*/gate`, (route) => {
    const match = route.request().url().match(/\/fix-verification\/(\d+)\/gate/)
    const attempt = match ? Number(match[1]) : 1
    const body = route.request().postDataJSON() as { approved?: boolean }
    const detail = options.onResolveFixGate?.(attempt, Boolean(body.approved)) ?? options.getRun()
    return route.fulfill(json(detail))
  })
  await page.route(`**/api/runs/${runId}`, (route) =>
    route.fulfill(json(options.getRun()))
  )
  await page.route(`**/api/runs/${runId}/cancel`, (route) => {
    const cancelled = options.onCancel?.() ?? options.getRun()
    return route.fulfill(json(cancelled))
  })
  await page.route('**/api/chat/stream**', (route) =>
    route.fulfill(eventStream(options.chatEvents ?? ['[DONE]']))
  )
}

test.describe('Run status and inspector', () => {
  const shellApprovalEvent: RunEventResponse = {
    id: 1,
    session_id: sessionId,
    seq: 1,
    type: 'shell_approval',
    run_id: runId,
    source: 'engine',
    created_at: now,
    payload: {
      approval_id: 'approval-1',
      command: 'rm -rf ./dist --force',
      reason: 'Recursive force delete on sensitive path',
      execution_mode: 'agent',
    },
  }

  const shellApprovalResolvedEvent: RunEventResponse = {
    id: 2,
    session_id: sessionId,
    seq: 2,
    type: 'shell_approval_resolved',
    run_id: runId,
    source: 'engine',
    created_at: now,
    payload: {
      approval_id: 'approval-1',
      approved: true,
    },
  }

  test('updates run status as SSE events arrive incrementally', async ({ page }) => {
    await installEventSourceMock(page)
    await setupProjectMocks(page, {
      getRun: () =>
        runDetail({
          status: 'running',
          finished_at: null,
          latest_error: null,
          current_phase: 'review',
          phase_status: 'running',
          review_summary: null,
          review_issues: [],
        }),
      chatEvents: [],
    })

    await page.goto(`/project/${sessionId}`)
    await page.getByTestId('chat-textarea').fill('Build a run lifecycle test page')
    await page.getByRole('button', { name: 'Send message' }).click()

    await expect
      .poll(() => page.evaluate(() => (window as unknown as { __runSse: { count: () => number } }).__runSse.count()))
      .toBe(1)

    await page.evaluate(
      ({ runId, now }) =>
        (window as unknown as { __runSse: { emit: (data: unknown) => void } }).__runSse.emit({
          type: 'build_complete',
          run_id: runId,
          timestamp: now,
          payload: {
            status: 'success',
            pages: ['index.html'],
            dist_path: 'dist/run-ui-session',
          },
        }),
      { runId, now },
    )
    await expect(page.getByTestId('run-status-strip')).toContainText('Build complete')
    await expect(page.getByTestId('run-status-strip')).toContainText('1 pages')
    await expect(page.getByTestId('run-status-strip')).toContainText('dist ready')

    await page.evaluate(
      ({ runId, now }) =>
        (window as unknown as { __runSse: { emit: (data: unknown) => void } }).__runSse.emit({
          type: 'verify_start',
          run_id: runId,
          timestamp: now,
          payload: { phase: 'review', status: 'running' },
        }),
      { runId, now },
    )
    await expect(page.getByTestId('run-status-strip')).toContainText('Review running')
    await expect(page.getByTestId('run-status-strip')).not.toContainText('Build complete')

    await page.evaluate(
      ({ runId, now }) =>
        (window as unknown as { __runSse: { emit: (data: unknown) => void } }).__runSse.emit({
          type: 'verify_fail',
          run_id: runId,
          timestamp: now,
          payload: {
            phase: 'review',
            status: 'failed',
            summary: {
              error_count: 1,
              warning_count: 0,
              build_status: 'success',
              generated_pages: ['index.html'],
            },
          },
        }),
      { runId, now },
    )
    await expect(page.getByTestId('run-status-strip')).toContainText('Review failed')
    await expect(page.getByTestId('run-status-strip')).toContainText('1 errors')
    await expect(page.getByTestId('run-status-strip')).toContainText('1 pages')

    await page.evaluate(() =>
      (window as unknown as { __runSse: { emit: (data: unknown) => void } }).__runSse.emit('[DONE]'),
    )
  })

  test('shows streamed shell approval and posts approval decision', async ({ page }) => {
    let approvedPayload: boolean | null = null
    await installEventSourceMock(page)
    await setupProjectMocks(page, {
      getRun: () =>
        runDetail({
          status: 'waiting_input',
          finished_at: null,
          latest_error: null,
          waiting_reason: 'Shell command approval required',
          current_phase: 'implement',
          phase_status: 'waiting_input',
          execution_mode: 'agent',
          review_summary: null,
          review_issues: [],
        }),
      onResolveApproval: (approved) => {
        approvedPayload = approved
        return runDetail({
          status: 'running',
          finished_at: null,
          latest_error: null,
          current_phase: 'implement',
          phase_status: 'running',
          execution_mode: 'agent',
          review_summary: null,
          review_issues: [],
        })
      },
      chatEvents: [],
    })

    await page.goto(`/project/${sessionId}`)
    await page.getByTestId('chat-textarea').fill('Build a run lifecycle test page')
    await page.getByRole('button', { name: 'Send message' }).click()

    await expect
      .poll(() => page.evaluate(() => (window as unknown as { __runSse: { count: () => number } }).__runSse.count()))
      .toBe(1)

    await page.evaluate(
      (event) =>
        (window as unknown as { __runSse: { emit: (data: unknown) => void } }).__runSse.emit(event),
      shellApprovalEvent,
    )

    await expect(page.getByTestId('run-status-strip')).toContainText('waiting input')
    await expect(page.getByTestId('shell-approval-card')).toBeVisible()
    await expect(page.getByTestId('shell-approval-card')).toContainText('Recursive force delete on sensitive path')
    await expect(page.getByTestId('shell-approval-card')).toContainText('rm -rf ./dist --force')

    await page.getByTestId('shell-approval-approve').click()

    await expect.poll(() => approvedPayload).toBe(true)
    await expect(page.getByTestId('run-inspector')).toContainText('running')
  })

  test('replays unresolved shell approval from run events', async ({ page }) => {
    await setupProjectMocks(page, {
      getRun: () =>
        runDetail({
          status: 'waiting_input',
          finished_at: null,
          latest_error: null,
          waiting_reason: 'Shell command approval required',
          current_phase: 'implement',
          phase_status: 'waiting_input',
          execution_mode: 'agent',
          review_summary: null,
          review_issues: [],
        }),
      runEvents: [shellApprovalEvent],
    })

    await page.goto(`/project/${sessionId}`)

    await expect(page.getByTestId('shell-approval-card')).toBeVisible()
    await expect(page.getByTestId('shell-approval-card')).toContainText('Recursive force delete on sensitive path')
    await expect(page.getByTestId('shell-approval-card')).toContainText('rm -rf ./dist --force')
  })

  test('does not replay resolved shell approval from run events', async ({ page }) => {
    await setupProjectMocks(page, {
      getRun: () =>
        runDetail({
          status: 'waiting_input',
          finished_at: null,
          latest_error: null,
          waiting_reason: 'Shell command approval required',
          current_phase: 'implement',
          phase_status: 'waiting_input',
          execution_mode: 'agent',
          review_summary: null,
          review_issues: [],
        }),
      runEvents: [shellApprovalEvent, shellApprovalResolvedEvent],
    })

    await page.goto(`/project/${sessionId}`)

    await expect(page.getByTestId('run-inspector')).toBeVisible()
    await expect(page.getByTestId('shell-approval-card')).toHaveCount(0)
  })

  test('renders streamed run status and inspector details', async ({ page }) => {
    const detail = runDetail()
    await setupProjectMocks(page, {
      getRun: () => detail,
      chatEvents: [
        { type: 'run_started', run_id: runId, phase: 'implement', status: 'running', timestamp: now },
        { type: 'build_complete', run_id: runId, timestamp: now, payload: { status: 'success', pages: ['index.html'], dist_path: 'dist/run-ui-session' } },
        { type: 'verify_fail', run_id: runId, timestamp: now, summary: { error_count: 1, warning_count: 0, build_status: 'success' } },
        '[DONE]',
      ],
    })

    await page.goto(`/project/${sessionId}`)
    await page.getByTestId('chat-textarea').fill('Build a run lifecycle test page')
    await page.getByRole('button', { name: 'Send message' }).click()

    await expect(page.getByTestId('run-status-strip')).toContainText('Review failed')
    await expect(page.getByTestId('run-status-strip')).toContainText('1 errors')
    await expect(page.getByTestId('run-status-strip')).toContainText(runId.slice(0, 10))

    await page.getByTestId('run-inspector-toggle').click()
    await expect(page.getByTestId('run-inspector')).toContainText('Review')
    await expect(page.getByTestId('run-inspector')).toContainText('failed')
    await expect(page.getByTestId('run-inspector-artifacts')).toContainText('1 generated')
    await expect(page.getByTestId('run-inspector-artifacts')).toContainText('dist/run-ui-session')
    await expect(page.getByTestId('run-inspector-open-build')).toBeEnabled()
    await expect(page.getByTestId('run-inspector')).toContainText('missing_button_label')
    await expect(page.getByTestId('run-inspector')).toContainText('Primary action needs an accessible label.')
    await expect(page.getByTestId('run-inspector')).toContainText('Review found blocking issues')
    await expect(page.getByTestId('verification-failure-routes')).toContainText('pytest · backend test (2)')
    await expect(page.getByTestId('verification-failure-routes')).toContainText('eslint · frontend lint')
    await expect(page.getByTestId('run-inspector-verification')).toContainText('rerun backend tests')
  })

  test('fixes verification and resolves a blocked fix gate from the inspector', async ({ page }) => {
    let detail = runDetail()
    let fixRequests = 0
    let reviewRequests = 0
    let approvedPayload: boolean | null = null

    await setupProjectMocks(page, {
      getRun: () => detail,
      onFixVerification: () => {
        fixRequests += 1
        detail = runDetail({
          status: 'waiting_input',
          current_phase: 'fix',
          phase_status: 'waiting_input',
          waiting_reason: 'Verification fix gate requires admin decision',
          latest_error: null,
          fix_attempts: 2,
          verification: {
            ...detail.verification!,
            status: 'failed',
            fix_attempts: [
              {
                attempt: 1,
                status: 'blocked',
                prompt: 'Fix verification failures',
                failures: detail.verification?.last_run?.commands[0].failures ?? [],
                change_summary: {
                  status: 'captured',
                  changed_files: ['packages/backend/app/services/review.py'],
                  file_count: 1,
                  risk_level: 'medium',
                  risk_flags: ['verification_failed'],
                  verification_status: 'failed',
                  captured_at: now,
                },
                gate: {
                  status: 'blocked',
                  decision: 'requires_review',
                  reasons: ['verification_failed'],
                  evaluated_at: now,
                  approved: null,
                  approved_at: null,
                  reviewer: null,
                },
                error: null,
                started_at: now,
                completed_at: now,
              },
            ],
          },
        })
        return detail
      },
      onReviewFixGate: (attempt) => {
        reviewRequests += attempt
        detail = runDetail({
          ...detail,
          verification: {
            ...detail.verification!,
            fix_attempts: detail.verification!.fix_attempts!.map((item) =>
              item.attempt === attempt
                ? {
                    ...item,
                    gate: {
                      ...item.gate!,
                      reviewer: {
                        source: 'deterministic',
                        recommendation: 'accept',
                        summary: 'The change is limited and ready for admin approval.',
                        reasons: ['low_blast_radius'],
                        checklist: ['Reviewed changed files'],
                        changed_files: ['packages/backend/app/services/review.py'],
                        verification_status: 'failed',
                        reviewed_at: now,
                      },
                    },
                  }
                : item,
            ),
          },
        })
        return detail
      },
      onResolveFixGate: (attempt, approved) => {
        approvedPayload = approved
        detail = runDetail({
          ...detail,
          status: 'completed',
          current_phase: 'done',
          phase_status: 'completed',
          waiting_reason: null,
          latest_error: null,
          verification: {
            ...detail.verification!,
            status: 'passed',
            passed: true,
            last_run: {
              ...detail.verification!.last_run!,
              status: 'passed',
              passed: true,
              commands: detail.verification!.last_run!.commands.map((command) => ({
                ...command,
                status: 'passed',
                exit_code: 0,
                failures: [],
              })),
            },
            fix_attempts: detail.verification!.fix_attempts!.map((item) =>
              item.attempt === attempt
                ? {
                    ...item,
                    status: 'accepted',
                    gate: {
                      ...item.gate!,
                      status: 'accepted',
                      decision: approved ? 'accepted' : 'rejected',
                      approved,
                      approved_at: now,
                    },
                  }
                : item,
            ),
          },
        })
        return detail
      },
    })

    await page.goto(`/project/${sessionId}`)
    await page.getByTestId('run-inspector-toggle').click()

    await page.getByTestId('run-inspector-fix-verification').click()
    await expect.poll(() => fixRequests).toBe(1)
    await expect(page.getByTestId('run-inspector')).toContainText('Gate · blocked')
    await expect(page.getByTestId('run-inspector')).toContainText('verification failed')

    await page.getByTestId('run-inspector-review-fix-gate').click()
    await expect.poll(() => reviewRequests).toBe(1)
    await expect(page.getByTestId('run-inspector')).toContainText('Reviewer · accept')
    await expect(page.getByTestId('run-inspector')).toContainText('ready for admin approval')

    await page.getByTestId('run-inspector-approve-fix-gate').click()
    await expect.poll(() => approvedPayload).toBe(true)
    await expect(page.getByTestId('run-inspector')).toContainText('Gate · accepted · accepted')
    await expect(page.getByTestId('run-inspector-verification')).toContainText('passed')
  })

  test('renders review running from verify_start', async ({ page }) => {
    const detail = runDetail({
      status: 'running',
      finished_at: null,
      latest_error: null,
      current_phase: 'review',
      phase_status: 'running',
      review_summary: null,
      review_issues: [],
    })
    await setupProjectMocks(page, {
      getRun: () => detail,
      chatEvents: [
        { type: 'build_complete', run_id: runId, timestamp: now, payload: { status: 'success', pages: ['index.html'], dist_path: 'dist/run-ui-session' } },
        { type: 'verify_start', run_id: runId, timestamp: now, payload: { phase: 'review', status: 'running' } },
        '[DONE]',
      ],
    })

    await page.goto(`/project/${sessionId}`)
    await page.getByTestId('chat-textarea').fill('Build a run lifecycle test page')
    await page.getByRole('button', { name: 'Send message' }).click()

    await expect(page.getByTestId('run-status-strip')).toContainText('Review running')
    await expect(page.getByTestId('run-status-strip')).toContainText(runId.slice(0, 10))
  })

  for (const verdict of ['verify_fail', 'verify_pass'] as const) {
    test(`keeps build preview available after ${verdict}`, async ({ page }) => {
      const detail = runDetail({
        status: verdict === 'verify_pass' ? 'completed' : 'failed',
        latest_error:
          verdict === 'verify_pass'
            ? null
            : { code: 'review_failed', message: 'Review found blocking issues' },
        current_phase: verdict === 'verify_pass' ? 'done' : 'review',
        phase_status: verdict === 'verify_pass' ? 'completed' : 'failed',
        review_summary: {
          error_count: verdict === 'verify_pass' ? 0 : 1,
          warning_count: 0,
          build_status: 'success',
          generated_pages: ['index.html'],
        },
        review_issues:
          verdict === 'verify_pass'
            ? []
            : [
                {
                  code: 'missing_button_label',
                  severity: 'error',
                  message: 'Primary action needs an accessible label.',
                },
              ],
      })
      await setupProjectMocks(page, {
        getRun: () => detail,
        chatEvents: [
          { type: 'build_complete', run_id: runId, timestamp: now, payload: { status: 'success', pages: ['index.html'], dist_path: 'dist/run-ui-session' } },
          { type: 'verify_start', run_id: runId, timestamp: now, payload: { phase: 'review', status: 'running' } },
          { type: verdict, run_id: runId, timestamp: now, payload: { phase: 'review', status: verdict === 'verify_pass' ? 'completed' : 'failed', summary: { error_count: verdict === 'verify_pass' ? 0 : 1, warning_count: 0, build_status: 'success', generated_pages: ['index.html'] } } },
          '[DONE]',
        ],
      })

      await page.goto(`/project/${sessionId}`)
      await page.getByTestId('chat-textarea').fill('Build a run lifecycle test page')
      await page.getByRole('button', { name: 'Send message' }).click()

      await expect(page.getByTestId('run-status-strip')).toContainText(
        verdict === 'verify_pass' ? 'Review passed' : 'Review failed',
      )
      await page.getByRole('button', { name: 'Build' }).click()
      await expect(page.getByTestId('preview-iframe')).toBeVisible()
      await expect(page.getByText('Build output not available')).toHaveCount(0)
      await expect(page.getByTestId('preview-iframe')).toHaveAttribute(
        'src',
        new RegExp(`/preview/${sessionId}/index\\.html`),
      )
    })
  }

  test('cancels a waiting run from the inspector', async ({ page }) => {
    let detail = runDetail({
      status: 'waiting_input',
      current_phase: 'review',
      phase_status: 'waiting_input',
      waiting_reason: 'Review needs user feedback',
      latest_error: null,
      finished_at: null,
      review_summary: null,
      review_issues: [],
    })
    let cancelRequests = 0
    await setupProjectMocks(page, {
      getRun: () => detail,
      onCancel: () => {
        cancelRequests += 1
        detail = runDetail({
          status: 'cancelled',
          current_phase: 'review',
          phase_status: 'cancelled',
          finished_at: now,
          latest_error: null,
          review_summary: null,
          review_issues: [],
        })
        return detail
      },
      chatEvents: [
        { type: 'run_waiting_input', run_id: runId, phase: 'review', status: 'waiting_input', waiting_reason: 'Review needs user feedback', timestamp: now },
        '[DONE]',
      ],
    })

    await page.goto(`/project/${sessionId}`)
    await page.getByTestId('chat-textarea').fill('Continue the waiting run')
    await page.getByRole('button', { name: 'Send message' }).click()

    await expect(page.getByTestId('run-status-strip')).toContainText('Waiting for input')
    await page.getByTestId('run-inspector-toggle').click()
    await expect(page.getByTestId('run-inspector')).toContainText('waiting input')

    await page.getByTestId('run-inspector-cancel').click()

    await expect
      .poll(() => cancelRequests)
      .toBe(1)
    await expect(page.getByTestId('run-inspector')).toContainText('cancelled')
  })

  test('refreshes waiting run details in the inspector', async ({ page }) => {
    let detail = runDetail({
      status: 'waiting_input',
      current_phase: 'implement',
      phase_status: 'waiting_input',
      waiting_reason: 'Choose a visual direction',
      latest_error: null,
      finished_at: null,
      review_summary: null,
      review_issues: [],
      phase_history: [{ phase: 'implement', status: 'waiting_input', waiting_reason: 'Choose a visual direction' }],
    })
    await setupProjectMocks(page, {
      getRun: () => detail,
      chatEvents: [
        { type: 'run_waiting_input', run_id: runId, phase: 'implement', status: 'waiting_input', waiting_reason: 'Choose a visual direction', timestamp: now },
        '[DONE]',
      ],
    })

    await page.goto(`/project/${sessionId}`)
    await page.getByTestId('chat-textarea').fill('Continue the waiting run')
    await page.getByRole('button', { name: 'Send message' }).click()

    await expect(page.getByTestId('run-status-strip')).toContainText('Waiting for input')
    await page.getByTestId('run-inspector-toggle').click()
    await expect(page.getByTestId('run-inspector')).toContainText('waiting input')

    detail = runDetail({
      status: 'completed',
      latest_error: null,
      current_phase: 'done',
      phase_status: 'completed',
      review_summary: { error_count: 0, warning_count: 0, build_status: 'success' },
      review_issues: [],
      phase_history: [
        { phase: 'implement', status: 'waiting_input', waiting_reason: 'Choose a visual direction' },
        { phase: 'implement', status: 'completed' },
        { phase: 'build', status: 'completed' },
        { phase: 'review', status: 'completed' },
      ],
    })
    await page.getByTestId('run-inspector-refresh').click()

    await expect(page.getByTestId('run-inspector')).toContainText('completed')
    await expect(page.getByTestId('run-inspector')).toContainText('Done')
    await expect(page.getByTestId('run-inspector')).toContainText('0 errors')
  })
})
