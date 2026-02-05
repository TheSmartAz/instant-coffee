export type EventType =
  | 'agent_start'
  | 'agent_progress'
  | 'agent_end'
  | 'agent_complete'
  | 'agent_error'
  | 'tool_call'
  | 'tool_result'
  | 'page_created'
  | 'page_version_created'
  | 'page_preview_ready'
  | 'aesthetic_score'
  | 'plan_created'
  | 'plan_updated'
  | 'task_started'
  | 'task_progress'
  | 'task_done'
  | 'task_failed'
  | 'task_retrying'
  | 'task_skipped'
  | 'task_blocked'
  | 'task_completed'
  | 'task_aborted'
  | 'token_usage'
  | 'error'
  | 'done'
  | 'interview_question'
  | 'interview_answer'
  | 'multipage_decision_made'
  | 'sitemap_proposed'
  | 'product_doc_generated'
  | 'product_doc_updated'
  | 'product_doc_confirmed'
  | 'product_doc_outdated'
  | 'version_created'
  | 'snapshot_created'
  | 'history_created'

export type EventSource = 'session' | 'plan' | 'task'

export interface BaseEvent {
  type: EventType
  timestamp: string
  session_id?: string
  seq?: number
  source?: EventSource
}

export interface AgentStartEvent extends BaseEvent {
  type: 'agent_start'
  task_id?: string
  agent_id: string
  agent_type: string
  agent_instance?: number
}

export interface AgentProgressEvent extends BaseEvent {
  type: 'agent_progress'
  task_id?: string
  agent_id: string
  message: string
  progress?: number
}

export interface AgentEndEvent extends BaseEvent {
  type: 'agent_end'
  task_id?: string
  agent_id: string
  status: 'success' | 'failed'
  summary?: string
}

export interface AgentCompleteEvent extends BaseEvent {
  type: 'agent_complete'
  task_id?: string
  agent_id?: string
  agent_type?: string
  status?: 'success' | 'failed'
  summary?: string
}

export interface AgentErrorEvent extends BaseEvent {
  type: 'agent_error'
  task_id?: string
  agent_id?: string
  message?: string
  details?: string
}

export interface ToolCallEvent extends BaseEvent {
  type: 'tool_call'
  task_id?: string
  agent_id: string
  tool_name: string
  tool_input?: Record<string, unknown>
}

export interface ToolResultEvent extends BaseEvent {
  type: 'tool_result'
  task_id?: string
  agent_id: string
  tool_name: string
  success: boolean
  tool_output?: Record<string, unknown>
  error?: string
}

export type TaskStatus =
  | 'pending'
  | 'in_progress'
  | 'done'
  | 'failed'
  | 'aborted'
  | 'timeout'
  | 'blocked'
  | 'skipped'
  | 'retrying'

export interface PlanTaskSnapshot {
  id: string
  title: string
  description?: string
  depends_on?: string[]
  can_parallel: boolean
  status: TaskStatus
  agent_type?: string
}

export interface PlanCreatedEvent extends BaseEvent {
  type: 'plan_created'
  plan?: {
    id: string
    goal: string
    tasks: PlanTaskSnapshot[]
  }
}

export interface PlanUpdatedEvent extends BaseEvent {
  type: 'plan_updated'
  plan_id: string
  changes: Array<{
    task_id: string
    field: string
    old_value: unknown
    new_value: unknown
  }>
}

export interface TaskStartedEvent extends BaseEvent {
  type: 'task_started'
  task_id: string
  task_title: string
}

export interface TaskProgressEvent extends BaseEvent {
  type: 'task_progress'
  task_id: string
  progress: number
  message?: string
}

export interface TaskDoneEvent extends BaseEvent {
  type: 'task_done'
  task_id: string
  result?: {
    output_file?: string
    preview_url?: string
    summary?: string
  }
}

export interface TaskCompletedEvent extends BaseEvent {
  type: 'task_completed'
  task_id: string
  result?: {
    output_file?: string
    preview_url?: string
    summary?: string
  }
}

export interface TaskFailedEvent extends BaseEvent {
  type: 'task_failed'
  task_id: string
  error_type: 'temporary' | 'logic' | 'dependency'
  error_message: string
  retry_count: number
  max_retries: number
  available_actions: Array<'retry' | 'skip' | 'modify' | 'abort'>
  blocked_tasks: string[]
}

export interface TaskAbortedEvent extends BaseEvent {
  type: 'task_aborted'
  task_id: string
  reason?: string
  message?: string
}

export interface TaskRetryingEvent extends BaseEvent {
  type: 'task_retrying'
  task_id: string
  attempt: number
  max_attempts: number
  next_retry_in: number
}

export interface TaskSkippedEvent extends BaseEvent {
  type: 'task_skipped'
  task_id: string
  reason?: string
}

export interface TaskBlockedEvent extends BaseEvent {
  type: 'task_blocked'
  task_id: string
  blocked_by?: string[]
  message?: string
}

export interface PageCreatedEvent extends BaseEvent {
  type: 'page_created'
  page_id: string
  slug: string
  title: string
}

export interface PageVersionCreatedEvent extends BaseEvent {
  type: 'page_version_created'
  page_id: string
  slug: string
  version: number
}

export interface PagePreviewReadyEvent extends BaseEvent {
  type: 'page_preview_ready'
  page_id: string
  slug: string
  preview_url?: string | null
}

export interface AestheticScoreEvent extends BaseEvent {
  type: 'aesthetic_score'
  page_id: string
  slug?: string
  score: Record<string, unknown>
  attempts?: Array<Record<string, unknown>>
}

export interface ErrorEvent extends BaseEvent {
  type: 'error'
  message: string
  details?: string
}

export interface TokenUsageEvent extends BaseEvent {
  type: 'token_usage'
  task_id?: string
  agent_type?: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cost_usd: number
}

export interface DoneEvent extends BaseEvent {
  type: 'done'
  summary?: string
  token_usage?: {
    total: {
      input_tokens: number
      output_tokens: number
      total_tokens: number
      cost_usd: number
    }
    by_agent: Record<string, { input_tokens: number; output_tokens: number; total_tokens: number; cost_usd: number }>
  }
}

export interface InterviewQuestionEvent extends BaseEvent {
  type: 'interview_question'
  batch_id?: string
  message?: string
  questions?: unknown[]
}

export interface InterviewAnswerEvent extends BaseEvent {
  type: 'interview_answer'
  batch_id?: string
  action?: string
  answers?: unknown[]
}

export interface VersionCreatedEvent extends BaseEvent {
  type: 'version_created'
  version_id?: string
  version?: number
  description?: string
}

export interface SnapshotCreatedEvent extends BaseEvent {
  type: 'snapshot_created'
  snapshot_id?: string
  snapshot_number?: number
}

export interface HistoryCreatedEvent extends BaseEvent {
  type: 'history_created'
  history_id?: string
  version?: number
}

export interface MultiPageDecisionEvent extends BaseEvent {
  type: 'multipage_decision_made'
  decision: string
  confidence: number
  reasons?: string[]
  suggested_pages?: Array<Record<string, unknown>> | null
  risk?: string | null
}

export interface SitemapProposedEvent extends BaseEvent {
  type: 'sitemap_proposed'
  pages_count: number
  sitemap?: Record<string, unknown> | null
}

export interface ProductDocGeneratedEvent extends BaseEvent {
  type: 'product_doc_generated'
  session_id?: string
  doc_id: string
  status: string
}

export interface ProductDocUpdatedEvent extends BaseEvent {
  type: 'product_doc_updated'
  session_id?: string
  doc_id: string
  change_summary?: string
}

export interface ProductDocConfirmedEvent extends BaseEvent {
  type: 'product_doc_confirmed'
  session_id?: string
  doc_id: string
}

export interface ProductDocOutdatedEvent extends BaseEvent {
  type: 'product_doc_outdated'
  session_id?: string
  doc_id: string
}

export interface SessionEvent {
  id: number
  session_id: string
  seq: number
  type: string
  payload: Record<string, unknown> | null
  source: EventSource
  created_at: string
}

export interface SessionEventsResponse {
  events: SessionEvent[]
  last_seq: number
  has_more: boolean
}

export type ExecutionEvent =
  | AgentStartEvent
  | AgentProgressEvent
  | AgentEndEvent
  | AgentCompleteEvent
  | AgentErrorEvent
  | ToolCallEvent
  | ToolResultEvent
  | PageCreatedEvent
  | PageVersionCreatedEvent
  | PagePreviewReadyEvent
  | AestheticScoreEvent
  | PlanCreatedEvent
  | PlanUpdatedEvent
  | TaskStartedEvent
  | TaskProgressEvent
  | TaskDoneEvent
  | TaskCompletedEvent
  | TaskFailedEvent
  | TaskAbortedEvent
  | TaskRetryingEvent
  | TaskSkippedEvent
  | TaskBlockedEvent
  | TokenUsageEvent
  | ErrorEvent
  | DoneEvent
  | InterviewQuestionEvent
  | InterviewAnswerEvent
  | MultiPageDecisionEvent
  | SitemapProposedEvent
  | ProductDocGeneratedEvent
  | ProductDocUpdatedEvent
  | ProductDocConfirmedEvent
  | ProductDocOutdatedEvent
  | VersionCreatedEvent
  | SnapshotCreatedEvent
  | HistoryCreatedEvent

export function isAgentEvent(
  event: ExecutionEvent
): event is AgentStartEvent | AgentProgressEvent | AgentEndEvent {
  return event.type.startsWith('agent_')
}

export function isTaskEvent(
  event: ExecutionEvent
): event is
  | TaskStartedEvent
  | TaskProgressEvent
  | TaskDoneEvent
  | TaskFailedEvent
  | TaskRetryingEvent
  | TaskSkippedEvent
  | TaskBlockedEvent {
  return event.type.startsWith('task_')
}

export function isToolEvent(
  event: ExecutionEvent
): event is ToolCallEvent | ToolResultEvent {
  return event.type.startsWith('tool_')
}

export function isPlanEvent(
  event: ExecutionEvent
): event is PlanCreatedEvent | PlanUpdatedEvent {
  return event.type.startsWith('plan_')
}
