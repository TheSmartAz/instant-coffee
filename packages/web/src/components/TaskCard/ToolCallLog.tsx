import * as React from 'react'
import { Check, ChevronDown, ChevronRight, Wrench, X } from 'lucide-react'
import type { ExecutionEvent } from '@/types/events'
import { cn } from '@/lib/utils'

interface ToolCallLogProps {
  event: ExecutionEvent
}

export function ToolCallLog({ event }: ToolCallLogProps) {
  const [isExpanded, setIsExpanded] = React.useState(false)

  if (event.type === 'tool_call') {
    return (
      <div className="rounded-md border border-border">
        <button
          type="button"
          onClick={() => setIsExpanded((prev) => !prev)}
          className="flex w-full items-center gap-2 px-2 py-2 text-left text-sm hover:bg-muted/40"
        >
          <Wrench className="h-4 w-4 text-primary" />
          <span className="flex-1 font-medium text-foreground">{event.tool_name}</span>
          <span className="text-xs text-muted-foreground">Calling…</span>
          {event.tool_input ? (
            isExpanded ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )
          ) : null}
        </button>
        {isExpanded && event.tool_input ? (
          <div className="border-t border-border bg-muted/30 px-3 py-2">
            <div className="text-xs font-medium text-muted-foreground">Input</div>
            <pre className="mt-1 whitespace-pre-wrap text-xs text-foreground">
              {JSON.stringify(event.tool_input, null, 2)}
            </pre>
          </div>
        ) : null}
      </div>
    )
  }

  if (event.type === 'tool_result') {
    const isSuccess = event.success
    return (
      <div
        className={cn(
          'rounded-md border',
          isSuccess ? 'border-emerald-200' : 'border-destructive/40'
        )}
      >
        <button
          type="button"
          onClick={() => setIsExpanded((prev) => !prev)}
          className={cn(
            'flex w-full items-center gap-2 px-2 py-2 text-left text-sm',
            isSuccess ? 'hover:bg-emerald-50/50' : 'hover:bg-destructive/10'
          )}
        >
          {isSuccess ? (
            <Check className="h-4 w-4 text-emerald-600" />
          ) : (
            <X className="h-4 w-4 text-destructive" />
          )}
          <span className="flex-1 font-medium text-foreground">{event.tool_name}</span>
          <span
            className={cn(
              'text-xs',
              isSuccess ? 'text-emerald-600' : 'text-destructive'
            )}
          >
            {isSuccess ? 'Success' : 'Failed'}
          </span>
          {event.tool_output || event.error ? (
            isExpanded ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )
          ) : null}
        </button>
        {isExpanded ? (
          <div
            className={cn(
              'border-t px-3 py-2',
              isSuccess ? 'border-emerald-200 bg-emerald-50/60' : 'border-destructive/40 bg-destructive/10'
            )}
          >
            {isSuccess && event.tool_output ? (
              <>
                <div className="text-xs font-medium text-muted-foreground">Output</div>
                <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap text-xs text-foreground">
                  {JSON.stringify(event.tool_output, null, 2)}
                </pre>
              </>
            ) : null}
            {!isSuccess && event.error ? (
              <>
                <div className="text-xs font-medium text-destructive">Error</div>
                <pre className="mt-1 whitespace-pre-wrap text-xs text-destructive">
                  {event.error}
                </pre>
              </>
            ) : null}
          </div>
        ) : null}
      </div>
    )
  }

  return null
}
