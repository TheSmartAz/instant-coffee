import * as React from 'react'
import type { ExecutionEvent } from '@/types/events'

type ConnectionState = 'idle' | 'connecting' | 'open' | 'error' | 'closed'

export interface UseSSEOptions {
  url: string
  onEvent?: (event: ExecutionEvent) => void
  onError?: (error: Error) => void
  onDone?: () => void
  autoReconnect?: boolean
  reconnectDelay?: number
  autoConnect?: boolean
}

export interface UseSSEReturn {
  events: ExecutionEvent[]
  isConnected: boolean
  isLoading: boolean
  error: Error | null
  connectionState: ConnectionState
  connect: () => void
  disconnect: () => void
  clearEvents: () => void
}

export function useSSE({
  url,
  onEvent,
  onError,
  onDone,
  autoReconnect = true,
  reconnectDelay = 3000,
  autoConnect = true,
}: UseSSEOptions): UseSSEReturn {
  const [events, setEvents] = React.useState<ExecutionEvent[]>([])
  const [isConnected, setIsConnected] = React.useState(false)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<Error | null>(null)
  const [connectionState, setConnectionState] =
    React.useState<ConnectionState>('idle')

  const eventSourceRef = React.useRef<EventSource | null>(null)
  const reconnectTimeoutRef = React.useRef<number | null>(null)

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
    setConnectionState('closed')
  }, [clearReconnect])

  const connect = React.useCallback(() => {
    clearReconnect()
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    setIsLoading(true)
    setError(null)
    setConnectionState('connecting')

    const eventSource = new EventSource(url)
    eventSourceRef.current = eventSource

    eventSource.onopen = () => {
      setIsConnected(true)
      setIsLoading(false)
      setConnectionState('open')
    }

    eventSource.onmessage = (event) => {
      if (event.data === '[DONE]') {
        setIsConnected(false)
        setConnectionState('closed')
        eventSource.close()
        onDone?.()
        return
      }

      try {
        const parsed = JSON.parse(event.data) as ExecutionEvent
        setEvents((prev) => [...prev, parsed])
        onEvent?.(parsed)
        if (parsed.type === 'done') {
          onDone?.()
        }
      } catch (parseError) {
        const err =
          parseError instanceof Error
            ? parseError
            : new Error('Failed to parse SSE event')
        setError(err)
        onError?.(err)
      }
    }

    eventSource.onerror = () => {
      const err = new Error('SSE connection error')
      setIsConnected(false)
      setIsLoading(false)
      setConnectionState('error')
      setError(err)
      onError?.(err)
      eventSource.close()

      if (autoReconnect) {
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect()
        }, reconnectDelay)
      }
    }
  }, [autoReconnect, clearReconnect, onDone, onError, onEvent, reconnectDelay, url])

  const clearEvents = React.useCallback(() => {
    setEvents([])
  }, [])

  React.useEffect(() => {
    if (!autoConnect || !url) return
    connect()
    return () => {
      disconnect()
    }
  }, [autoConnect, connect, disconnect, url])

  return {
    events,
    isConnected,
    isLoading,
    error,
    connectionState,
    connect,
    disconnect,
    clearEvents,
  }
}
