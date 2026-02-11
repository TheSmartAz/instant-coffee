import * as React from 'react'
import { api } from '@/api/client'
import type { Thread } from '@/types'

type ApiThread = {
  id: string
  session_id: string
  title?: string | null
  created_at?: string
  updated_at?: string
  message_count?: number
}

const mapThread = (t: ApiThread): Thread => ({
  id: t.id,
  session_id: t.session_id,
  title: t.title ?? null,
  created_at: t.created_at ?? new Date().toISOString(),
  updated_at: t.updated_at ?? new Date().toISOString(),
  message_count: t.message_count ?? 0,
})

const THREAD_STORAGE_KEY = (sid: string) =>
  `instant-coffee:active-thread:${sid}`

const readStoredThreadId = (sessionId?: string): string | null => {
  if (!sessionId) return null
  try {
    return localStorage.getItem(THREAD_STORAGE_KEY(sessionId))
  } catch {
    return null
  }
}

const writeStoredThreadId = (sessionId: string, threadId: string | null) => {
  try {
    if (threadId) {
      localStorage.setItem(THREAD_STORAGE_KEY(sessionId), threadId)
    } else {
      localStorage.removeItem(THREAD_STORAGE_KEY(sessionId))
    }
  } catch {
    // ignore storage errors
  }
}

export function useThreads(sessionId?: string) {
  const [threads, setThreads] = React.useState<Thread[]>([])
  const [activeThreadId, setActiveThreadId] = React.useState<
    string | null
  >(() => readStoredThreadId(sessionId))
  const [isLoading, setIsLoading] = React.useState(false)
  const activeThreadIdRef = React.useRef(activeThreadId)

  // Keep ref in sync with state
  React.useEffect(() => {
    activeThreadIdRef.current = activeThreadId
  }, [activeThreadId])

  // Persist activeThreadId to localStorage whenever it changes
  React.useEffect(() => {
    if (sessionId && activeThreadId) {
      writeStoredThreadId(sessionId, activeThreadId)
    }
  }, [sessionId, activeThreadId])

  const refresh = React.useCallback(async () => {
    if (!sessionId) return
    setIsLoading(true)
    try {
      const response = await api.sessions.threads(sessionId)
      const list = (
        response as { threads?: ApiThread[] }
      )?.threads ?? []
      const mapped = list.map(mapThread)
      setThreads(mapped)
      const currentActiveId = activeThreadIdRef.current
      if (
        mapped.length > 0 &&
        !mapped.some((t) => t.id === currentActiveId)
      ) {
        // Prefer the stored thread ID if it exists in the list
        const stored = readStoredThreadId(sessionId)
        const restoredThread =
          stored && mapped.some((t) => t.id === stored) ? stored : mapped[0].id
        setActiveThreadId(restoredThread)
      }
    } catch {
      // ignore
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

  React.useEffect(() => {
    if (!sessionId) {
      setThreads([])
      setActiveThreadId(null)
      return
    }
    // Read stored thread for the new session
    const stored = readStoredThreadId(sessionId)
    if (stored) {
      setActiveThreadId(stored)
    } else {
      setActiveThreadId(null)
    }
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  const createThread = React.useCallback(
    async (title?: string) => {
      if (!sessionId) return null
      try {
        const response = await api.sessions.createThread(
          sessionId,
          title,
        )
        const thread = mapThread(response as ApiThread)
        setThreads((prev) => [...prev, thread])
        setActiveThreadId(thread.id)
        return thread
      } catch {
        return null
      }
    },
    [sessionId],
  )

  const deleteThread = React.useCallback(
    async (threadId: string) => {
      if (!sessionId) return false
      try {
        await api.sessions.deleteThread(sessionId, threadId)
        setThreads((prev) => {
          const next = prev.filter((t) => t.id !== threadId)
          if (activeThreadId === threadId && next.length > 0) {
            setActiveThreadId(next[0].id)
          }
          return next
        })
        return true
      } catch {
        return false
      }
    },
    [sessionId, activeThreadId],
  )

  const switchThread = React.useCallback(
    (threadId: string) => {
      if (threads.some((t) => t.id === threadId)) {
        setActiveThreadId(threadId)
      }
    },
    [threads],
  )

  const updateThreadTitle = React.useCallback(
    async (threadId: string, title: string) => {
      if (!sessionId) return
      try {
        await api.sessions.updateThread(sessionId, threadId, { title })
        setThreads((prev) =>
          prev.map((t) =>
            t.id === threadId ? { ...t, title } : t,
          ),
        )
      } catch {
        // ignore
      }
    },
    [sessionId],
  )

  return {
    threads,
    activeThreadId,
    isLoading,
    refresh,
    createThread,
    deleteThread,
    switchThread,
    setActiveThreadId,
    updateThreadTitle,
  }
}
