import { Circle, CircleDot, CheckCircle2 } from 'lucide-react'
import type { PlanStep } from '@/types/events'

const STATUS_CONFIG: Record<
  string,
  { icon: typeof Circle; className: string }
> = {
  pending: { icon: Circle, className: 'text-muted-foreground' },
  in_progress: { icon: CircleDot, className: 'text-blue-500 animate-pulse' },
  completed: { icon: CheckCircle2, className: 'text-emerald-500' },
}

interface PlanChecklistProps {
  steps: PlanStep[]
  explanation?: string
}

export function PlanChecklist({ steps, explanation }: PlanChecklistProps) {
  if (!steps.length) return null

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
                {step.step}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
