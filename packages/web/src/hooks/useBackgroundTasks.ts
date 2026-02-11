import * as React from 'react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface BackgroundTask {
  id: string
  command: string
  status: 'starting' | 'running' | 'stopped' | 'failed'
  pid: number | null
  exit_code: number | null
  created_at: string
  output_lines: number
  output_preview: string[]
}

export interface UseBackgroundTasksReturn {
  tasks: BackgroundTask[]
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
  stopTask: (taskId: string) => Promise<void>
  getTaskOutput: (taskId: string, since?: number) => Promise<BackgroundTaskOutputResponse | null>
}

export interface BackgroundTaskOutputResponse {
  task_id?: string
  status?: string
  output: string
  output_lines: number
  error?: string
}

/**
 * Hook to fetch and manage background tasks for a session.
 */
export function useBackgroundTasks(sessionId: string | undefined): UseBackgroundTasksReturn {
  const [tasks, setTasks] = React.useState<BackgroundTask[]>([])
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const refresh = React.useCallback(async () => {
    if (!sessionId) return
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/background-tasks/${sessionId}`)
      if (!res.ok) throw new Error('Failed to fetch background tasks')
      const result = await res.json()
      setTasks(result.tasks || [])
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch background tasks'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

  const stopTask = React.useCallback(async (taskId: string) => {
    if (!sessionId) throw new Error('Session ID is required')
    await fetch(
      `${API_BASE}/api/background-tasks/${sessionId}/${taskId}/stop`,
      { method: 'POST' }
    )
    // Refresh after stopping
    refresh()
  }, [sessionId, refresh])

  const getTaskOutput = React.useCallback(async (taskId: string, since?: number) => {
    if (!sessionId) return null
    const response = await fetch(
      `${API_BASE}/api/background-tasks/${sessionId}/${taskId}/output${since ? `?since=${since}` : ''}`
    )
    if (!response.ok) throw new Error('Failed to fetch task output')
    return response.json() as Promise<BackgroundTaskOutputResponse>
  }, [sessionId])

  React.useEffect(() => {
    if (!sessionId) {
      setTasks([])
      setError(null)
      return
    }

    // Initial load
    refresh()

    // Poll every 5 seconds (reduced from 2s since SSE events trigger immediate refresh)
    const interval = setInterval(() => {
      refresh()
    }, 5000)

    // Listen for SSE-dispatched bg_task events for immediate refresh
    const handleBgTaskEvent = () => { refresh() }
    window.addEventListener('bg-task-event', handleBgTaskEvent)

    return () => {
      clearInterval(interval)
      window.removeEventListener('bg-task-event', handleBgTaskEvent)
    }
  }, [sessionId, refresh])

  return {
    tasks,
    isLoading,
    error,
    refresh,
    stopTask,
    getTaskOutput,
  }
}
