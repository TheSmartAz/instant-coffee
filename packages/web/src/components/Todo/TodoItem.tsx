import {
  AlertTriangle,
  Check,
  Circle,
  Layers,
  Loader2,
  Lock,
  PauseCircle,
  RefreshCw,
  SkipForward,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { Task } from '@/types/plan'
import { ProgressBar } from '@/components/EventFlow/ProgressBar'

export type TaskAction = 'retry' | 'skip'

interface TodoItemProps {
  task: Task
  onAction?: (taskId: string, action: TaskAction) => void
}

const statusStyles = {
  pending: {
    icon: Circle,
    iconClass: 'text-muted-foreground',
    textClass: 'text-foreground',
  },
  in_progress: {
    icon: Loader2,
    iconClass: 'text-primary animate-spin',
    textClass: 'text-foreground',
  },
  done: {
    icon: Check,
    iconClass: 'text-foreground',
    textClass: 'text-muted-foreground line-through',
  },
  failed: {
    icon: X,
    iconClass: 'text-destructive',
    textClass: 'text-destructive',
  },
  timeout: {
    icon: AlertTriangle,
    iconClass: 'text-destructive',
    textClass: 'text-destructive',
  },
  aborted: {
    icon: PauseCircle,
    iconClass: 'text-muted-foreground',
    textClass: 'text-muted-foreground',
  },
  blocked: {
    icon: PauseCircle,
    iconClass: 'text-muted-foreground',
    textClass: 'text-muted-foreground',
  },
  skipped: {
    icon: SkipForward,
    iconClass: 'text-muted-foreground',
    textClass: 'text-muted-foreground line-through',
  },
  retrying: {
    icon: RefreshCw,
    iconClass: 'text-muted-foreground animate-spin',
    textClass: 'text-muted-foreground',
  },
}

const formatTokens = (n: number) => {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

const formatCost = (usd: number) => {
  if (usd < 0.01) return `$${usd.toFixed(4)}`
  return `$${usd.toFixed(2)}`
}

export function TodoItem({ task, onAction }: TodoItemProps) {
  const config = statusStyles[task.status]
  const Icon = config.icon
  const blockedCount = task.depends_on?.length ?? 0

  return (
    <div className="rounded-lg border border-border px-3 py-2">
      <div className="flex items-start gap-2">
        <Icon className={cn('mt-0.5 h-4 w-4', config.iconClass)} />
        <div className="flex-1 space-y-1">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5">
              <div className={cn('text-sm font-medium', config.textClass)}>
                {task.title}
              </div>
              {task.can_parallel ? (
                <span className="inline-flex items-center gap-0.5 rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                  <Layers className="h-3 w-3" />
                  Parallel
                </span>
              ) : null}
            </div>
            {task.status === 'retrying' ? (
              <span className="text-xs text-muted-foreground">
                Retry {task.retry_count}
              </span>
            ) : null}
          </div>
          {task.description ? (
            <div className="text-xs text-muted-foreground">{task.description}</div>
          ) : null}
          {task.status === 'blocked' && blockedCount > 0 ? (
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Lock className="h-3 w-3" />
              Blocked by {blockedCount} task{blockedCount !== 1 ? 's' : ''}
            </div>
          ) : null}
          {task.status === 'in_progress' ? (
            <ProgressBar value={task.progress} className="mt-2" />
          ) : null}
          {(task.status === 'failed' || task.status === 'timeout') && task.error_message ? (
            <div className="flex items-start gap-2 rounded-md bg-destructive/10 px-2 py-1 text-xs text-destructive">
              <AlertTriangle className="mt-0.5 h-3 w-3" />
              <span>{task.error_message}</span>
            </div>
          ) : null}
          {(task.status === 'failed' || task.status === 'timeout') && onAction ? (
            <div className="flex gap-2 pt-1">
              <Button
                size="sm"
                variant="outline"
                onClick={() => onAction(task.id, 'retry')}
              >
                Retry
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => onAction(task.id, 'skip')}
              >
                Skip
              </Button>
            </div>
          ) : null}
          {task.status === 'done' && task.token_usage ? (
            <div className="text-[10px] text-muted-foreground">
              {formatTokens(task.token_usage.total_tokens)} tokens · {formatCost(task.token_usage.cost_usd)}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
