import * as React from 'react'
import { api } from '@/api/client'
import type { ExecutionEvent, SessionEvent } from '@/types/events'

type ConnectionState = 'idle' | 'connecting' | 'open' | 'error' | 'closed'

const EXCLUDED_EVENT_TYPES = new Set(['delta', 'thinking', 'ping'])
const DEFAULT_MAX_EVENTS = 2000

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value && typeof value === 'object')

const toTimestampMs = (timestamp?: string) => {
  const parsed = Date.parse(timestamp ?? '')
  return Number.isNaN(parsed) ? Date.now() : parsed
}

const normalizePayloadEvent = (
  payload: Record<string, unknown>
): ExecutionEvent | null => {
  const rawType = payload.type
  if (typeof rawType !== 'string') return null
  if (EXCLUDED_EVENT_TYPES.has(rawType)) return null
  const timestamp =
    typeof payload.timestamp === 'string'
      ? payload.timestamp
      : new Date().toISOString()
  const timestampMs = toTimestampMs(timestamp)
  return { ...payload, type: rawType, timestamp, timestamp_ms: timestampMs } as ExecutionEvent
}

const normalizeSessionEvent = (event: SessionEvent): ExecutionEvent | null => {
  if (!event.type || EXCLUDED_EVENT_TYPES.has(event.type)) return null
  const payload = isRecord(event.payload) ? event.payload : {}
  const timestamp = event.created_at
  const base = {
    ...payload,
    type: event.type,
    timestamp,
    timestamp_ms: toTimestampMs(timestamp),
    session_id: event.session_id,
    run_id: event.run_id ?? undefined,
    event_id: event.event_id ?? undefined,
    seq: event.seq,
    source: event.source,
  } as ExecutionEvent
  return base
}

const dispatchBuildEvent = (event: ExecutionEvent) => {
  if (typeof window === 'undefined') return
  if (
    event.type === 'build_start' ||
    event.type === 'build_progress' ||
    event.type === 'build_complete' ||
    event.type === 'build_failed'
  ) {
    window.dispatchEvent(new CustomEvent('build-event', { detail: event }))
  }
}

const buildEventKey = (event: ExecutionEvent) => {
  const runId = (event as { run_id?: string }).run_id
  if (event.seq !== undefined && event.seq !== null) {
    if (runId) {
      return `run-seq:${runId}:${event.seq}`
    }
    return `seq:${event.seq}`
  }
  const timestamp = event.timestamp ?? ''
  const taskId = (event as { task_id?: string }).task_id ?? ''
  const agentId = (event as { agent_id?: string }).agent_id ?? ''
  return `event:${event.type}:${timestamp}:${taskId}:${agentId}`
}

const sortEvents = (a: ExecutionEvent, b: ExecutionEvent) => {
  const aSeq = a.seq
  const bSeq = b.seq
  if (typeof aSeq === 'number' && typeof bSeq === 'number') {
    return aSeq - bSeq
  }
  if (typeof aSeq === 'number') return -1
  if (typeof bSeq === 'number') return 1
  const aTime =
    typeof a.timestamp_ms === 'number' ? a.timestamp_ms : toTimestampMs(a.timestamp)
  const bTime =
    typeof b.timestamp_ms === 'number' ? b.timestamp_ms : toTimestampMs(b.timestamp)
  return aTime - bTime
}

const mergeEvents = (existing: ExecutionEvent[], incoming: ExecutionEvent[]) => {
  const combined = [...existing, ...incoming].sort(sortEvents)
  const seen = new Set<string>()
  const result: ExecutionEvent[] = []
  for (const event of combined) {
    const key = buildEventKey(event)
    if (seen.has(key)) continue
    seen.add(key)
    result.push(event)
  }
  return result
}

export interface UseSSEOptions {
  url: string
  sessionId?: string
  onEvent?: (event: ExecutionEvent) => void
  onError?: (error: Error) => void
  onDone?: () => void
  autoReconnect?: boolean
  reconnectDelay?: number
  maxReconnectAttempts?: number
  autoConnect?: boolean
  loadHistory?: boolean
  historyLimit?: number
  replayHistory?: boolean
  maxEvents?: number
}

export interface UseSSEReturn {
  events: ExecutionEvent[]
  isConnected: boolean
  isLoading: boolean
  isHistoryLoading: boolean
  error: Error | null
  connectionState: ConnectionState
  connect: () => void
  disconnect: () => void
  clearEvents: () => void
}

export function useSSE({
  url,
  sessionId,
  onEvent,
  onError,
  onDone,
  autoReconnect = true,
  reconnectDelay = 3000,
  maxReconnectAttempts = 10,
  autoConnect = true,
  loadHistory = true,
  historyLimit = 1000,
  replayHistory = true,
  maxEvents = DEFAULT_MAX_EVENTS,
}: UseSSEOptions): UseSSEReturn {
  const [events, setEvents] = React.useState<ExecutionEvent[]>([])
  const [isConnected, setIsConnected] = React.useState(false)
  const [isConnecting, setIsConnecting] = React.useState(false)
  const [isHistoryLoading, setIsHistoryLoading] = React.useState(false)
  const [error, setError] = React.useState<Error | null>(null)
  const [connectionState, setConnectionState] =
    React.useState<ConnectionState>('idle')

  const eventSourceRef = React.useRef<EventSource | null>(null)
  const reconnectTimeoutRef = React.useRef<number | null>(null)
  const reconnectAttemptRef = React.useRef(0)
  const seenEventKeysRef = React.useRef<Set<string>>(new Set())
  const pendingEventsRef = React.useRef<ExecutionEvent[]>([])
  const flushHandleRef = React.useRef<number | null>(null)
  const flushUsesRafRef = React.useRef(false)
  const onEventRef = React.useRef<typeof onEvent>(onEvent)
  const onErrorRef = React.useRef<typeof onError>(onError)
  const onDoneRef = React.useRef<typeof onDone>(onDone)
  const maxEventsResolved = Math.max(50, maxEvents)

  React.useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  React.useEffect(() => {
    onErrorRef.current = onError
  }, [onError])

  React.useEffect(() => {
    onDoneRef.current = onDone
  }, [onDone])

  const clampEvents = React.useCallback(
    (items: ExecutionEvent[]) => {
      if (items.length <= maxEventsResolved) return items
      const trimmed = items.slice(-maxEventsResolved)
      seenEventKeysRef.current = new Set(
        trimmed.map((event) => buildEventKey(event))
      )
      return trimmed
    },
    [maxEventsResolved]
  )

  const cancelFlush = React.useCallback(() => {
    const handle = flushHandleRef.current
    if (handle === null) return
    if (flushUsesRafRef.current && typeof window !== 'undefined') {
      window.cancelAnimationFrame(handle)
    } else {
      window.clearTimeout(handle)
    }
    flushHandleRef.current = null
    flushUsesRafRef.current = false
  }, [])

  const scheduleFlush = React.useCallback(() => {
    if (flushHandleRef.current !== null) return
    const useRaf =
      typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function'
    flushUsesRafRef.current = useRaf
    const handle = useRaf
      ? window.requestAnimationFrame(() => {
          flushHandleRef.current = null
          const pending = pendingEventsRef.current
          if (pending.length === 0) return
          pendingEventsRef.current = []
          setEvents((prev) => clampEvents([...prev, ...pending]))
        })
      : window.setTimeout(() => {
          flushHandleRef.current = null
          const pending = pendingEventsRef.current
          if (pending.length === 0) return
          pendingEventsRef.current = []
          setEvents((prev) => clampEvents([...prev, ...pending]))
        }, 16)
    flushHandleRef.current = handle
  }, [clampEvents])

  const clearReconnect = React.useCallback(() => {
    if (reconnectTimeoutRef.current) {
      window.clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
  }, [])

  const disconnect = React.useCallback(() => {
    clearReconnect()
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setIsConnected(false)
    setIsConnecting(false)
    setConnectionState('closed')
  }, [clearReconnect])

  const connect = React.useCallback(() => {
    clearReconnect()
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    setIsConnecting(true)
    setError(null)
    setConnectionState('connecting')

    const eventSource = new EventSource(url)
    eventSourceRef.current = eventSource

    eventSource.onopen = () => {
      reconnectAttemptRef.current = 0
      setIsConnected(true)
      setIsConnecting(false)
      setConnectionState('open')
    }

    eventSource.onmessage = (event) => {
      if (event.data === '[DONE]') {
        clearReconnect()
        setIsConnected(false)
        setConnectionState('closed')
        eventSource.close()
        onDoneRef.current?.()
        return
      }

      try {
        const parsed = JSON.parse(event.data)
        if (!isRecord(parsed)) return
        const normalized = normalizePayloadEvent(parsed)
        if (!normalized) return
        const key = buildEventKey(normalized)
        if (seenEventKeysRef.current.has(key)) return
        seenEventKeysRef.current.add(key)
        pendingEventsRef.current.push(normalized)
        scheduleFlush()
        onEventRef.current?.(normalized)
        dispatchBuildEvent(normalized)
        if (normalized.type === 'done') {
          onDoneRef.current?.()
        }
      } catch (parseError) {
        const err =
          parseError instanceof Error
            ? parseError
            : new Error('Failed to parse SSE event')
        setError(err)
        onErrorRef.current?.(err)
        eventSource.close()
        eventSourceRef.current = null
        setIsConnected(false)
        setConnectionState('error')
      }
    }

    eventSource.onerror = () => {
      const err = new Error('SSE connection error')
      setIsConnected(false)
      setIsConnecting(false)
      setConnectionState('error')
      setError(err)
      onErrorRef.current?.(err)
      eventSource.close()

      if (autoReconnect && reconnectAttemptRef.current < maxReconnectAttempts) {
        const attempt = reconnectAttemptRef.current
        reconnectAttemptRef.current = attempt + 1
        const delay = Math.min(reconnectDelay * Math.pow(2, attempt), 30000)
        clearReconnect()
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect()
        }, delay)
      }
    }
  }, [autoReconnect, clearReconnect, maxReconnectAttempts, reconnectDelay, url, scheduleFlush])

  const clearEvents = React.useCallback(() => {
    cancelFlush()
    pendingEventsRef.current = []
    setEvents([])
    seenEventKeysRef.current = new Set()
  }, [cancelFlush])

  React.useEffect(() => {
    if (!sessionId || !loadHistory) {
      setEvents([])
      setIsHistoryLoading(false)
      return
    }
    let active = true
    const fetchHistory = async () => {
      setIsHistoryLoading(true)
      try {
        const accumulated: SessionEvent[] = []
        let sinceSeq: number | undefined = undefined
        let hasMore = true
        let page = 0
        const requestLimit = Math.min(historyLimit, maxEventsResolved)
        while (hasMore && page < 5 && accumulated.length < maxEventsResolved) {
          const response = await api.events.getSessionEvents(
            sessionId,
            sinceSeq,
            requestLimit
          )
          const payload = response as {
            events?: SessionEvent[]
            has_more?: boolean
            last_seq?: number
          }
          const batch = payload.events ?? []
          accumulated.push(...batch)
          hasMore = Boolean(payload.has_more)
          sinceSeq = payload.last_seq
          page += 1
          if (batch.length === 0) break
        }
        if (!active) return
        const rawEvents = accumulated
        const normalized = rawEvents
          .map((event) => normalizeSessionEvent(event))
          .filter(Boolean) as ExecutionEvent[]
        normalized.sort(sortEvents)
        const trimmed = normalized.length > maxEventsResolved
          ? normalized.slice(-maxEventsResolved)
          : normalized
        setEvents((prev) => {
          const merged = mergeEvents(prev, trimmed)
          const capped = clampEvents(merged)
          seenEventKeysRef.current = new Set(
            capped.map((event) => buildEventKey(event))
          )
          return capped
        })
        if (replayHistory && onEventRef.current) {
          trimmed.forEach((event) => {
            onEventRef.current?.(event)
            dispatchBuildEvent(event)
          })
        }
      } catch (err) {
        if (!active) return
        const errorValue =
          err instanceof Error ? err : new Error('Failed to load historical events')
        setError(errorValue)
        onErrorRef.current?.(errorValue)
      } finally {
        if (active) setIsHistoryLoading(false)
      }
    }

    fetchHistory()
    return () => {
      active = false
    }
  }, [historyLimit, loadHistory, replayHistory, sessionId, maxEventsResolved, clampEvents])

  React.useEffect(() => {
    if (!autoConnect || !url) return
    connect()
    return () => {
      cancelFlush()
      disconnect()
    }
  }, [autoConnect, cancelFlush, connect, disconnect, url])

  React.useEffect(() => {
    cancelFlush()
    pendingEventsRef.current = []
    setEvents([])
    seenEventKeysRef.current = new Set()
  }, [sessionId, cancelFlush])

  return {
    events,
    isConnected,
    isLoading: isConnecting || isHistoryLoading,
    isHistoryLoading,
    error,
    connectionState,
    connect,
    disconnect,
    clearEvents,
  }
}
