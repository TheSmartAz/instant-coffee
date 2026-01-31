import {
  AlertTriangle,
  Check,
  Circle,
  Loader2,
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
    iconClass: 'text-emerald-600',
    textClass: 'text-muted-foreground line-through',
  },
  failed: {
    icon: X,
    iconClass: 'text-destructive',
    textClass: 'text-destructive',
  },
  blocked: {
    icon: PauseCircle,
    iconClass: 'text-amber-500',
    textClass: 'text-amber-600',
  },
  skipped: {
    icon: SkipForward,
    iconClass: 'text-muted-foreground',
    textClass: 'text-muted-foreground line-through',
  },
  retrying: {
    icon: RefreshCw,
    iconClass: 'text-yellow-500 animate-spin',
    textClass: 'text-yellow-600',
  },
}

export function TodoItem({ task, onAction }: TodoItemProps) {
  const config = statusStyles[task.status]
  const Icon = config.icon

  return (
    <div className="rounded-lg border border-border px-3 py-2">
      <div className="flex items-start gap-2">
        <Icon className={cn('mt-0.5 h-4 w-4', config.iconClass)} />
        <div className="flex-1 space-y-1">
          <div className="flex items-center justify-between gap-2">
            <div className={cn('text-sm font-medium', config.textClass)}>
              {task.title}
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
          {task.status === 'in_progress' ? (
            <ProgressBar value={task.progress} className="mt-2" />
          ) : null}
          {task.status === 'failed' && task.error_message ? (
            <div className="flex items-start gap-2 rounded-md bg-destructive/10 px-2 py-1 text-xs text-destructive">
              <AlertTriangle className="mt-0.5 h-3 w-3" />
              <span>{task.error_message}</span>
            </div>
          ) : null}
          {task.status === 'failed' && onAction ? (
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
        </div>
      </div>
    </div>
  )
}
