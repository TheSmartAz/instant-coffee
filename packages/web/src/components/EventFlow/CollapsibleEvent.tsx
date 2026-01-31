import * as React from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { EventStatus } from './StatusIcon'
import { StatusIcon } from './StatusIcon'
import { ProgressBar } from './ProgressBar'

interface CollapsibleEventProps {
  title: string
  timestamp?: string
  status: EventStatus
  badge?: string
  details?: React.ReactNode
  progress?: number
  defaultCollapsed?: boolean
  isCollapsible?: boolean
}

export function CollapsibleEvent({
  title,
  timestamp,
  status,
  badge,
  details,
  progress,
  defaultCollapsed = status === 'done',
  isCollapsible = Boolean(details),
}: CollapsibleEventProps) {
  const [isOpen, setIsOpen] = React.useState(!defaultCollapsed)

  const containerClass = cn(
    'rounded-lg border px-3 py-2.5 transition-colors',
    status === 'done' && 'border-emerald-200 bg-emerald-50/70',
    status === 'failed' && 'border-destructive/30 bg-destructive/10',
    status === 'in_progress' && 'border-primary/20 bg-primary/5',
    status === 'pending' && 'border-border bg-background'
  )

  return (
    <Collapsible open={isCollapsible ? isOpen : true} onOpenChange={setIsOpen}>
      <div className={containerClass}>
        <CollapsibleTrigger asChild disabled={!isCollapsible}>
          <button
            type="button"
            className={cn(
              'flex w-full items-center gap-2 text-left',
              isCollapsible ? 'cursor-pointer' : 'cursor-default'
            )}
            aria-expanded={isCollapsible ? isOpen : undefined}
          >
            <StatusIcon status={status} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="truncate text-sm font-medium text-foreground">{title}</span>
                {badge ? (
                  <Badge variant="secondary" className="text-[10px]">
                    {badge}
                  </Badge>
                ) : null}
              </div>
              {timestamp ? (
                <div className="text-xs text-muted-foreground">{timestamp}</div>
              ) : null}
            </div>
            {isCollapsible ? (
              isOpen ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              )
            ) : null}
          </button>
        </CollapsibleTrigger>

        {typeof progress === 'number' ? (
          <div className="mt-2">
            <ProgressBar value={progress} status={status} />
          </div>
        ) : null}

        {details ? (
          <CollapsibleContent className="mt-2 space-y-2 text-xs text-muted-foreground">
            {details}
          </CollapsibleContent>
        ) : null}
      </div>
    </Collapsible>
  )
}
