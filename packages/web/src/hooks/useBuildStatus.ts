import * as React from 'react'
import { api } from '@/api/client'
import type { BuildProgress, BuildState, BuildStatusType } from '@/types/build'
import type { ExecutionEvent } from '@/types/events'

const DEFAULT_BUILD_STATE: BuildState = {
  status: 'idle',
  pages: [],
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value && typeof value === 'object')

const toTimestampMs = (timestamp?: string) => {
  const parsed = Date.parse(timestamp ?? '')
  return Number.isNaN(parsed) ? Date.now() : parsed
}

const normalizeStatus = (value: unknown): BuildStatusType => {
  if (value === 'pending' || value === 'building' || value === 'success' || value === 'failed') {
    return value
  }
  return 'pending'
}

const normalizeBuildInfo = (payload: unknown): BuildState | null => {
  if (!payload || typeof payload !== 'object') return null
  const raw = payload as Record<string, unknown>
  const pages = Array.isArray(raw.pages)
    ? raw.pages.filter((page): page is string => typeof page === 'string')
    : []
  const distPath =
    typeof raw.dist_path === 'string'
      ? raw.dist_path
      : typeof raw.distPath === 'string'
        ? raw.distPath
        : undefined
  const error = typeof raw.error === 'string' ? raw.error : undefined
  const startedAt =
    typeof raw.started_at === 'string'
      ? raw.started_at
      : typeof raw.startedAt === 'string'
        ? raw.startedAt
        : undefined
  const completedAt =
    typeof raw.completed_at === 'string'
      ? raw.completed_at
      : typeof raw.completedAt === 'string'
        ? raw.completedAt
        : undefined
  const status = normalizeStatus(raw.status)
  const resolvedStatus =
    status === 'pending' && pages.length === 0 && !startedAt && !completedAt && !error
      ? 'idle'
      : status
  return {
    status: resolvedStatus,
    pages,
    distPath,
    error,
    startedAt,
    completedAt,
  }
}

const clampPercent = (value: number) => Math.min(100, Math.max(0, value))

const toNumber = (value: unknown): number | undefined => {
  if (typeof value === 'number' && !Number.isNaN(value)) return value
  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isNaN(parsed) ? undefined : parsed
  }
  return undefined
}

const toString = (value: unknown): string | undefined =>
  typeof value === 'string' ? value : undefined

const extractPayload = (event: ExecutionEvent): Record<string, unknown> => {
  const payload = (event as { payload?: unknown }).payload
  if (isRecord(payload)) return payload
  return event as unknown as Record<string, unknown>
}

const getEventField = (
  event: ExecutionEvent,
  payload: Record<string, unknown>,
  key: string
) => {
  if (payload[key] !== undefined) return payload[key]
  return (event as unknown as Record<string, unknown>)[key]
}

export interface UseBuildStatusReturn {
  build: BuildState
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
  startBuild: () => Promise<BuildState | null>
  cancelBuild: () => Promise<BuildState | null>
  selectedPage: string | null
  selectPage: (page: string) => void
}

export function useBuildStatus(sessionId?: string): UseBuildStatusReturn {
  const [build, setBuild] = React.useState<BuildState>(DEFAULT_BUILD_STATE)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [selectedPage, setSelectedPage] = React.useState<string | null>(null)
  const lastEventRef = React.useRef(0)
  const lastSeqRef = React.useRef<number | null>(null)
  const eventSourceRef = React.useRef<EventSource | null>(null)
  const reconnectTimeoutRef = React.useRef<number | null>(null)
  const sessionIdRef = React.useRef<string | undefined>(sessionId)
  const buildStatusRef = React.useRef(build.status)
  const buildRef = React.useRef(build)

  React.useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])

  React.useEffect(() => {
    buildStatusRef.current = build.status
    buildRef.current = build
  }, [build])

  const clearReconnect = React.useCallback(() => {
    if (reconnectTimeoutRef.current !== null) {
      window.clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
  }, [])

  const disconnectStream = React.useCallback(() => {
    clearReconnect()
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
  }, [clearReconnect])

  const applyBuildInfo = React.useCallback((info: BuildState) => {
    setBuild((prev) => {
      const next: BuildState = {
        ...prev,
        ...info,
        progress: info.progress ?? prev.progress,
      }
      if (info.status === 'building' || info.status === 'pending') {
        next.progress = info.progress
        next.error = info.error ?? undefined
      }
      return next
    })
  }, [])

  const refresh = React.useCallback(async () => {
    if (!sessionId) return
    setIsLoading(true)
    setError(null)
    try {
      const info = normalizeBuildInfo(await api.build.status(sessionId))
      if (info) applyBuildInfo(info)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load build status'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [applyBuildInfo, sessionId])

  const startBuild = React.useCallback(async () => {
    if (!sessionId) return null
    setIsLoading(true)
    setError(null)
    try {
      const info = normalizeBuildInfo(await api.build.start(sessionId))
      if (info) {
        applyBuildInfo(info)
        return info
      }
      return null
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start build'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [applyBuildInfo, sessionId])

  const cancelBuild = React.useCallback(async () => {
    if (!sessionId) return null
    setIsLoading(true)
    setError(null)
    try {
      const info = normalizeBuildInfo(await api.build.cancel(sessionId))
      if (info) {
        applyBuildInfo(info)
        return info
      }
      return null
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to cancel build'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [applyBuildInfo, sessionId])

  const applyBuildEvent = React.useCallback(
    (event: ExecutionEvent) => {
      const eventSessionId = (event as { session_id?: string }).session_id
      if (sessionId && eventSessionId && eventSessionId !== sessionId) return
      if (!event.type.startsWith('build_')) return
      const timestampMs = toTimestampMs(event.timestamp)
      if (timestampMs < lastEventRef.current) return
      lastEventRef.current = timestampMs

      const payload = extractPayload(event)
      const step = toString(getEventField(event, payload, 'step'))
      const message = toString(getEventField(event, payload, 'message'))
      const percentValue = toNumber(getEventField(event, payload, 'percent'))
      const percent = typeof percentValue === 'number' ? clampPercent(percentValue) : undefined
      const pagesValue = getEventField(event, payload, 'pages')
      const pages = Array.isArray(pagesValue)
        ? pagesValue.filter((page): page is string => typeof page === 'string')
        : undefined
      const distPath = toString(getEventField(event, payload, 'dist_path'))
      const errorMessage = toString(getEventField(event, payload, 'error'))

      setBuild((prev) => {
        const baseProgress: BuildProgress | undefined = prev.progress
        const nextProgress =
          step || message || typeof percent === 'number'
            ? {
                step: step ?? baseProgress?.step,
                message: message ?? baseProgress?.message,
                percent: typeof percent === 'number' ? percent : baseProgress?.percent,
              }
            : baseProgress

        if (event.type === 'build_start') {
          return {
            ...prev,
            status: 'building',
            error: undefined,
            pages: [],
            startedAt: event.timestamp ?? prev.startedAt,
            completedAt: undefined,
            progress: {
              step: step ?? message ?? 'Starting build',
              message: message ?? undefined,
              percent: typeof percent === 'number' ? percent : 0,
            },
          }
        }

        if (event.type === 'build_progress') {
          return {
            ...prev,
            status: 'building',
            progress: nextProgress,
          }
        }

        if (event.type === 'build_complete') {
          return {
            ...prev,
            status: 'success',
            pages: pages ?? prev.pages,
            distPath: distPath ?? prev.distPath,
            completedAt: event.timestamp ?? prev.completedAt,
            progress: nextProgress ?? prev.progress,
          }
        }

        if (event.type === 'build_failed') {
          return {
            ...prev,
            status: 'failed',
            error: errorMessage ?? prev.error,
            completedAt: event.timestamp ?? prev.completedAt,
            progress: nextProgress ?? prev.progress,
          }
        }

        return prev
      })
    },
    [sessionId]
  )

  const connectStream = React.useCallback(() => {
    if (!sessionId) return
    clearReconnect()
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    const startedAt = buildRef.current.startedAt
    if (startedAt) {
      const startedMs = toTimestampMs(startedAt)
      if (startedMs > lastEventRef.current) {
        lastEventRef.current = startedMs - 1
      }
    }

    const streamUrl = api.build.streamUrl(sessionId, {
      sinceSeq: lastSeqRef.current ?? undefined,
    })
    const eventSource = new EventSource(streamUrl)
    eventSourceRef.current = eventSource

    eventSource.onmessage = (event) => {
      if (event.data === '[DONE]') {
        disconnectStream()
        return
      }
      try {
        const parsed = JSON.parse(event.data) as ExecutionEvent
        if (!parsed || typeof parsed !== 'object') return
        if (typeof parsed.seq === 'number') {
          lastSeqRef.current = parsed.seq
        }
        applyBuildEvent(parsed)
      } catch {
        // ignore parse errors
      }
    }

    eventSource.onerror = () => {
      eventSource.close()
      if (eventSourceRef.current === eventSource) {
        eventSourceRef.current = null
      }
      if (!sessionIdRef.current) return
      if (
        buildStatusRef.current !== 'building' &&
        buildStatusRef.current !== 'pending'
      ) {
        return
      }
      reconnectTimeoutRef.current = window.setTimeout(() => {
        if (!sessionIdRef.current) return
        if (
          buildStatusRef.current !== 'building' &&
          buildStatusRef.current !== 'pending'
        ) {
          return
        }
        connectStream()
      }, 2000)
    }
  }, [applyBuildEvent, clearReconnect, disconnectStream, sessionId])

  React.useEffect(() => {
    if (!sessionId) {
      setBuild(DEFAULT_BUILD_STATE)
      setSelectedPage(null)
      setError(null)
      lastEventRef.current = 0
      lastSeqRef.current = null
      disconnectStream()
      return
    }
    lastEventRef.current = 0
    lastSeqRef.current = null
    void refresh()
  }, [disconnectStream, refresh, sessionId])

  React.useEffect(() => {
    if (!sessionId) return
    const handleEvent = (event: Event) => {
      const customEvent = event as CustomEvent<ExecutionEvent>
      const detail = customEvent.detail
      if (!detail || typeof detail !== 'object') return
      applyBuildEvent(detail)
    }
    window.addEventListener('build-event', handleEvent)
    return () => window.removeEventListener('build-event', handleEvent)
  }, [applyBuildEvent, sessionId])

  React.useEffect(() => {
    if (build.pages.length === 0) {
      setSelectedPage(null)
      return
    }
    if (!selectedPage || !build.pages.includes(selectedPage)) {
      setSelectedPage(build.pages[0])
    }
  }, [build.pages, selectedPage])

  React.useEffect(() => {
    if (!sessionId) return
    if (build.status !== 'building' && build.status !== 'pending') return
    const interval = window.setInterval(() => {
      void refresh()
    }, 4000)
    return () => window.clearInterval(interval)
  }, [build.status, refresh, sessionId])

  React.useEffect(() => {
    if (!sessionId) return
    if (build.status !== 'building' && build.status !== 'pending') {
      disconnectStream()
      return
    }
    connectStream()
    return () => {
      disconnectStream()
    }
  }, [build.status, connectStream, disconnectStream, sessionId])

  return {
    build,
    isLoading,
    error,
    refresh,
    startBuild,
    cancelBuild,
    selectedPage,
    selectPage: setSelectedPage,
  }
}
