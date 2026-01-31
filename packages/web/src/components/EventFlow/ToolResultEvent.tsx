import { CheckCircle2, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ToolResultEvent } from '@/types/events'

interface ToolResultEventProps {
  event: ToolResultEvent
}

export function ToolResultEventDisplay({ event }: ToolResultEventProps) {
  const { tool_name, success, tool_output, error } = event

  // Format tool output for display
  const formatOutput = (output: unknown): string => {
    if (output === null || output === undefined) return ''
    try {
      const json = JSON.stringify(output, null, 2)
      // Truncate very long values
      const maxLength = 1000
      if (json.length > maxLength) {
        return json.slice(0, maxLength) + '\n... (truncated)'
      }
      return json
    } catch {
      return String(output)
    }
  }

  // Format error message
  const formatError = (err?: string): string => {
    if (!err) return 'Unknown error'
    return err
  }

  const hasOutput = tool_output !== undefined && tool_output !== null

  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-md border p-3',
        success
          ? 'border-emerald-200/70 bg-emerald-50/50'
          : 'border-destructive/30 bg-destructive/10'
      )}
    >
      <div className="mt-0.5 flex-shrink-0">
        <div
          className={cn(
            'flex h-7 w-7 items-center justify-center rounded-full',
            success ? 'bg-emerald-100' : 'bg-destructive/20'
          )}
        >
          {success ? (
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
          ) : (
            <XCircle className="h-3.5 w-3.5 text-destructive" />
          )}
        </div>
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">Tool Result</span>
          <span
            className={cn(
              'rounded-md px-2 py-0.5 text-xs font-medium',
              success
                ? 'bg-emerald-100 text-emerald-700'
                : 'bg-destructive/20 text-destructive'
            )}
          >
            {tool_name}
          </span>
          <span
            className={cn(
              'rounded-md px-2 py-0.5 text-xs font-medium',
              success
                ? 'bg-emerald-500/10 text-emerald-600'
                : 'bg-destructive/10 text-destructive'
            )}
          >
            {success ? 'Success' : 'Failed'}
          </span>
        </div>

        <div className="mt-2">
          {success && hasOutput ? (
            <details className="group">
              <summary
                className={cn(
                  'cursor-pointer text-xs',
                  success ? 'text-emerald-700 hover:text-emerald-900' : ''
                )}
              >
                {success ? 'Output' : 'Error details'} (click to expand)
              </summary>
              <pre
                className={cn(
                  'mt-2 overflow-x-auto rounded-md bg-background p-2 text-[11px]',
                  'border border-border/50'
                )}
              >
                {success ? formatOutput(tool_output) : formatError(error)}
              </pre>
            </details>
          ) : !success && error ? (
            <div
              className={cn(
                'rounded-md p-2 text-xs',
                success
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-destructive/20 text-destructive'
              )}
            >
              {formatError(error)}
            </div>
          ) : (
            <div className="text-xs text-muted-foreground">
              {success ? 'No output returned' : 'No error details available'}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
