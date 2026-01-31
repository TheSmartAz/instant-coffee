import { Check, X, Loader2, Circle } from 'lucide-react'
import { cn } from '@/lib/utils'

export type EventStatus = 'pending' | 'in_progress' | 'done' | 'failed'

interface StatusIconProps {
  status: EventStatus
  className?: string
}

export function StatusIcon({ status, className }: StatusIconProps) {
  const iconClass = cn('h-4 w-4', className)

  switch (status) {
    case 'done':
      return <Check className={cn(iconClass, 'text-emerald-600')} />
    case 'failed':
      return <X className={cn(iconClass, 'text-destructive')} />
    case 'in_progress':
      return <Loader2 className={cn(iconClass, 'animate-spin text-primary')} />
    case 'pending':
    default:
      return <Circle className={cn(iconClass, 'text-muted-foreground')} />
  }
}
