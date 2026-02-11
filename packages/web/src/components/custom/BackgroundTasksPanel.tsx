import * as React from 'react'
import { Square, Play, Maximize2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { useBackgroundTasks } from '@/hooks/useBackgroundTasks'

interface BackgroundTasksPanelProps {
  sessionId: string | undefined
  className?: string
}

export function BackgroundTasksPanel({ sessionId, className }: BackgroundTasksPanelProps) {
  const { tasks, isLoading, refresh, stopTask, getTaskOutput } = useBackgroundTasks(sessionId)
  const [outputStates, setOutputStates] = React.useState<Record<string, { output: string; since: number }>>({})

  // Auto-refresh output for running tasks
  React.useEffect(() => {
    if (!sessionId) return

    const interval = setInterval(async () => {
      const runningTasks = tasks.filter(t => t.status === 'running')
      if (runningTasks.length === 0) return

      for (const task of runningTasks) {
        try {
          const since = outputStates[task.id]?.since || 0
          const result = await getTaskOutput(task.id, since)
          if (result && !result.error) {
            setOutputStates(prev => ({
              ...prev,
              [task.id]: {
                output: result.output,
                since: result.output_lines || 0,
              },
            }))
          }
        } catch (e) {
          console.error(`Failed to fetch output for task ${task.id}:`, e)
        }
      }
    }, 1000) // Poll output every second

    return () => clearInterval(interval)
  }, [sessionId, tasks, outputStates, getTaskOutput])

  if (isLoading) {
    return (
      <div className={className}>
        <div className="p-4 border-b border-border">
          <h3 className="text-sm font-semibold">Background Tasks</h3>
        </div>
        <div className="p-4 space-y-2">
          <Skeleton className="h-16 w-full" />
        </div>
      </div>
    )
  }

  return (
    <div className={className}>
      <div className="flex items-center justify-between p-4 border-b border-border">
        <h3 className="text-sm font-semibold">Background Tasks</h3>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => refresh()}
          aria-label="Refresh background tasks"
        >
          <Play className="h-4 w-4" />
        </Button>
      </div>

      <ScrollArea className="h-[300px]">
        {tasks.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            No background tasks running
          </div>
        ) : (
          <div className="p-2 space-y-2">
            {tasks.map(task => (
              <TaskItem
                key={task.id}
                task={task}
                output={outputStates[task.id]?.output || ''}
                onStop={() => stopTask(task.id)}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  )
}

interface TaskItemProps {
  task: {
    id: string
    command: string
    status: string
    pid: number | null
    exit_code: number | null
    created_at: string
    output_lines: number
    output_preview: string[]
  }
  output: string
  onStop: () => void
}

function TaskItem({ task, output, onStop }: TaskItemProps) {
  const [isExpanded, setIsExpanded] = React.useState(false)

  const statusColors: Record<string, string> = {
    starting: 'bg-yellow-500',
    running: 'bg-green-500',
    stopped: 'bg-gray-500',
    failed: 'bg-red-500',
  }
  const statusColor = statusColors[task.status] || 'bg-gray-500'

  return (
    <div className="rounded-lg border border-border bg-background">
      <div
        className="flex items-center gap-3 p-3 cursor-pointer hover:bg-accent/50"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className={`h-2 w-2 rounded-full ${statusColor}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <code className="text-xs font-mono truncate">
              {task.command}
            </code>
            <Badge variant="outline" className="text-xs">
              {task.status}
            </Badge>
          </div>
          {task.pid && (
            <div className="text-xs text-muted-foreground">
              PID: {task.pid}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1">
          <Badge variant="secondary" className="text-xs">
            {task.output_lines} lines
          </Badge>
          {task.status === 'running' && (
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={(e) => {
                  e.stopPropagation()
                  onStop()
                }}
                aria-label="Stop task"
              >
                <Square className="h-3 w-3" />
              </Button>
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="border-t border-border p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground">Output</span>
            {output.length > 0 && (
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => navigator.clipboard.writeText(output)}
                aria-label="Copy task output"
              >
                <Maximize2 className="h-3 w-3" />
              </Button>
            )}
          </div>
          <pre className="text-xs font-mono bg-muted rounded p-2 overflow-x-auto whitespace-pre-wrap max-h-[150px] overflow-y-auto">
            {output || task.output_preview.join('\n') || 'No output yet...'}
          </pre>
        </div>
      )}
    </div>
  )
}
