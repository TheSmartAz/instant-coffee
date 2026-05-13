import * as React from 'react'
import {
  ChevronDown,
  ChevronUp,
  CircleAlert,
  ExternalLink,
  FileCode2,
  GitBranch,
  RefreshCw,
  Square,
  Wrench,
} from 'lucide-react'
import { api } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { ChatRunStatus, RunReviewIssue, SessionRunDetail } from '@/types'

interface RunInspectorProps {
  sessionId?: string
  threadId?: string
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

const REVIEW_SEVERITY_CLASS: Record<string, string> = {
  error: 'border-destructive/20 bg-destructive/10 text-destructive',
  warning: 'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-100',
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

const timelineDotClass = (status?: string) => {
  const tone = statusTone(status)
  if (tone === 'success') return 'bg-emerald-500'
  if (tone === 'failed') return 'bg-destructive'
  if (tone === 'waiting') return 'bg-amber-500'
  return 'bg-blue-500'
}

export function RunInspector({ sessionId, threadId, runStatus, onOpenBuildPreview }: RunInspectorProps) {
  const [expanded, setExpanded] = React.useState(false)
  const [run, setRun] = React.useState<SessionRunDetail | null>(null)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const statusRunId = runStatus?.runId

  React.useEffect(() => {
    setRun(null)
    setError(null)
    setLoading(false)
    setExpanded(false)
  }, [sessionId, threadId])

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
        if (!cancelled) setRun(data ?? null)
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
  }, [sessionId, statusRunId])

  const effectiveRun = run ?? null
  const actionableRunId = statusRunId ?? effectiveRun?.run_id

  React.useEffect(() => {
    if (!actionableRunId) return
    const tone = statusTone(run?.status ?? runStatus?.status)
    if (tone === 'running' || tone === 'waiting') {
      const timer = window.setInterval(() => {
        void api.runs.get(actionableRunId).then(setRun).catch(() => {})
      }, 5000)
      return () => window.clearInterval(timer)
    }
    return undefined
  }, [actionableRunId, run?.status, runStatus?.status])

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
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load run state')
      } finally {
        setLoading(false)
      }
    }
    void fetchRun()
  }, [statusRunId, sessionId])

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

  const phaseHistory = effectiveRun?.phase_history ?? []
  const reviewIssues = effectiveRun?.review_issues ?? []
  const reviewSummary = reviewSummaryText(effectiveRun?.review_summary ?? null)
  const phaseLabel = formatPhase(effectiveRun?.current_phase ?? runStatus?.phase)
  const statusLabel = formatStatus(effectiveRun?.phase_status ?? effectiveRun?.status ?? runStatus?.status)
  const tone = statusTone(effectiveRun?.status ?? runStatus?.status)
  const buildArtifact = getBuildArtifact(effectiveRun?.artifacts)
  const buildPages = stringList(buildArtifact?.pages ?? effectiveRun?.review_summary?.generated_pages)
  const distPath = typeof buildArtifact?.dist_path === 'string' ? buildArtifact.dist_path : undefined
  const buildStatus = typeof buildArtifact?.status === 'string' ? buildArtifact.status : undefined

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
        {effectiveRun?.run_id ? (
          <span className="font-mono text-[11px] text-muted-foreground">
            {effectiveRun.run_id.slice(0, 10)}
          </span>
        ) : null}
        <div className="ml-auto flex items-center gap-1">
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
      {expanded ? (
        <div className="mt-3 max-h-[min(60vh,32rem)] space-y-3 overflow-y-auto pr-1">
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="rounded-md border border-border bg-muted/20 px-3 py-2">
              <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Current</div>
              <div className="mt-1 text-sm font-medium">{phaseLabel ?? 'Unknown'}</div>
              <div className="text-[11px] text-muted-foreground">{statusLabel ?? 'Unknown'}</div>
            </div>
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
