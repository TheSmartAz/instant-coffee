import { Circle, CircleDot, CheckCircle2, Lock, AlertCircle, RefreshCw, SkipForward, Layers } from 'lucide-react'
import type { PlanStep, PlanTaskSnapshot, TaskStatus } from '@/types/events'

const STATUS_CONFIG: Record<
  string,
  { icon: typeof Circle; className: string }
> = {
  pending: { icon: Circle, className: 'text-muted-foreground' },
  in_progress: { icon: CircleDot, className: 'text-foreground animate-pulse' },
  completed: { icon: CheckCircle2, className: 'text-foreground' },
}

const TASK_STATUS_CONFIG: Record<
  TaskStatus,
  { icon: typeof Circle; className: string }
> = {
  pending: { icon: Circle, className: 'text-muted-foreground' },
  in_progress: { icon: CircleDot, className: 'text-foreground animate-pulse' },
  done: { icon: CheckCircle2, className: 'text-foreground' },
  failed: { icon: AlertCircle, className: 'text-destructive' },
  aborted: { icon: Circle, className: 'text-muted-foreground' },
  timeout: { icon: AlertCircle, className: 'text-destructive' },
  blocked: { icon: Lock, className: 'text-muted-foreground' },
  skipped: { icon: SkipForward, className: 'text-muted-foreground' },
  retrying: { icon: RefreshCw, className: 'text-muted-foreground animate-spin' },
}

interface PlanChecklistProps {
  steps?: PlanStep[]
  tasks?: PlanTaskSnapshot[]
  explanation?: string
}

export function PlanChecklist({ steps, tasks, explanation }: PlanChecklistProps) {
  // Tasks mode (rich plan_created data)
  if (tasks && tasks.length > 0) {
    const doneCount = tasks.filter((t) => t.status === 'done').length
    const failedCount = tasks.filter((t) => t.status === 'failed').length
    const totalCount = tasks.length
    const progressPercent = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0

    return (
      <div className="mt-2 rounded-lg border border-border/60 bg-muted/30 p-3">
        {explanation ? (
          <div className="mb-2 text-xs text-muted-foreground">{explanation}</div>
        ) : null}
        <div className="mb-1.5 flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground">
            Plan ({doneCount}/{totalCount})
          </span>
          {failedCount > 0 ? (
            <span className="text-[10px] text-destructive">{failedCount} failed</span>
          ) : null}
        </div>
        {/* Progress bar */}
        <div className="mb-2 h-1.5 w-full rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-foreground transition-all"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <div className="space-y-1">
          {tasks.map((task) => {
            const config = TASK_STATUS_CONFIG[task.status] ?? TASK_STATUS_CONFIG.pending
            const Icon = config.icon
            const blockedCount = task.depends_on?.length ?? 0
            const isDone = task.status === 'done' || task.status === 'skipped'

            return (
              <div
                key={task.id}
                className="flex items-start gap-2 text-xs"
              >
                <Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${config.className}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span
                      className={
                        isDone
                          ? 'text-muted-foreground line-through'
                          : task.status === 'failed'
                            ? 'text-destructive'
                            : 'text-foreground'
                      }
                    >
                      {task.title || task.description || `Task ${task.id}`}
                    </span>
                    {task.can_parallel ? (
                      <span className="inline-flex items-center gap-0.5 rounded bg-muted px-1 py-px text-[9px] font-medium text-muted-foreground">
                        <Layers className="h-2.5 w-2.5" />
                        Parallel
                      </span>
                    ) : null}
                  </div>
                  {task.status === 'blocked' && blockedCount > 0 ? (
                    <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                      <Lock className="h-2.5 w-2.5" />
                      Blocked by {blockedCount} task{blockedCount !== 1 ? 's' : ''}
                    </div>
                  ) : null}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  // Steps mode (simple plan_update data)
  if (!steps || !steps.length) return null

  const completed = steps.filter((s) => s.status === 'completed').length

  return (
    <div className="mt-2 rounded-lg border border-border/60 bg-muted/30 p-3">
      {explanation ? (
        <div className="mb-2 text-xs text-muted-foreground">{explanation}</div>
      ) : null}
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">
          Plan ({completed}/{steps.length})
        </span>
      </div>
      <div className="space-y-1">
        {steps.map((step, i) => {
          const config = STATUS_CONFIG[step.status] ?? STATUS_CONFIG.pending
          const Icon = config.icon

          return (
            <div
              key={`step-${i}`}
              className="flex items-start gap-2 text-xs"
            >
              <Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${config.className}`} />
              <span
                className={
                  step.status === 'completed'
                    ? 'text-muted-foreground line-through'
                    : 'text-foreground'
                }
              >
                {step.step || `Step ${i + 1}`}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
