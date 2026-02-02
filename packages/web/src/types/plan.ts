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

export interface TaskTokenUsage {
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cost_usd: number
}

export interface Task {
  id: string
  title: string
  description?: string
  agent_type?: string
  status: TaskStatus
  progress: number
  depends_on: string[]
  can_parallel: boolean
  retry_count: number
  error_message?: string
  summary?: string
  token_usage?: TaskTokenUsage
}

export interface Plan {
  id: string
  goal: string
  tasks: Task[]
  status: 'pending' | 'in_progress' | 'done' | 'failed' | 'aborted'
}
