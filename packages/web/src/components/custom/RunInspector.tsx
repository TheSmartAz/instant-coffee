import * as React from 'react'
import {
  ChevronDown,
  ChevronUp,
  Check,
  CircleAlert,
  ExternalLink,
  FileCode2,
  GitBranch,
  RefreshCw,
  Square,
  Wrench,
  X,
} from 'lucide-react'
import { api } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { ChatRunStatus, RunEventResponse, RunReviewIssue, SessionRunDetail } from '@/types'

interface RunInspectorProps {
  sessionId?: string
  runStatus?: ChatRunStatus | null
  onOpenBuildPreview?: () => void
}

const PHASE_LABELS: Record<string, string> = {
  plan: 'Plan',
  implement: 'Implement',
  build: 'Build',
  review: 'Review',
  fix: 'Fix',
  verify: 'Verify',
  done: 'Done',
}

const EXECUTION_MODE_LABELS = {
  plan: 'Plan only',
  agent: 'Agent',
  auto: 'Auto',
} as const

const formatPhase = (phase?: string | null) => {
  if (!phase) return undefined
  return PHASE_LABELS[phase] ?? phase.replace(/_/g, ' ')
}

const formatStatus = (status?: string | null) => {
  if (!status) return undefined
  return status.replace(/_/g, ' ')
}

const formatDate = (value?: string | null) => {
  if (!value) return undefined
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return undefined
  return date.toLocaleString()
}

const runActionErrorMessage = (error: unknown, fallback: string) => {
  if (error instanceof Error && 'status' in error) {
    const status = Number((error as Error & { status?: number }).status)
    if (status === 401 || status === 403) return `${fallback}: admin token required`
    if (status === 409) return error.message || `${fallback}: run is not ready`
  }
  return error instanceof Error ? error.message : fallback
}

const REVIEW_SEVERITY_CLASS: Record<string, string> = {
  error: 'border-destructive/20 bg-destructive/10 text-destructive',
  warning: 'border-warning/30 bg-warning-muted text-warning-muted-foreground',
}

const reviewSummaryText = (summary?: Record<string, unknown> | null) => {
  if (!summary) return undefined
  const parts: string[] = []
  if (typeof summary.error_count === 'number') parts.push(`${summary.error_count} errors`)
  if (typeof summary.warning_count === 'number') parts.push(`${summary.warning_count} warnings`)
  if (typeof summary.build_status === 'string' && summary.build_status) {
    parts.push(`build ${summary.build_status}`)
  }
  if (Array.isArray(summary.generated_pages)) {
    parts.push(`${summary.generated_pages.length} pages`)
  }
  return parts.length ? parts.join(', ') : undefined
}

const verificationTone = (status?: string | null) => {
  const normalized = (status ?? '').toLowerCase()
  if (normalized === 'passed') return 'success'
  if (normalized === 'failed' || normalized === 'cancelled') return 'failed'
  if (normalized === 'in_progress') return 'running'
  return 'waiting'
}

const statusTone = (status?: string | null) => {
  const normalized = (status ?? '').toLowerCase()
  if (normalized === 'completed' || normalized === 'success') return 'success'
  if (normalized === 'failed' || normalized === 'cancelled') return 'failed'
  if (normalized === 'waiting_input') return 'waiting'
  return 'running'
}

function phaseHistoryLabel(entry: Record<string, unknown>) {
  const phase = formatPhase(typeof entry.phase === 'string' ? entry.phase : undefined)
  const status = formatStatus(typeof entry.status === 'string' ? entry.status : undefined)
  const waitingReason =
    typeof entry.waiting_reason === 'string' && entry.waiting_reason
      ? entry.waiting_reason
      : undefined
  const error =
    typeof entry.error === 'string' && entry.error
      ? entry.error
      : undefined
  return {
    label: phase ? `${phase}${status ? ` · ${status}` : ''}` : status ?? 'Phase',
    detail: waitingReason ?? error ?? undefined,
  }
}

function issueLabel(issue: RunReviewIssue) {
  const severity = (issue.severity ?? '').toLowerCase()
  return REVIEW_SEVERITY_CLASS[severity] ?? 'border-border bg-muted/40 text-foreground'
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value && typeof value === 'object' && !Array.isArray(value))

const getBuildArtifact = (artifacts?: Record<string, unknown>) => {
  if (!artifacts) return null
  if (isRecord(artifacts.build)) return artifacts.build
  if (isRecord(artifacts.fix) && isRecord(artifacts.fix.build)) return artifacts.fix.build
  if ('dist_path' in artifacts || 'pages' in artifacts || 'status' in artifacts) return artifacts
  return null
}

const stringList = (value: unknown) =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []

const numberValue = (value: unknown) => (typeof value === 'number' && Number.isFinite(value) ? value : undefined)

const stringValue = (value: unknown) => (typeof value === 'string' && value ? value : undefined)

const failureText = (failure: Record<string, unknown>, key: string) => {
  const value = failure[key]
  return typeof value === 'string' && value ? value : undefined
}

const failureLabel = (value?: string) => (value ? value.replace(/_/g, ' ') : undefined)

const verificationFailureGroups = (failures: Array<Record<string, unknown>>) => {
  const groups = new Map<string, { route?: string; kind?: string; count: number; hint?: string; message?: string }>()
  for (const failure of failures) {
    const route = failureText(failure, 'route') ?? failureText(failure, 'source') ?? 'command'
    const kind = failureText(failure, 'kind')
    const key = `${route}:${kind ?? ''}`
    const existing = groups.get(key)
    if (existing) {
      existing.count += 1
      existing.hint ??= failureText(failure, 'fix_hint')
      existing.message ??= failureText(failure, 'message')
      continue
    }
    groups.set(key, {
      route,
      kind,
      count: 1,
      hint: failureText(failure, 'fix_hint'),
      message: failureText(failure, 'message'),
    })
  }
  return Array.from(groups.values())
}

const MEMORY_LABELS: Record<string, string> = {
  architecture_notes: 'Architecture',
  interface_contracts: 'Contracts',
  testing_notes: 'Testing',
  style_preferences: 'Style',
  component_inventory: 'Components',
  design_decisions: 'Design',
  user_preferences: 'User',
}

const timelineDotClass = (status?: string) => {
  const tone = statusTone(status)
  if (tone === 'success') return 'bg-success'
  if (tone === 'failed') return 'bg-destructive'
  if (tone === 'waiting') return 'bg-warning'
  return 'bg-info'
}

const getExecutionMode = (run?: SessionRunDetail | null, status?: ChatRunStatus | null) => {
  const value = run?.execution_mode ?? run?.executionMode ?? run?.approval_mode ?? status?.executionMode
  return value ? EXECUTION_MODE_LABELS[value] : undefined
}

interface PendingShellApproval {
  approvalId: string
  runId: string
  command: string
  reason: string
  executionMode?: string
}

const eventPayload = (event: RunEventResponse) => event.payload ?? {}

const stringPayload = (event: RunEventResponse, key: string) => {
  const payload = eventPayload(event)
  const value = payload[key]
  return typeof value === 'string' && value ? value : undefined
}

const getPendingApproval = (
  events: RunEventResponse[],
  runStatus?: ChatRunStatus | null,
): PendingShellApproval | null => {
  const resolved = new Set(
    events
      .filter((event) => event.type === 'shell_approval_resolved')
      .map((event) => stringPayload(event, 'approval_id'))
      .filter((value): value is string => Boolean(value)),
  )
  for (const event of [...events].reverse()) {
    if (event.type !== 'shell_approval') continue
    const approvalId = stringPayload(event, 'approval_id')
    const runId = event.run_id ?? stringPayload(event, 'run_id')
    if (!approvalId || !runId || resolved.has(approvalId)) continue
    return {
      approvalId,
      runId,
      command: stringPayload(event, 'command') ?? '',
      reason: stringPayload(event, 'reason') ?? 'Approval required',
      executionMode: stringPayload(event, 'execution_mode'),
    }
  }
  if (runStatus?.eventType === 'shell_approval' && runStatus.approvalId && runStatus.runId) {
    return {
      approvalId: runStatus.approvalId,
      runId: runStatus.runId,
      command: runStatus.command ?? '',
      reason: runStatus.reason ?? runStatus.message ?? 'Approval required',
      executionMode: runStatus.executionMode,
    }
  }
  return null
}

export function RunInspector({ sessionId, runStatus, onOpenBuildPreview }: RunInspectorProps) {
  const [expanded, setExpanded] = React.useState(false)
  const [run, setRun] = React.useState<SessionRunDetail | null>(null)
  const [runEvents, setRunEvents] = React.useState<RunEventResponse[]>([])
  const [loading, setLoading] = React.useState(false)
  const [approvalBusy, setApprovalBusy] = React.useState<string | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const previousSessionIdRef = React.useRef<string | undefined>(undefined)

  const statusRunId = runStatus?.runId

  React.useEffect(() => {
    if (previousSessionIdRef.current === undefined) {
      previousSessionIdRef.current = sessionId
      return
    }
    if (previousSessionIdRef.current === sessionId) return
    previousSessionIdRef.current = sessionId
    setRun(null)
    setRunEvents([])
    setError(null)
    setLoading(false)
    setExpanded(false)
  }, [sessionId])

  const refreshRunEvents = React.useCallback(async (runId: string) => {
    try {
      const data = await api.runs.events(runId, { limit: 200 })
      setRunEvents(data.events ?? [])
    } catch {
      setRunEvents([])
    }
  }, [])

  React.useEffect(() => {
    if (!sessionId) return
    let cancelled = false
    const fetchRun = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = statusRunId
          ? await api.runs.get(statusRunId)
          : (await api.runs.list(sessionId, { limit: 1 })).runs[0] ?? null
        if (!cancelled) {
          setRun(data ?? null)
          if (data?.run_id) void refreshRunEvents(data.run_id)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load run state')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void fetchRun()
    return () => {
      cancelled = true
    }
  }, [sessionId, statusRunId, refreshRunEvents])

  const effectiveRun = run ?? null
  const actionableRunId = statusRunId ?? effectiveRun?.run_id

  React.useEffect(() => {
    if (!actionableRunId) return
    const tone = statusTone(run?.status ?? runStatus?.status)
    if (tone === 'running' || tone === 'waiting') {
      const timer = window.setInterval(() => {
        void api.runs.get(actionableRunId).then((data) => {
          setRun(data)
          void refreshRunEvents(actionableRunId)
        }).catch(() => {})
      }, 5000)
      return () => window.clearInterval(timer)
    }
    return undefined
  }, [actionableRunId, run?.status, runStatus?.status, refreshRunEvents])

  const handleRefresh = React.useCallback(() => {
    if (!sessionId) return
    setLoading(true)
    setError(null)
    const fetchRun = async () => {
      try {
        const data = statusRunId
          ? await api.runs.get(statusRunId)
          : (await api.runs.list(sessionId, { limit: 1 })).runs[0] ?? null
        setRun(data ?? null)
        if (data?.run_id) void refreshRunEvents(data.run_id)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load run state')
      } finally {
        setLoading(false)
      }
    }
    void fetchRun()
  }, [statusRunId, sessionId, refreshRunEvents])

  const handleCancel = React.useCallback(async () => {
    if (!actionableRunId) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.runs.cancel(actionableRunId)
      setRun(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel run')
    } finally {
      setLoading(false)
    }
  }, [actionableRunId])

  const handleVerify = React.useCallback(async () => {
    if (!actionableRunId) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.runs.verify(actionableRunId)
      setRun(data)
    } catch (err) {
      setError(runActionErrorMessage(err, 'Failed to run verification'))
    } finally {
      setLoading(false)
    }
  }, [actionableRunId])

  const handleFixVerification = React.useCallback(async () => {
    if (!actionableRunId) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.runs.fixVerification(actionableRunId)
      setRun(data)
      setExpanded(true)
    } catch (err) {
      setError(runActionErrorMessage(err, 'Failed to fix verification'))
    } finally {
      setLoading(false)
    }
  }, [actionableRunId])

  const handleResolveFixGate = React.useCallback(async (attempt: number, approved: boolean) => {
    if (!actionableRunId) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.runs.resolveFixGate(actionableRunId, attempt, approved)
      setRun(data)
      setExpanded(true)
    } catch (err) {
      setError(runActionErrorMessage(err, 'Failed to resolve fix gate'))
    } finally {
      setLoading(false)
    }
  }, [actionableRunId])

  const handleReviewFixGate = React.useCallback(async (attempt: number) => {
    if (!actionableRunId) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.runs.reviewFixGate(actionableRunId, attempt)
      setRun(data)
      setExpanded(true)
    } catch (err) {
      setError(runActionErrorMessage(err, 'Failed to review fix gate'))
    } finally {
      setLoading(false)
    }
  }, [actionableRunId])

  const handleResolveApproval = React.useCallback(async (approval: PendingShellApproval, approved: boolean) => {
    setApprovalBusy(approval.approvalId)
    setError(null)
    try {
      const data = await api.runs.resolveApproval(approval.runId, approval.approvalId, approved)
      setRun(data)
      await refreshRunEvents(approval.runId)
    } catch (err) {
      setError(runActionErrorMessage(err, approved ? 'Failed to approve command' : 'Failed to reject command'))
    } finally {
      setApprovalBusy(null)
    }
  }, [refreshRunEvents])

  const phaseHistory = effectiveRun?.phase_history ?? []
  const reviewIssues = effectiveRun?.review_issues ?? []
  const reviewSummary = reviewSummaryText(effectiveRun?.review_summary ?? null)
  const phaseLabel = formatPhase(effectiveRun?.current_phase ?? runStatus?.phase)
  const statusLabel = formatStatus(effectiveRun?.phase_status ?? effectiveRun?.status ?? runStatus?.status)
  const executionModeLabel = getExecutionMode(effectiveRun, runStatus)
  const tone = statusTone(effectiveRun?.status ?? runStatus?.status)
  const buildArtifact = getBuildArtifact(effectiveRun?.artifacts)
  const buildPages = stringList(buildArtifact?.pages ?? effectiveRun?.review_summary?.generated_pages)
  const distPath = typeof buildArtifact?.dist_path === 'string' ? buildArtifact.dist_path : undefined
  const buildStatus = typeof buildArtifact?.status === 'string' ? buildArtifact.status : undefined
  const verification = effectiveRun?.verification
  const verificationStatus = verification?.status
  const visualCheck = verification?.checks.find((check) => check.name === 'visual')
  const visualScore = numberValue(visualCheck?.details?.quality_score)
  const visualScreenshot = stringValue(visualCheck?.details?.screenshot_path)
  const verificationBadgeTone = verificationTone(verificationStatus)
  const recommendedCommands =
    verification?.profile?.recommended_commands?.filter((item) => typeof item.command === 'string') ?? []
  const riskFlags = verification?.profile?.risk_flags ?? []
  const lastVerificationRun = verification?.last_run
  const verificationFixAttempts = verification?.fix_attempts ?? []
  const verificationAuditTrail = verification?.audit_trail ?? []
  const actionAuditTrail = verification?.action_audit_trail ?? []
  const contextMemory = effectiveRun?.context?.memory ?? {}
  const contextEntries = Object.entries(contextMemory).filter(([, value]) => value.trim())
  const pendingApproval = getPendingApproval(runEvents, runStatus)

  if (!sessionId) return null
  if (!run && !runStatus && !error && !loading) return null

  return (
    <div className="border-t border-border bg-background px-4 py-3 text-xs" data-testid="run-inspector">
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs"
          onClick={() => setExpanded((value) => !value)}
          data-testid="run-inspector-toggle"
        >
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          Run
        </Button>
        {phaseLabel ? <Badge variant="secondary">{phaseLabel}</Badge> : null}
        {statusLabel ? <Badge variant={tone === 'failed' ? 'destructive' : 'outline'}>{statusLabel}</Badge> : null}
        {executionModeLabel ? <Badge variant="outline">{executionModeLabel}</Badge> : null}
        {effectiveRun?.run_id ? (
          <span className="font-mono text-[11px] text-muted-foreground">
            {effectiveRun.run_id.slice(0, 10)}
          </span>
        ) : null}
        <div className="ml-auto flex items-center gap-1">
          {!expanded && verification?.last_run?.status === 'failed' ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 gap-1 px-2 text-xs"
              onClick={handleFixVerification}
              disabled={!actionableRunId || loading}
              data-testid="run-inspector-fix-verification"
            >
              <Wrench className="h-3.5 w-3.5" />
              Fix
            </Button>
          ) : null}
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={handleRefresh}
            disabled={loading}
            data-testid="run-inspector-refresh"
          >
            <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={handleCancel}
            disabled={!actionableRunId || loading || (tone !== 'running' && tone !== 'waiting')}
            title="Cancel run"
            data-testid="run-inspector-cancel"
          >
            <Square className="h-4 w-4" />
          </Button>
        </div>
      </div>
      {error ? (
        <div className="mt-2 flex items-start gap-2 rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-destructive">
          <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
          <span className="min-w-0 break-words">{error}</span>
        </div>
      ) : null}
      {pendingApproval ? (
        <div className="mt-2 rounded-md border border-warning/40 bg-warning-muted px-3 py-2 text-warning-muted-foreground" data-testid="shell-approval-card">
          <div className="flex items-start gap-2">
            <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium">Shell approval required</div>
              <div className="mt-0.5 text-[11px] text-warning-muted-foreground/80">
                {pendingApproval.reason}
                {pendingApproval.executionMode ? ` · ${pendingApproval.executionMode}` : ''}
              </div>
              {pendingApproval.command ? (
                <div className="mt-2 max-h-24 overflow-auto rounded-sm bg-background/80 px-2 py-1 font-mono text-[11px] text-foreground">
                  <span className="break-all">{pendingApproval.command}</span>
                </div>
              ) : null}
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 gap-1 px-2 text-xs"
                onClick={() => void handleResolveApproval(pendingApproval, false)}
                disabled={approvalBusy === pendingApproval.approvalId}
                data-testid="shell-approval-reject"
              >
                <X className="h-3.5 w-3.5" />
                Reject
              </Button>
              <Button
                type="button"
                size="sm"
                className="h-7 gap-1 px-2 text-xs"
                onClick={() => void handleResolveApproval(pendingApproval, true)}
                disabled={approvalBusy === pendingApproval.approvalId}
                data-testid="shell-approval-approve"
              >
                <Check className="h-3.5 w-3.5" />
                Approve
              </Button>
            </div>
          </div>
        </div>
      ) : null}
      {expanded ? (
        <div className="mt-3 max-h-[min(60vh,32rem)] space-y-3 overflow-y-auto pr-1">
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="rounded-md border border-border bg-muted/20 px-3 py-2">
              <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Current</div>
              <div className="mt-1 text-sm font-medium">{phaseLabel ?? 'Unknown'}</div>
              <div className="text-[11px] text-muted-foreground">{statusLabel ?? 'Unknown'}</div>
            </div>
            {executionModeLabel ? (
              <div className="rounded-md border border-border bg-muted/20 px-3 py-2">
                <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Execution mode</div>
                <div className="mt-1 text-sm font-medium">{executionModeLabel}</div>
                <div className="text-[11px] text-muted-foreground">Run workflow</div>
              </div>
            ) : null}
            <div className="rounded-md border border-border bg-muted/20 px-3 py-2">
              <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Updated</div>
              <div className="mt-1 text-sm font-medium">{formatDate(effectiveRun?.updated_at) ?? '-'}</div>
              <div className="text-[11px] text-muted-foreground">{formatDate(effectiveRun?.heartbeat_at) ?? 'No heartbeat'}</div>
            </div>
          </div>
          {reviewSummary ? (
            <div className="rounded-md border border-border bg-muted/20 px-3 py-2">
              <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Review</div>
              <div className="mt-1 text-sm">{reviewSummary}</div>
            </div>
          ) : null}
          {verification ? (
            <div className="rounded-md border border-border bg-muted/20 px-3 py-2" data-testid="run-inspector-verification">
              <div className="flex items-center gap-2">
                <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Verification</div>
                <Badge
                  variant={verificationBadgeTone === 'failed' ? 'destructive' : 'outline'}
                  className="ml-auto text-[10px]"
                >
                  {verificationStatus?.replace(/_/g, ' ') ?? 'unknown'}
                </Badge>
              </div>
              {verification.checks.length ? (
                <div className="mt-2 grid gap-1">
                  {verification.checks.slice(0, 4).map((check) => (
                    <div key={check.name} className="flex min-w-0 items-center justify-between gap-2 text-[11px]">
                      <span className="truncate font-medium">{formatPhase(check.name) ?? check.name}</span>
                      <span className="truncate text-muted-foreground">
                        {check.status}
                        {typeof check.passed === 'boolean' ? ` · ${check.passed ? 'passed' : 'failed'}` : ''}
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}
              {verification.evidence.length ? (
                <div className="mt-2 space-y-1 text-[11px] text-muted-foreground">
                  {verification.evidence.slice(0, 3).map((item, index) => (
                    <div key={index} className="break-words">{item}</div>
                  ))}
                </div>
              ) : null}
              {visualCheck ? (
                <div className="mt-2 rounded-sm bg-background/70 px-2 py-1 text-[11px]">
                  <div className="flex min-w-0 items-center justify-between gap-2">
                    <span className="font-medium">Visual check</span>
                    <span className={cn('shrink-0', visualCheck.passed ? 'text-success' : visualCheck.passed === false ? 'text-destructive' : 'text-muted-foreground')}>
                      {visualScore !== undefined ? `${visualScore}/100` : visualCheck.status}
                    </span>
                  </div>
                  {visualScreenshot ? (
                    <div className="mt-1 break-all font-mono text-[10px] text-muted-foreground">
                      {visualScreenshot}
                    </div>
                  ) : null}
                </div>
              ) : null}
              {riskFlags.length ? (
                <div className="mt-2 flex flex-wrap gap-1">
                  {riskFlags.slice(0, 4).map((flag) => (
                    <Badge key={flag} variant="outline" className="text-[10px]">
                      {flag.replace(/_/g, ' ')}
                    </Badge>
                  ))}
                </div>
              ) : null}
              {recommendedCommands.length ? (
                <div className="mt-2 space-y-1">
                  {recommendedCommands.slice(0, 3).map((item, index) => (
                    <div key={index} className="min-w-0 rounded-sm bg-background/70 px-2 py-1 font-mono text-[10px] text-muted-foreground">
                      <span className="break-all">{String(item.command)}</span>
                    </div>
                  ))}
                </div>
              ) : null}
              {lastVerificationRun ? (
                <div className="mt-2 space-y-1">
                  <div className="text-[11px] font-medium">
                    Last run · {lastVerificationRun.status}
                  </div>
                  {lastVerificationRun.commands.slice(0, 4).map((item) => (
                    <div key={`${item.scope}-${item.command}`} className="rounded-sm bg-background/70 px-2 py-1 text-[11px]">
                      <div className="flex min-w-0 items-center justify-between gap-2">
                        <span className="truncate font-medium">{item.name}</span>
                        <span className={cn('shrink-0', item.status === 'passed' ? 'text-success' : 'text-destructive')}>
                          {item.status}
                        </span>
                      </div>
                      {item.failures.length ? (
                        <div className="mt-1 space-y-1">
                          <div className="flex flex-wrap gap-1" data-testid="verification-failure-routes">
                            {verificationFailureGroups(item.failures).slice(0, 4).map((group, index) => (
                              <Badge key={`${group.route ?? 'route'}-${group.kind ?? index}`} variant="outline" className="text-[10px]">
                                {[failureLabel(group.route), failureLabel(group.kind)].filter(Boolean).join(' · ')}
                                {group.count > 1 ? ` (${group.count})` : ''}
                              </Badge>
                            ))}
                          </div>
                          {verificationFailureGroups(item.failures)[0]?.hint ? (
                            <div className="line-clamp-2 break-words text-muted-foreground">
                              {verificationFailureGroups(item.failures)[0].hint}
                            </div>
                          ) : (
                            <div className="line-clamp-2 break-words text-muted-foreground">
                              {verificationFailureGroups(item.failures)[0]?.message ?? String(item.output_summary)}
                            </div>
                          )}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}
              {verificationFixAttempts.length ? (
                <div className="mt-2 space-y-1">
                  <div className="text-[11px] font-medium">Fix attempts</div>
                  {verificationFixAttempts.slice(-2).map((attempt) => (
                    <div key={attempt.attempt} className="rounded-sm bg-background/70 px-2 py-1 text-[11px]">
                      <div className="flex min-w-0 items-center justify-between gap-2">
                        <span className="font-medium">Attempt {attempt.attempt}</span>
                        <span className={cn('shrink-0', attempt.status === 'passed' ? 'text-success' : 'text-destructive')}>
                          {attempt.status}
                        </span>
                      </div>
                      {attempt.change_summary ? (
                        <div className="mt-1 space-y-1">
                          <div className="text-[11px] text-muted-foreground">
                            {attempt.change_summary.file_count} file(s) changed · {attempt.change_summary.risk_level} risk
                            {attempt.change_summary.verification_status
                              ? ` · verification ${attempt.change_summary.verification_status}`
                              : ''}
                          </div>
                          {attempt.change_summary.changed_files.length ? (
                            <div className="flex flex-wrap gap-1">
                              {attempt.change_summary.changed_files.slice(0, 3).map((file) => (
                                <Badge key={file} variant="outline" className="max-w-full text-[10px]">
                                  <span className="truncate">{file}</span>
                                </Badge>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                      {attempt.gate ? (
                        <div className="mt-1 space-y-1">
                          <div className="flex min-w-0 items-center justify-between gap-2 text-[11px] text-muted-foreground">
                            <span className="truncate">
                              Gate · {attempt.gate.status.replace(/_/g, ' ')}
                              {attempt.gate.decision ? ` · ${attempt.gate.decision.replace(/_/g, ' ')}` : ''}
                            </span>
                          </div>
                          {attempt.gate.reasons?.length ? (
                            <div className="flex flex-wrap gap-1">
                              {attempt.gate.reasons.slice(0, 3).map((reason) => (
                                <Badge key={reason} variant="outline" className="text-[10px]">
                                  {reason.replace(/_/g, ' ')}
                                </Badge>
                              ))}
                            </div>
                          ) : null}
                          {attempt.gate.reviewer ? (
                            <div className="rounded-sm border border-border/70 px-2 py-1 text-[11px] text-muted-foreground">
                              <div className="font-medium text-foreground">
                                Reviewer · {attempt.gate.reviewer.recommendation?.replace(/_/g, ' ') ?? 'review required'}
                              </div>
                              {attempt.gate.reviewer.summary ? (
                                <div className="mt-0.5 line-clamp-2 break-words">{attempt.gate.reviewer.summary}</div>
                              ) : null}
                            </div>
                          ) : null}
                          {attempt.gate.status === 'blocked' ? (
                            <div className="flex gap-1">
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                className="h-6 px-2 text-[11px]"
                                onClick={() => void handleReviewFixGate(attempt.attempt)}
                                disabled={!actionableRunId || loading}
                                data-testid="run-inspector-review-fix-gate"
                              >
                                Review
                              </Button>
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                className="h-6 px-2 text-[11px]"
                                onClick={() => void handleResolveFixGate(attempt.attempt, true)}
                                disabled={!actionableRunId || loading}
                                data-testid="run-inspector-approve-fix-gate"
                              >
                                Approve
                              </Button>
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                className="h-6 px-2 text-[11px]"
                                onClick={() => void handleResolveFixGate(attempt.attempt, false)}
                                disabled={!actionableRunId || loading}
                                data-testid="run-inspector-reject-fix-gate"
                              >
                                Reject
                              </Button>
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                      {attempt.error ? (
                        <div className="mt-1 line-clamp-2 break-words text-muted-foreground">{attempt.error}</div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}
              {verificationAuditTrail.length ? (
                <div className="mt-2 space-y-1">
                  <div className="text-[11px] font-medium">Audit trail</div>
                  {verificationAuditTrail.slice(-3).map((event, index) => (
                    <div key={`${event.type}-${event.at ?? index}`} className="rounded-sm bg-background/70 px-2 py-1 text-[11px]">
                      <div className="flex min-w-0 items-center justify-between gap-2">
                        <span className="truncate font-medium">{event.type.replace(/_/g, ' ')}</span>
                        <span className={cn('shrink-0', event.status === 'passed' ? 'text-success' : event.status.includes('error') || event.status === 'failed' ? 'text-destructive' : 'text-muted-foreground')}>
                          {event.status}
                        </span>
                      </div>
                      {event.message ? (
                        <div className="mt-1 line-clamp-2 break-words text-muted-foreground">{event.message}</div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}
              {actionAuditTrail.length ? (
                <div className="mt-2 space-y-1">
                  <div className="text-[11px] font-medium">Action trail</div>
                  {actionAuditTrail.slice(-4).map((event, index) => (
                    <div key={`${event.type}-${event.at ?? index}`} className="rounded-sm bg-background/70 px-2 py-1 text-[11px]">
                      <div className="flex min-w-0 items-center justify-between gap-2">
                        <span className="truncate font-medium">
                          {event.category.replace(/_/g, ' ')} · {event.type.replace(/_/g, ' ')}
                        </span>
                        <span className={cn('shrink-0', event.status === 'passed' ? 'text-success' : event.status.includes('error') || event.status === 'failed' ? 'text-destructive' : 'text-muted-foreground')}>
                          {event.status}
                        </span>
                      </div>
                      {event.summary ? (
                        <div className="mt-1 line-clamp-2 break-words text-muted-foreground">{event.summary}</div>
                      ) : null}
                      {event.command ? (
                        <div className="mt-1 break-all font-mono text-[10px] text-muted-foreground">
                          {event.scope ? `[${event.scope}] ` : ''}{event.command}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-2 h-7 gap-1 px-2 text-xs"
                onClick={handleVerify}
                disabled={!actionableRunId || loading || !recommendedCommands.length}
                data-testid="run-inspector-run-verification"
              >
                <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
                Run verification
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="ml-2 mt-2 h-7 gap-1 px-2 text-xs"
                onClick={handleFixVerification}
                disabled={!actionableRunId || loading || lastVerificationRun?.status !== 'failed'}
                data-testid="run-inspector-fix-verification"
              >
                <Wrench className="h-3.5 w-3.5" />
                Fix verification
              </Button>
            </div>
          ) : null}
          {contextEntries.length ? (
            <div className="rounded-md border border-border bg-muted/20 px-3 py-2" data-testid="run-inspector-context">
              <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Agent Context</div>
              <div className="mt-2 space-y-2">
                {contextEntries.slice(0, 4).map(([key, value]) => (
                  <div key={key} className="min-w-0">
                    <div className="text-[11px] font-medium">{MEMORY_LABELS[key] ?? key.replace(/_/g, ' ')}</div>
                    <div className="mt-0.5 line-clamp-2 break-words text-[11px] text-muted-foreground">{value}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          <div className="rounded-md border border-border bg-muted/20 px-3 py-2" data-testid="run-inspector-artifacts">
            <div className="flex items-center gap-2">
              <FileCode2 className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
              <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Artifacts</div>
              {buildStatus ? <Badge variant="outline" className="ml-auto text-[10px]">{buildStatus}</Badge> : null}
            </div>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              <div>
                <div className="text-[11px] text-muted-foreground">Build pages</div>
                <div className="mt-0.5 truncate text-sm font-medium">
                  {buildPages.length ? `${buildPages.length} generated` : 'No build pages'}
                </div>
              </div>
              <div>
                <div className="text-[11px] text-muted-foreground">Fix attempts</div>
                <div className="mt-0.5 flex items-center gap-1 text-sm font-medium">
                  <Wrench className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
                  {effectiveRun?.fix_attempts ?? 0}
                </div>
              </div>
            </div>
            {distPath ? (
              <div className="mt-2 min-w-0 rounded-sm bg-background/70 px-2 py-1 font-mono text-[11px] text-muted-foreground">
                <span className="break-all">{distPath}</span>
              </div>
            ) : null}
            {effectiveRun?.checkpoint_thread ? (
              <div className="mt-2 flex min-w-0 items-center gap-1 text-[11px] text-muted-foreground">
                <GitBranch className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                <span className="truncate">{effectiveRun.checkpoint_thread}</span>
              </div>
            ) : null}
            {onOpenBuildPreview ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-2 h-7 gap-1 px-2 text-xs"
                onClick={onOpenBuildPreview}
                disabled={!buildPages.length && !distPath}
                data-testid="run-inspector-open-build"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                Build preview
              </Button>
            ) : null}
          </div>
          {reviewIssues.length > 0 ? (
            <div className="space-y-2">
              <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Issues</div>
              <div className="space-y-2">
                {reviewIssues.slice(0, 5).map((issue, index) => (
                  <div key={`${issue.code ?? 'issue'}-${index}`} className={cn('rounded-md border px-3 py-2', issueLabel(issue))}>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{issue.code ?? 'issue'}</span>
                      {issue.severity ? <Badge variant="outline" className="text-[10px] uppercase">{issue.severity}</Badge> : null}
                    </div>
                    <div className="mt-1 break-words text-current/90">{issue.message ?? ''}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          {phaseHistory.length > 0 ? (
            <div className="space-y-2">
              <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Timeline</div>
              <div className="space-y-1">
                {phaseHistory.slice(-6).map((entry, index) => {
                  const payload = entry && typeof entry === 'object' ? entry : {}
                  const { label, detail } = phaseHistoryLabel(payload)
                  return (
                    <div key={index} className="flex gap-2 rounded-md border border-border px-3 py-2">
                      <span
                        className={cn(
                          'mt-1 h-2 w-2 shrink-0 rounded-full',
                          timelineDotClass(typeof payload.status === 'string' ? payload.status : undefined),
                        )}
                      />
                      <div className="min-w-0">
                        <div className="font-medium">{label}</div>
                        {detail ? <div className="mt-1 break-words text-muted-foreground">{detail}</div> : null}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ) : null}
          {effectiveRun?.latest_error ? (
            <div className="rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-destructive">
              <div className="text-[11px] uppercase tracking-wide">Latest error</div>
              <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words text-xs">
                {JSON.stringify(effectiveRun.latest_error, null, 2)}
              </pre>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
