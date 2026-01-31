import { cn } from '@/lib/utils'
import type { EventStatus } from './StatusIcon'

interface ProgressBarProps {
  value: number
  status?: EventStatus
  className?: string
}

export function ProgressBar({ value, status = 'in_progress', className }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value))

  const barClass = cn(
    'h-1.5 rounded-full transition-all',
    status === 'failed' && 'bg-destructive',
    status === 'done' && 'bg-emerald-500',
    status === 'pending' && 'bg-muted-foreground/40',
    status === 'in_progress' && 'bg-primary'
  )

  return (
    <div
      className={cn('h-1.5 w-full rounded-full bg-muted', className)}
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div className={barClass} style={{ width: `${clamped}%` }} />
    </div>
  )
}
