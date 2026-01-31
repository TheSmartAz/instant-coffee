export type EventType =
  | 'agent_start'
  | 'agent_progress'
  | 'agent_end'
  | 'tool_call'
  | 'tool_result'
  | 'plan_created'
  | 'plan_updated'
  | 'task_started'
  | 'task_progress'
  | 'task_done'
  | 'task_failed'
  | 'task_retrying'
  | 'task_skipped'
  | 'task_blocked'
  | 'token_usage'
  | 'error'
  | 'done'

export interface BaseEvent {
  type: EventType
  timestamp: string
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

export type ExecutionEvent =
  | AgentStartEvent
  | AgentProgressEvent
  | AgentEndEvent
  | ToolCallEvent
  | ToolResultEvent
  | PlanCreatedEvent
  | PlanUpdatedEvent
  | TaskStartedEvent
  | TaskProgressEvent
  | TaskDoneEvent
  | TaskFailedEvent
  | TaskRetryingEvent
  | TaskSkippedEvent
  | TaskBlockedEvent
  | TokenUsageEvent
  | ErrorEvent
  | DoneEvent

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
