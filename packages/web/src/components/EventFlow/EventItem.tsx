import * as React from 'react'
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

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value && typeof value === 'object' && !Array.isArray(value))

const getNestedPayload = (event: ExecutionEvent): Record<string, unknown> => {
  const payload = (event as { payload?: unknown }).payload
  return isRecord(payload) ? payload : {}
}

const getEventField = (event: ExecutionEvent, key: string): unknown => {
  const eventRecord = event as unknown as Record<string, unknown>
  if (eventRecord[key] !== undefined) return eventRecord[key]
  return getNestedPayload(event)[key]
}

const getStringField = (event: ExecutionEvent, key: string): string | undefined => {
  const value = getEventField(event, key)
  return typeof value === 'string' && value.trim() ? value : undefined
}

const getNumberField = (event: ExecutionEvent, key: string): number | undefined => {
  const value = getEventField(event, key)
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : undefined
  }
  return undefined
}

const truncateText = (value: string, max = 96) =>
  value.length <= max ? value : `${value.slice(0, max)}...`

const PHASE_LABELS: Record<string, string> = {
  plan: 'Plan',
  implement: 'Implement',
  build: 'Build',
  review: 'Review',
  fix: 'Fix',
  done: 'Done',
}

const formatPhase = (phase?: string) => {
  if (!phase) return undefined
  return PHASE_LABELS[phase] ?? phase.replace(/_/g, ' ')
}

const withPhase = (event: ExecutionEvent, title: string, omitPhase?: string) => {
  const phase = getStringField(event, 'phase')
  if (!phase || phase === omitPhase) return title
  return `${title}: ${formatPhase(phase)}`
}

const formatReviewSummary = (summary: unknown): string | undefined => {
  if (typeof summary === 'string' && summary.trim()) return summary
  if (!isRecord(summary)) return undefined

  const parts: string[] = []
  const errorCount = summary.error_count
  const warningCount = summary.warning_count
  const buildStatus = summary.build_status
  const generatedPages = summary.generated_pages

  if (typeof errorCount === 'number') parts.push(`${errorCount} errors`)
  if (typeof warningCount === 'number') parts.push(`${warningCount} warnings`)
  if (typeof buildStatus === 'string' && buildStatus) parts.push(`build ${buildStatus}`)
  if (Array.isArray(generatedPages)) parts.push(`${generatedPages.length} pages`)

  if (parts.length) return parts.join(', ')
  return JSON.stringify(summary)
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
    case 'build_start':
      return 'Build started'
    case 'build_progress': {
      const message = getStringField(event, 'message') ?? getStringField(event, 'step')
      return message ? `Build: ${truncateText(message)}` : 'Build progress'
    }
    case 'build_complete': {
      const pages = getEventField(event, 'pages')
      return Array.isArray(pages) ? `Build complete (${pages.length} pages)` : 'Build complete'
    }
    case 'build_failed': {
      const error = getStringField(event, 'error')
      return error ? `Build failed: ${truncateText(error)}` : 'Build failed'
    }
    case 'run_created':
      return withPhase(event, 'Run created')
    case 'run_started':
      return withPhase(event, 'Run started')
    case 'run_waiting_input':
      return withPhase(event, 'Run waiting input')
    case 'run_resumed':
      return withPhase(event, 'Run resumed')
    case 'run_completed':
      return withPhase(event, 'Run completed')
    case 'run_failed':
      return getStringField(event, 'error') ?? withPhase(event, 'Run failed')
    case 'run_cancelled':
      return withPhase(event, 'Run cancelled')
    case 'verify_start':
      return withPhase(event, 'Review started', 'review')
    case 'verify_pass': {
      const summary = formatReviewSummary(getEventField(event, 'summary'))
      return summary
        ? `${withPhase(event, 'Review passed', 'review')} (${summary})`
        : withPhase(event, 'Review passed', 'review')
    }
    case 'verify_fail': {
      const summary = formatReviewSummary(getEventField(event, 'summary'))
      return summary
        ? `${withPhase(event, 'Review failed', 'review')} (${summary})`
        : withPhase(event, 'Review failed', 'review')
    }
    case 'tool_policy_blocked':
      return getStringField(event, 'message') ?? 'Tool policy blocked'
    case 'tool_policy_warn':
      return getStringField(event, 'message') ?? 'Tool policy warning'
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
    case 'build_start':
    case 'build_progress':
    case 'run_started':
    case 'run_resumed':
    case 'verify_start':
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
    case 'run_created':
    case 'run_completed':
    case 'build_complete':
    case 'verify_pass':
    case 'tool_policy_warn':
      return 'done'
    case 'task_failed':
    case 'task_aborted':
    case 'error':
    case 'product_doc_outdated':
    case 'run_failed':
    case 'run_cancelled':
    case 'build_failed':
    case 'verify_fail':
    case 'tool_policy_blocked':
      return 'failed'
    case 'task_blocked':
    case 'run_waiting_input':
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
  if (event.type.startsWith('build_')) return 'Build'
  if (event.type.startsWith('run_')) return 'Run'
  if (event.type.startsWith('verify_')) return 'Review'
  if (event.type.startsWith('tool_policy_')) return 'Policy'
  return undefined
}

const formatDetailValue = (key: string, value: unknown): string | undefined => {
  if (value === undefined || value === null) return undefined
  if (key === 'percent') {
    const percent = typeof value === 'number' ? value : Number(value)
    return Number.isFinite(percent) ? `${percent}%` : undefined
  }
  if (typeof value === 'string') return value.trim() ? truncateText(value, 240) : undefined
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) {
    const preview = value
      .slice(0, 4)
      .map((item) => (typeof item === 'string' ? item : JSON.stringify(item)))
      .join(', ')
    const suffix = value.length > 4 ? ` +${value.length - 4} more` : ''
    return preview ? `${preview}${suffix}` : `${value.length} items`
  }
  if (isRecord(value)) {
    return formatReviewSummary(value) ?? JSON.stringify(value)
  }
  return undefined
}

const buildWorkflowDetails = (event: ExecutionEvent): React.ReactNode | undefined => {
  const rows = [
    ['Phase', 'phase'],
    ['Status', 'status'],
    ['Step', 'step'],
    ['Message', 'message'],
    ['Error', 'error'],
    ['Tool', 'tool_name'],
    ['Reason', 'reason'],
    ['Progress', 'percent'],
    ['Pages', 'pages'],
    ['Dist path', 'dist_path'],
    ['Summary', 'summary'],
  ]
    .map(([label, key]) => {
      const value = formatDetailValue(key, getEventField(event, key))
      return value ? { label, value } : null
    })
    .filter((row): row is { label: string; value: string } => Boolean(row))

  if (rows.length === 0) return undefined

  return (
    <div className="rounded-md bg-muted/50 p-2">
      <dl className="grid gap-1 text-xs sm:grid-cols-[90px_1fr]">
        {rows.map((row) => (
          <React.Fragment key={row.label}>
            <dt className="font-medium text-muted-foreground">{row.label}</dt>
            <dd className="min-w-0 break-words text-foreground/85">{row.value}</dd>
          </React.Fragment>
        ))}
      </dl>
    </div>
  )
}

const buildDetails = (event: ExecutionEvent): React.ReactNode | undefined => {
  // Tool events have their own specialized display components
  if (event.type === 'tool_call') {
    return <ToolCallEventDisplay event={event as ToolCallEvent} />
  }
  if (event.type === 'tool_result') {
    return <ToolResultEventDisplay event={event as ToolResultEvent} />
  }
  if (
    event.type.startsWith('build_') ||
    event.type.startsWith('run_') ||
    event.type.startsWith('verify_') ||
    event.type.startsWith('tool_policy_')
  ) {
    return buildWorkflowDetails(event)
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

export const EventItem = React.memo(function EventItem({ event }: EventItemProps) {
  const status = getEventStatus(event)
  const title = getEventTitle(event)
  const timestamp = formatTimestamp(event.timestamp)
  const badge = getBadge(event)
  const details = buildDetails(event)
  const progress =
    event.type === 'task_progress'
      ? event.progress
      : event.type === 'agent_progress'
        ? getNumberField(event, 'progress')
        : event.type === 'build_progress'
          ? getNumberField(event, 'percent')
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
}, (prev, next) => prev.event === next.event)
