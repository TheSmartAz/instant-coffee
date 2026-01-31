import { Bot, Loader2, CheckCircle2, XCircle } from 'lucide-react'
import type { ExecutionEvent } from '@/types/events'
import { cn } from '@/lib/utils'
import { ProgressBar } from '@/components/EventFlow/ProgressBar'

interface AgentActivityProps {
  event: ExecutionEvent
}

export function AgentActivity({ event }: AgentActivityProps) {
  if (event.type === 'agent_start') {
    return (
      <div className="flex items-center gap-2 rounded-md border border-primary/20 bg-primary/5 px-2 py-2">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        <span className="text-sm text-foreground">{event.agent_type} agent started</span>
        {event.agent_instance ? (
          <span className="text-xs text-muted-foreground">#{event.agent_instance}</span>
        ) : null}
      </div>
    )
  }

  if (event.type === 'agent_progress') {
    return (
      <div className="rounded-md border border-border bg-muted/30 px-2 py-2">
        <div className="flex items-start gap-2">
          <Bot className="mt-0.5 h-4 w-4 text-muted-foreground" />
          <div className="flex-1 space-y-2">
            <div className="text-sm text-foreground">{event.message}</div>
            {typeof event.progress === 'number' ? (
              <ProgressBar value={event.progress} className="mt-1" />
            ) : null}
          </div>
        </div>
      </div>
    )
  }

  if (event.type === 'agent_end') {
    const isSuccess = event.status === 'success'
    return (
      <div
        className={cn(
          'flex items-center gap-2 rounded-md border px-2 py-2',
          isSuccess
            ? 'border-emerald-200 bg-emerald-50/70 text-emerald-700'
            : 'border-destructive/30 bg-destructive/10 text-destructive'
        )}
      >
        {isSuccess ? (
          <CheckCircle2 className="h-4 w-4" />
        ) : (
          <XCircle className="h-4 w-4" />
        )}
        <span className="text-sm">
          {event.summary || (isSuccess ? 'Agent completed' : 'Agent failed')}
        </span>
      </div>
    )
  }

  return null
}
