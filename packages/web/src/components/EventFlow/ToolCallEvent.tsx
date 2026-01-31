import { Wrench } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ToolCallEvent } from '@/types/events'

interface ToolCallEventProps {
  event: ToolCallEvent
}

export function ToolCallEventDisplay({ event }: ToolCallEventProps) {
  const { tool_name, tool_input } = event

  // Format tool input for display
  const formatInput = (input?: Record<string, unknown>): string => {
    if (!input) return '{}'
    try {
      const json = JSON.stringify(input, null, 2)
      // Truncate very long values
      const maxLength = 500
      if (json.length > maxLength) {
        return json.slice(0, maxLength) + '\n... (truncated)'
      }
      return json
    } catch {
      return String(input)
    }
  }

  const hasInput = tool_input && Object.keys(tool_input).length > 0

  return (
    <div className="flex items-start gap-3 rounded-md bg-muted/50 p-3">
      <div className="mt-0.5 flex-shrink-0">
        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10">
          <Wrench className="h-3.5 w-3.5 text-primary" />
        </div>
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">Tool Call</span>
          <span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            {tool_name}
          </span>
        </div>

        {hasInput ? (
          <div className="mt-2">
            <details className="group">
              <summary
                className="cursor-pointer text-xs text-muted-foreground hover:text-foreground"
              >
                Input parameters ({Object.keys(tool_input!).length})
              </summary>
              <pre
                className={cn(
                  'mt-2 overflow-x-auto rounded-md bg-background p-2 text-[11px]',
                  'border border-border/50'
                )}
              >
                {formatInput(tool_input)}
              </pre>
            </details>
          </div>
        ) : (
          <div className="mt-1 text-xs text-muted-foreground">No input parameters</div>
        )}
      </div>
    </div>
  )
}
