import * as React from 'react'
import { CheckCircle2, Clock, Loader2, RotateCcw, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { BuildProgress, BuildStatusType } from '@/types/build'

const STATUS_CONFIG: Record<
  BuildStatusType,
  { label: string; tone: string; icon: typeof Clock; spin?: boolean }
> = {
  idle: {
    label: 'Ready',
    tone: 'bg-muted text-muted-foreground',
    icon: Clock,
  },
  pending: {
    label: 'Pending',
    tone: 'bg-amber-100 text-amber-700',
    icon: Clock,
  },
  building: {
    label: 'Building',
    tone: 'bg-blue-100 text-blue-700',
    icon: Loader2,
    spin: true,
  },
  success: {
    label: 'Complete',
    tone: 'bg-emerald-100 text-emerald-700',
    icon: CheckCircle2,
  },
  failed: {
    label: 'Failed',
    tone: 'bg-rose-100 text-rose-700',
    icon: XCircle,
  },
}

const formatDuration = (ms: number) => {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const seconds = totalSeconds % 60
  const minutes = Math.floor(totalSeconds / 60) % 60
  const hours = Math.floor(totalSeconds / 3600)
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  }
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

const normalizePageLabel = (page: string) => {
  const normalized = page.replace(/\\/g, '/').replace(/^pages\//, '')
  if (normalized.endsWith('/index.html')) {
    return normalized.replace('/index.html', '') || 'index'
  }
  if (normalized.endsWith('index.html')) {
    const trimmed = normalized.replace('index.html', '')
    return trimmed ? trimmed.replace(/\/$/, '') : 'index'
  }
  if (normalized.endsWith('.html')) {
    return normalized.replace('.html', '')
  }
  return normalized
}

export interface BuildStatusIndicatorProps {
  status: BuildStatusType
  progress?: BuildProgress
  pages?: string[]
  error?: string
  startedAt?: string
  completedAt?: string
  onRetry?: () => void
  onCancel?: () => void
  onPageSelect?: (page: string) => void
  selectedPage?: string | null
  className?: string
}

export function BuildStatusIndicator({
  status,
  progress,
  pages,
  error,
  startedAt,
  completedAt,
  onRetry,
  onCancel,
  onPageSelect,
  selectedPage,
  className,
}: BuildStatusIndicatorProps) {
  const config = STATUS_CONFIG[status]
  const Icon = config.icon
  const percent = typeof progress?.percent === 'number' ? progress.percent : undefined
  const stepLabel = progress?.step || progress?.message

  const [elapsedMs, setElapsedMs] = React.useState<number | null>(null)

  React.useEffect(() => {
    if (!startedAt) {
      setElapsedMs(null)
      return
    }
    const startMs = Date.parse(startedAt)
    if (Number.isNaN(startMs)) {
      setElapsedMs(null)
      return
    }

    const computeElapsed = () => {
      const endMs =
        completedAt && status !== 'building' && status !== 'pending'
          ? Date.parse(completedAt)
          : Date.now()
      setElapsedMs(endMs - startMs)
    }

    computeElapsed()
    if (status === 'building' || status === 'pending') {
      const interval = window.setInterval(computeElapsed, 1000)
      return () => window.clearInterval(interval)
    }
  }, [completedAt, startedAt, status])

  return (
    <div className={cn('rounded-lg border border-border bg-background p-4', className)}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span
            className={cn(
              'mt-0.5 inline-flex h-9 w-9 items-center justify-center rounded-full text-xs font-semibold',
              config.tone
            )}
          >
            <Icon className={cn('h-4 w-4', config.spin ? 'animate-spin' : '')} />
          </span>
          <div>
            <div className="text-sm font-semibold text-foreground">{config.label}</div>
            <div className="text-xs text-muted-foreground">
              {stepLabel ??
                (status === 'failed'
                  ? 'Build failed'
                  : status === 'success'
                    ? 'Build ready'
                    : 'Waiting for build')}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {(status === 'building' || status === 'pending') && onCancel ? (
            <Button size="sm" variant="outline" onClick={onCancel}>
              Cancel
            </Button>
          ) : null}
          {status === 'failed' && onRetry ? (
            <Button size="sm" onClick={onRetry}>
              <RotateCcw className="h-3 w-3" />
              Retry
            </Button>
          ) : null}
        </div>
      </div>

      {status === 'building' || status === 'pending' ? (
        <div className="mt-4 space-y-2">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{stepLabel ?? 'Preparing build...'}</span>
            <span className="tabular-nums">
              {typeof percent === 'number' ? `${Math.round(percent)}%` : '—'}
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full bg-primary transition-all"
              style={{ width: `${percent ?? 0}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-[11px] text-muted-foreground">
            <span>
              {elapsedMs !== null ? `Elapsed ${formatDuration(elapsedMs)}` : 'Elapsed —'}
            </span>
            <span>{status === 'pending' ? 'Queued' : 'Running'}</span>
          </div>
        </div>
      ) : null}

      {status === 'failed' && error ? (
        <div className="mt-3 rounded-md border border-destructive/20 bg-destructive/5 p-3 text-xs text-destructive">
          <div className="font-semibold">Build error</div>
          <div className="mt-1 whitespace-pre-wrap">{error}</div>
        </div>
      ) : null}

      {status === 'success' && pages && pages.length > 0 ? (
        <div className="mt-4 border-t border-border pt-3">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{pages.length} pages generated</span>
            {elapsedMs !== null ? <span>Elapsed {formatDuration(elapsedMs)}</span> : null}
          </div>
          <div className="mt-3 grid gap-2">
            <select
              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              value={selectedPage ?? ''}
              onChange={(event) => onPageSelect?.(event.target.value)}
            >
              <option value="">Select a page</option>
              {pages.map((page) => {
                const label = normalizePageLabel(page)
                return (
                  <option key={page} value={page}>
                    {label}
                  </option>
                )
              })}
            </select>
            <div className="flex flex-wrap gap-2">
              {pages.map((page) => {
                const label = normalizePageLabel(page)
                const isSelected = selectedPage === page
                return (
                  <button
                    key={page}
                    type="button"
                    onClick={() => onPageSelect?.(page)}
                    className={cn(
                      'rounded-full border px-3 py-1 text-xs transition',
                      isSelected
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'border-border bg-background text-foreground hover:bg-muted'
                    )}
                  >
                    {label}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
