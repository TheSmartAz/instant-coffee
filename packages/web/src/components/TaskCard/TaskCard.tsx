import * as React from 'react'
import { ChevronDown, ChevronRight, Coins } from 'lucide-react'
import type { ExecutionEvent } from '@/types/events'
import { isAgentEvent, isToolEvent } from '@/types/events'
import type { Task } from '@/types/plan'
import { cn } from '@/lib/utils'
import { StatusIcon } from '@/components/EventFlow/StatusIcon'
import { ProgressBar } from '@/components/EventFlow/ProgressBar'
import { AgentActivity } from './AgentActivity'
import { ToolCallLog } from './ToolCallLog'

interface TaskCardProps {
  task: Task
  events: ExecutionEvent[]
  isActive: boolean
}

interface TaskTokenUsageProps {
  usage: {
    input_tokens: number
    output_tokens: number
    total_tokens: number
    cost_usd: number
  }
}

function TaskTokenUsage({ usage }: TaskTokenUsageProps) {
  if (usage.total_tokens === 0) {
    return null
  }

  const inputPercent = (usage.input_tokens / usage.total_tokens) * 100
  const outputPercent = (usage.output_tokens / usage.total_tokens) * 100

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <Coins className="h-3 w-3 text-amber-500" />
          <span>Token Usage</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-muted-foreground">{usage.total_tokens.toLocaleString()}</span>
          <span className="font-mono text-emerald-600">${usage.cost_usd.toFixed(4)}</span>
        </div>
      </div>
      <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-muted">
        {inputPercent > 0 && (
          <div
            className="bg-blue-500"
            style={{ width: `${inputPercent}%` }}
            title={`Input: ${usage.input_tokens.toLocaleString()}`}
          />
        )}
        {outputPercent > 0 && (
          <div
            className="bg-emerald-500"
            style={{ width: `${outputPercent}%` }}
            title={`Output: ${usage.output_tokens.toLocaleString()}`}
          />
        )}
      </div>
      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
        <span>In: {usage.input_tokens.toLocaleString()}</span>
        <span>Out: {usage.output_tokens.toLocaleString()}</span>
      </div>
    </div>
  )
}

const getStatusStyle = (status: Task['status']) => {
  switch (status) {
    case 'done':
      return 'border-emerald-200 bg-emerald-50/60'
    case 'failed':
    case 'timeout':
      return 'border-destructive/30 bg-destructive/10'
    case 'aborted':
      return 'border-muted-foreground/20 bg-muted/30'
    case 'in_progress':
      return 'border-primary/20 bg-primary/5'
    case 'blocked':
      return 'border-amber-200 bg-amber-50/60'
    case 'retrying':
      return 'border-yellow-200 bg-yellow-50/60'
    default:
      return 'border-border bg-background'
  }
}

const getStatusIcon = (status: Task['status']) => {
  switch (status) {
    case 'done':
      return 'done'
    case 'failed':
    case 'timeout':
      return 'failed'
    case 'in_progress':
    case 'retrying':
      return 'in_progress'
    case 'blocked':
      return 'pending'
    case 'skipped':
      return 'done'
    case 'aborted':
      return 'pending'
    default:
      return 'pending'
  }
}

export const TaskCard = React.memo(function TaskCard({ task, events, isActive }: TaskCardProps) {
  const [isExpanded, setIsExpanded] = React.useState(isActive)

  React.useEffect(() => {
    if (isActive) {
      setIsExpanded(true)
    }
  }, [isActive])

  const taskEvents = events

  const agentEvents = React.useMemo(
    () => taskEvents.filter((event) => isAgentEvent(event)),
    [taskEvents]
  )
  const toolEvents = React.useMemo(
    () => taskEvents.filter((event) => isToolEvent(event)),
    [taskEvents]
  )

  return (
    <div
      className={cn(
        'rounded-lg border transition-all',
        getStatusStyle(task.status),
        isActive ? 'ring-2 ring-ring ring-offset-2 ring-offset-background' : ''
      )}
    >
      <button
        type="button"
        onClick={() => setIsExpanded((prev) => !prev)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
        aria-expanded={isExpanded}
      >
        <StatusIcon status={getStatusIcon(task.status)} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold text-foreground">{task.title}</div>
          {task.agent_type ? (
            <div className="text-xs text-muted-foreground">Agent: {task.agent_type}</div>
          ) : null}
        </div>
        {task.status === 'in_progress' ? (
          <div className="flex items-center gap-2">
            <ProgressBar value={task.progress} className="w-20" />
            <span className="text-xs text-muted-foreground">{task.progress}%</span>
          </div>
        ) : null}
        {isExpanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {isExpanded ? (
        <div className="border-t border-border px-4 py-3 space-y-4">
          {task.description ? (
            <div className="text-sm text-muted-foreground">{task.description}</div>
          ) : null}

          {task.token_usage ? (
            <TaskTokenUsage usage={task.token_usage} />
          ) : null}

          {agentEvents.length > 0 ? (
            <div className="space-y-2">
              <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Agent Activity
              </div>
              <div className="space-y-2">
                {agentEvents.map((event, index) => (
                  <AgentActivity key={`${event.timestamp}-${index}`} event={event} />
                ))}
              </div>
            </div>
          ) : null}

          {toolEvents.length > 0 ? (
            <div className="space-y-2">
              <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Tool Calls
              </div>
              <div className="space-y-2">
                {toolEvents.map((event, index) => (
                  <ToolCallLog key={`${event.timestamp}-${index}`} event={event} />
                ))}
              </div>
            </div>
          ) : null}

          {(task.status === 'failed' || task.status === 'timeout') && task.error_message ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {task.error_message}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}, (prev, next) => {
  if (prev.isActive !== next.isActive) return false
  if (prev.task !== next.task) return false
  if (prev.events !== next.events) return false
  return true
})
