import * as React from 'react'
import type { ExecutionEvent } from '@/types/events'
import type { Plan, Task, TaskStatus } from '@/types/plan'
import type { SessionTokenSummary } from '@/types'

interface ProgressState {
  completed: number
  total: number
  percent: number
}

const normalizeTask = (task: Partial<Task> & { id: string; title: string }): Task => ({
  id: task.id,
  title: task.title,
  description: task.description,
  agent_type: task.agent_type,
  status: task.status ?? 'pending',
  progress: task.progress ?? 0,
  depends_on: task.depends_on ?? [],
  can_parallel: task.can_parallel ?? false,
  retry_count: task.retry_count ?? 0,
  error_message: task.error_message,
  summary: task.summary,
})

export function usePlan() {
  const [plan, setPlanState] = React.useState<Plan | null>(null)
  const taskIndexRef = React.useRef<Map<string, number>>(new Map())
  const [tokenUsage, setTokenUsage] = React.useState<SessionTokenSummary>({
    total: {
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
      cost_usd: 0,
    },
    by_agent: {},
  })

  const setPlan = React.useCallback((nextPlan: Plan) => {
    taskIndexRef.current = new Map(
      nextPlan.tasks.map((task, index) => [task.id, index])
    )
    setPlanState(nextPlan)
  }, [])

  const updateTaskStatus = React.useCallback(
    (taskId: string, status: TaskStatus, extra?: Partial<Task>) => {
      setPlanState((prev) => {
        if (!prev) return prev
        const index = taskIndexRef.current.get(taskId)
        if (index === undefined) return prev
        const current = prev.tasks[index]
        const nextTask = { ...current, status, ...extra }
        if (nextTask === current) return prev
        const nextTasks = [...prev.tasks]
        nextTasks[index] = nextTask
        return { ...prev, tasks: nextTasks }
      })
    },
    []
  )

  const handleTokenUsage = React.useCallback((event: ExecutionEvent) => {
    if (event.type === 'token_usage') {
      setTokenUsage((prev) => {
        const newTotal = {
          input_tokens: prev.total.input_tokens + event.input_tokens,
          output_tokens: prev.total.output_tokens + event.output_tokens,
          total_tokens: prev.total.total_tokens + event.total_tokens,
          cost_usd: prev.total.cost_usd + event.cost_usd,
        }

        const agentType = event.agent_type ?? 'unknown'
        const existingAgent = prev.by_agent[agentType] ?? {
          input_tokens: 0,
          output_tokens: 0,
          total_tokens: 0,
          cost_usd: 0,
        }

        const newAgentUsage = {
          input_tokens: existingAgent.input_tokens + event.input_tokens,
          output_tokens: existingAgent.output_tokens + event.output_tokens,
          total_tokens: existingAgent.total_tokens + event.total_tokens,
          cost_usd: existingAgent.cost_usd + event.cost_usd,
        }

        return {
          total: newTotal,
          by_agent: {
            ...prev.by_agent,
            [agentType]: newAgentUsage,
          },
        }
      })

      // Also update token usage for the specific task
      const taskId = event.task_id
      if (taskId) {
        setPlanState((prev) => {
          if (!prev) return prev
          const index = taskIndexRef.current.get(taskId)
          if (index === undefined) return prev
          const task = prev.tasks[index]
          const existing = task.token_usage ?? {
            input_tokens: 0,
            output_tokens: 0,
            total_tokens: 0,
            cost_usd: 0,
          }
          const nextTask = {
            ...task,
            token_usage: {
              input_tokens: existing.input_tokens + event.input_tokens,
              output_tokens: existing.output_tokens + event.output_tokens,
              total_tokens: existing.total_tokens + event.total_tokens,
              cost_usd: existing.cost_usd + event.cost_usd,
            },
          }
          const nextTasks = [...prev.tasks]
          nextTasks[index] = nextTask
          return { ...prev, tasks: nextTasks }
        })
      }
    } else if (event.type === 'done' && event.token_usage) {
      setTokenUsage({
        total: event.token_usage.total,
        by_agent: event.token_usage.by_agent,
      })
    }
  }, [])

  const handlePlanCreated = React.useCallback((event: ExecutionEvent) => {
    if (event.type !== 'plan_created' || !('plan' in event) || !event.plan) return
    const tasks = event.plan.tasks.map((task) =>
      normalizeTask({
        id: task.id,
        title: task.title,
        description: task.description,
        agent_type: task.agent_type,
        status: task.status ?? 'pending',
        progress: 0,
        depends_on: task.depends_on ?? [],
        can_parallel: task.can_parallel,
      })
    )

    taskIndexRef.current = new Map(
      tasks.map((task, index) => [task.id, index])
    )
    setPlanState({
      id: event.plan.id,
      goal: event.plan.goal,
      tasks,
      status: 'in_progress',
    })
  }, [])

  const handleEvent = React.useCallback(
    (event: ExecutionEvent) => {
      handleTokenUsage(event)

      switch (event.type) {
        case 'plan_created':
          handlePlanCreated(event)
          break
        case 'plan_updated':
          setPlanState((prev) => {
            if (!prev) return prev
            const nextTasks = [...prev.tasks]
            let changed = false
            for (const change of event.changes) {
              const index = taskIndexRef.current.get(change.task_id)
              if (index === undefined) continue
              const task = nextTasks[index]
              const key = change.field as keyof Task
              const nextValue = change.new_value as Task[keyof Task]
              if (task[key] === nextValue) continue
              nextTasks[index] = { ...task, [key]: nextValue }
              changed = true
            }
            if (!changed) return prev
            return { ...prev, tasks: nextTasks }
          })
          break
        case 'task_started':
          updateTaskStatus(event.task_id, 'in_progress', { progress: 0 })
          break
        case 'task_progress':
          updateTaskStatus(event.task_id, 'in_progress', {
            progress: event.progress,
          })
          break
        case 'task_done':
          updateTaskStatus(event.task_id, 'done', {
            progress: 100,
            summary: event.result?.summary,
          })
          break
        case 'task_completed':
          updateTaskStatus(event.task_id, 'done', {
            progress: 100,
            summary: event.result?.summary,
          })
          break
        case 'task_failed':
          updateTaskStatus(event.task_id, 'failed', {
            error_message: event.error_message,
            retry_count: event.retry_count,
          })
          break
        case 'task_aborted':
          updateTaskStatus(event.task_id, 'aborted', { progress: 100 })
          break
        case 'task_retrying':
          updateTaskStatus(event.task_id, 'retrying', {
            retry_count: event.attempt,
          })
          break
        case 'task_skipped':
          updateTaskStatus(event.task_id, 'skipped', { progress: 100 })
          break
        case 'task_blocked':
          updateTaskStatus(event.task_id, 'blocked')
          break
        case 'done':
          setPlanState((prev) => (prev ? { ...prev, status: 'done' } : prev))
          break
        case 'error':
          setPlanState((prev) => (prev ? { ...prev, status: 'failed' } : prev))
          break
        default:
          break
      }
    },
    [handlePlanCreated, updateTaskStatus, handleTokenUsage]
  )

  const progress: ProgressState = React.useMemo(() => {
    if (!plan) return { completed: 0, total: 0, percent: 0 }
    const total = plan.tasks.length
    const completed = plan.tasks.filter((task) =>
      ['done', 'skipped', 'failed', 'aborted', 'timeout'].includes(task.status)
    ).length
    const percent = total === 0 ? 0 : Math.round((completed / total) * 100)
    return { completed, total, percent }
  }, [plan])

  return {
    plan,
    setPlan,
    updateTaskStatus,
    handleEvent,
    progress,
    tokenUsage,
  }
}
