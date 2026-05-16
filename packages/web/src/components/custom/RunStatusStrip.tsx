import { AlertCircle, CheckCircle2, Clock, Loader2, ShieldAlert, XCircle } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ChatRunStatus, ChatRunStatusStage } from '@/types'

interface RunStatusStripProps {
  status?: ChatRunStatus | null
}

type StatusTone = 'running' | 'success' | 'failed' | 'waiting' | 'warning'

const STAGE_LABELS: Record<ChatRunStatusStage, string> = {
  run: 'Run',
  build: 'Build',
  review: 'Review',
  policy: 'Policy',
}

const PHASE_LABELS: Record<string, string> = {
  plan: 'Plan',
  implement: 'Implement',
  build: 'Build',
  review: 'Review',
  fix: 'Fix',
  done: 'Done',
}

const TONE_STYLES: Record<StatusTone, { icon: LucideIcon; className: string; dot: string }> = {
  running: {
    icon: Loader2,
    className: 'border-blue-200 bg-blue-50 text-blue-900 dark:border-blue-900/60 dark:bg-blue-950/30 dark:text-blue-100',
    dot: 'bg-blue-500',
  },
  success: {
    icon: CheckCircle2,
    className: 'border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-100',
    dot: 'bg-emerald-500',
  },
  failed: {
    icon: XCircle,
    className: 'border-destructive/30 bg-destructive/10 text-destructive',
    dot: 'bg-destructive',
  },
  waiting: {
    icon: Clock,
    className: 'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-100',
    dot: 'bg-amber-500',
  },
  warning: {
    icon: AlertCircle,
    className: 'border-orange-200 bg-orange-50 text-orange-900 dark:border-orange-900/60 dark:bg-orange-950/30 dark:text-orange-100',
    dot: 'bg-orange-500',
  },
}

const formatPhase = (phase?: string) => {
  if (!phase) return undefined
  return PHASE_LABELS[phase] ?? phase.replace(/_/g, ' ')
}

const formatStatus = (status?: string) => {
  if (!status) return undefined
  return status.replace(/_/g, ' ')
}

const formatRunId = (runId?: string) => {
  if (!runId) return undefined
  return runId.length > 10 ? runId.slice(0, 10) : runId
}

const EXECUTION_MODE_LABELS = {
  plan: 'Plan only',
  agent: 'Agent',
  auto: 'Auto',
} as const

const formatSummary = (summary?: Record<string, unknown>) => {
  if (!summary) return undefined
  const parts: string[] = []
  const errorCount = summary.error_count
  const warningCount = summary.warning_count
  const buildStatus = summary.build_status
  const generatedPages = summary.generated_pages
  const distPath = summary.dist_path

  if (typeof errorCount === 'number') parts.push(`${errorCount} errors`)
  if (typeof warningCount === 'number') parts.push(`${warningCount} warnings`)
  if (typeof buildStatus === 'string' && buildStatus) parts.push(`build ${buildStatus}`)
  if (Array.isArray(generatedPages)) parts.push(`${generatedPages.length} pages`)
  if (typeof distPath === 'string' && distPath) parts.push('dist ready')
  return parts.length ? parts.join(', ') : undefined
}

const getTone = (status: ChatRunStatus): StatusTone => {
  const normalized = (status.status ?? '').toLowerCase()
  if (status.eventType === 'tool_policy_warn' || normalized === 'warning') return 'warning'
  if (normalized === 'waiting_input' || status.eventType === 'run_waiting_input') return 'waiting'
  if (
    normalized === 'failed' ||
    normalized === 'cancelled' ||
    status.eventType.endsWith('_failed') ||
    status.eventType.endsWith('_fail') ||
    status.eventType.endsWith('_blocked') ||
    status.eventType.endsWith('_cancelled')
  ) {
    return 'failed'
  }
  if (
    normalized === 'completed' ||
    normalized === 'success' ||
    status.eventType.endsWith('_complete') ||
    status.eventType.endsWith('_completed') ||
    status.eventType.endsWith('_pass')
  ) {
    return 'success'
  }
  return 'running'
}

const getTitle = (status: ChatRunStatus) => {
  if (status.eventType === 'verify_pass') return 'Review passed'
  if (status.eventType === 'verify_fail') return 'Review failed'
  if (status.eventType === 'verify_start') return 'Review running'
  if (status.eventType === 'build_complete') return 'Build complete'
  if (status.eventType === 'build_failed') return 'Build failed'
  if (status.eventType === 'build_start') return 'Build running'
  if (status.eventType === 'run_waiting_input') return 'Waiting for input'
  if (status.eventType === 'run_resumed') return 'Run resumed'
  if (status.eventType === 'run_completed') return 'Run complete'
  if (status.eventType === 'run_failed') return 'Run failed'

  const phase = formatPhase(status.phase)
  const subject = status.stage === 'run' && phase ? phase : STAGE_LABELS[status.stage]
  const state = formatStatus(status.status)
  return state ? `${subject} ${state}` : subject
}

const clampPercent = (percent?: number) => {
  if (typeof percent !== 'number' || !Number.isFinite(percent)) return undefined
  return Math.max(0, Math.min(100, percent))
}

export function RunStatusStrip({ status }: RunStatusStripProps) {
  if (!status) return null

  const tone = getTone(status)
  const toneStyle = TONE_STYLES[tone]
  const Icon = status.stage === 'policy' ? ShieldAlert : toneStyle.icon
  const percent = clampPercent(status.percent)
  const detail = status.error ?? status.message ?? formatSummary(status.summary)
  const runId = formatRunId(status.runId)
  const executionMode = status.executionMode ? EXECUTION_MODE_LABELS[status.executionMode] : undefined

  return (
    <div
      className="border-t border-border bg-background px-4 py-2"
      role="status"
      aria-live="polite"
      data-testid="run-status-strip"
    >
      <div
        className={cn(
          'flex min-h-9 min-w-0 items-center gap-2 rounded-md border px-3 py-2 text-xs',
          toneStyle.className,
        )}
      >
        <Icon
          className={cn('h-4 w-4 shrink-0', tone === 'running' && 'animate-spin')}
          aria-hidden="true"
        />
        <span className={cn('h-2 w-2 shrink-0 rounded-full', toneStyle.dot)} />
        <span className="shrink-0 font-medium">{getTitle(status)}</span>
        {percent !== undefined ? (
          <div className="hidden h-1.5 w-20 shrink-0 overflow-hidden rounded-full bg-background/70 sm:block">
            <div
              className={cn('h-full rounded-full', toneStyle.dot)}
              style={{ width: `${percent}%` }}
            />
          </div>
        ) : null}
        {detail ? (
          <span className="min-w-0 flex-1 truncate text-current/75">{detail}</span>
        ) : (
          <span className="min-w-0 flex-1" />
        )}
        {runId ? (
          <span className="hidden shrink-0 font-mono text-[11px] text-current/60 sm:inline">
            {runId}
          </span>
        ) : null}
        {executionMode ? (
          <span className="shrink-0 rounded-full border border-current/20 px-2 py-0.5 text-[11px] font-medium text-current/75">
            {executionMode}
          </span>
        ) : null}
      </div>
    </div>
  )
}
