import type { ReactNode } from 'react'
import { format } from 'date-fns'
import type { ExecutionEvent, ToolCallEvent, ToolResultEvent } from '@/types/events'
import {
  isAgentEvent,
  isPlanEvent,
  isTaskEvent,
  isToolEvent,
} from '@/types/events'
import { CollapsibleEvent } from './CollapsibleEvent'
import type { EventStatus } from './StatusIcon'
import { ToolCallEventDisplay } from './ToolCallEvent'
import { ToolResultEventDisplay } from './ToolResultEvent'

interface EventItemProps {
  event: ExecutionEvent
}

const formatTimestamp = (timestamp?: string) => {
  if (!timestamp) return undefined
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return undefined
  return format(date, 'HH:mm:ss')
}

const getEventTitle = (event: ExecutionEvent): string => {
  switch (event.type) {
    case 'plan_created':
      return event.plan ? `Plan created: ${event.plan.goal}` : 'Plan created'
    case 'plan_updated':
      return `Plan updated (${event.changes.length} change${
        event.changes.length === 1 ? '' : 's'
      })`
    case 'agent_start':
      return `${event.agent_type} agent started`
    case 'agent_progress':
      return event.message
    case 'agent_end':
      return `${event.agent_id} ${event.status === 'success' ? 'completed' : 'failed'}`
    case 'agent_complete':
      return `${event.agent_id ?? 'Agent'} completed`
    case 'agent_error':
      return `${event.agent_id ?? 'Agent'} failed`
    case 'tool_call':
      return `Calling: ${event.tool_name}`
    case 'tool_result':
      return event.success
        ? `Success: ${event.tool_name}`
        : `Failed: ${event.tool_name}`
    case 'task_started':
      return `Task started: ${event.task_title}`
    case 'task_progress':
      return event.message ?? `Task progress: ${event.progress}%`
    case 'task_done':
      return event.result?.summary ? `Task done: ${event.result.summary}` : 'Task done'
    case 'task_completed':
      return 'Task completed'
    case 'task_failed':
      return `Task failed: ${event.error_message}`
    case 'task_aborted':
      return 'Task aborted'
    case 'task_retrying':
      return `Retrying task (attempt ${event.attempt}/${event.max_attempts})`
    case 'task_skipped':
      return 'Task skipped'
    case 'task_blocked':
      return 'Task blocked'
    case 'error':
      return event.message
    case 'done':
      return event.summary ?? 'Execution complete'
    case 'token_usage':
      return `Token usage: ${event.total_tokens} tokens ($${event.cost_usd.toFixed(4)})`
    case 'interview_question':
      return 'Interview question'
    case 'interview_answer':
      return 'Interview answer'
    // ProductDoc events
    case 'product_doc_generated':
      return `Product Doc generated (${event.status})`
    case 'product_doc_updated':
      return event.change_summary ?? 'Product Doc updated'
    case 'product_doc_confirmed':
      return 'Product Doc confirmed'
    case 'product_doc_outdated':
      return 'Product Doc is outdated'
    // MultiPage events
    case 'multipage_decision_made':
      return `Decision: ${event.decision} (confidence: ${Math.round(event.confidence * 100)}%)`
    case 'sitemap_proposed':
      return `Sitemap proposed (${event.pages_count} pages)`
    // Page events
    case 'page_created':
      return `Page created: ${event.title} (${event.slug})`
    case 'page_version_created':
      return `Page version created: ${event.slug} v${event.version}`
    case 'page_preview_ready':
      return `Preview ready: ${event.slug}`
    case 'version_created':
      return 'Version created'
    case 'snapshot_created':
      return 'Snapshot created'
    case 'history_created':
      return 'History created'
    default:
      return event.type
  }
}

const getEventStatus = (event: ExecutionEvent): EventStatus => {
  switch (event.type) {
    case 'agent_start':
    case 'task_started':
    case 'task_progress':
    case 'agent_progress':
    case 'tool_call':
    case 'task_retrying':
    case 'token_usage':
      return 'in_progress'
    case 'agent_end':
      return event.status === 'success' ? 'done' : 'failed'
    case 'agent_complete':
      return 'done'
    case 'agent_error':
      return 'failed'
    case 'tool_result':
      return event.success ? 'done' : 'failed'
    case 'task_done':
    case 'task_completed':
    case 'done':
    case 'plan_created':
    case 'plan_updated':
    case 'task_skipped':
    case 'product_doc_generated':
    case 'product_doc_updated':
    case 'product_doc_confirmed':
    case 'multipage_decision_made':
    case 'sitemap_proposed':
    case 'page_created':
    case 'page_version_created':
    case 'page_preview_ready':
    case 'version_created':
    case 'snapshot_created':
    case 'history_created':
    case 'interview_question':
    case 'interview_answer':
      return 'done'
    case 'task_failed':
    case 'task_aborted':
    case 'error':
    case 'product_doc_outdated':
      return 'failed'
    case 'task_blocked':
      return 'pending'
    default:
      return 'pending'
  }
}

const getBadge = (event: ExecutionEvent): string | undefined => {
  if (isAgentEvent(event)) return 'Agent'
  if (isToolEvent(event)) return 'Tool'
  if (isPlanEvent(event)) return 'Plan'
  if (isTaskEvent(event)) return 'Task'
  if (event.type === 'error') return 'Error'
  if (event.type === 'done') return 'Summary'
  if (event.type === 'token_usage') return 'Tokens'
  if (event.type === 'interview_question') return 'Interview'
  if (event.type === 'interview_answer') return 'Interview'
  if (event.type === 'product_doc_generated') return 'Product Doc'
  if (event.type === 'product_doc_updated') return 'Product Doc'
  if (event.type === 'product_doc_confirmed') return 'Product Doc'
  if (event.type === 'product_doc_outdated') return 'Product Doc'
  if (event.type === 'multipage_decision_made') return 'Decision'
  if (event.type === 'sitemap_proposed') return 'Sitemap'
  if (event.type === 'page_created') return 'Page'
  if (event.type === 'page_version_created') return 'Page'
  if (event.type === 'page_preview_ready') return 'Preview'
  if (event.type === 'version_created') return 'Version'
  if (event.type === 'snapshot_created') return 'Snapshot'
  if (event.type === 'history_created') return 'History'
  return undefined
}

const buildDetails = (event: ExecutionEvent): ReactNode | undefined => {
  // Tool events have their own specialized display components
  if (event.type === 'tool_call') {
    return <ToolCallEventDisplay event={event as ToolCallEvent} />
  }
  if (event.type === 'tool_result') {
    return <ToolResultEventDisplay event={event as ToolResultEvent} />
  }

  // Other events use the generic JSON display
  const hasDetails =
    isAgentEvent(event) ||
    isPlanEvent(event) ||
    event.type === 'task_failed' ||
    event.type === 'task_aborted' ||
    event.type === 'task_retrying' ||
    event.type === 'task_done' ||
    event.type === 'task_completed' ||
    event.type === 'token_usage' ||
    event.type === 'multipage_decision_made' ||
    event.type === 'sitemap_proposed' ||
    event.type === 'product_doc_updated' ||
    event.type === 'page_created' ||
    event.type === 'interview_question' ||
    event.type === 'interview_answer'

  if (!hasDetails) return undefined

  return (
    <div className="rounded-md bg-muted/50 p-2">
      <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(event, null, 2)}</pre>
    </div>
  )
}

export function EventItem({ event }: EventItemProps) {
  const status = getEventStatus(event)
  const title = getEventTitle(event)
  const timestamp = formatTimestamp(event.timestamp)
  const badge = getBadge(event)
  const details = buildDetails(event)
  const progress =
    event.type === 'task_progress'
      ? event.progress
      : event.type === 'agent_progress'
        ? event.progress
        : undefined

  // Tool events have custom display - render them directly without CollapsibleEvent wrapper
  if (event.type === 'tool_call' || event.type === 'tool_result') {
    return (
      <div className="flex items-center gap-2 px-1 pb-1">
        {timestamp && (
          <span className="flex-shrink-0 text-[10px] text-muted-foreground">
            {timestamp}
          </span>
        )}
        <div className="min-w-0 flex-1">{details}</div>
      </div>
    )
  }

  return (
    <CollapsibleEvent
      title={title}
      timestamp={timestamp}
      status={status}
      badge={badge}
      details={details}
      progress={typeof progress === 'number' ? progress : undefined}
      defaultCollapsed={status === 'done'}
      isCollapsible={Boolean(details)}
    />
  )
}
