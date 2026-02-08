import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'

export interface EventData {
  id?: string
  name?: string
  type?: string
  data?: unknown
  payload?: unknown
  timestamp: number | string
  page?: string
  scene?: string
}

export type PreviewEvent = EventData

export type RecordType = 'order_submitted' | 'booking_submitted' | 'form_submission'

export interface RecordData {
  type: RecordType
  payload?: unknown
  data?: unknown
  created_at?: string
  timestamp?: number | string
}

export type PreviewRecord = RecordData

export interface PreviewData {
  state: Record<string, unknown>
  events: EventData[]
  records: RecordData[]
}

export interface PreviewMessage {
  type: 'instant-coffee:update'
  state: Record<string, unknown>
  events: EventData[]
  records: RecordData[]
  timestamp: number
}

export interface PreviewBridgeState {
  data: PreviewData
  connected: boolean
  lastUpdate: number | null
}

export interface UsePreviewBridgeOptions {
  debounceMs?: number
  onMessage?: (data: PreviewData) => void
  onConnect?: () => void
  onDisconnect?: () => void
  resetKey?: string
}

const buildEmptyData = (): PreviewData => ({ state: {}, events: [], records: [] })

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const isEventData = (value: unknown): value is EventData => {
  if (!isObject(value)) return false
  const hasName = typeof value.name === 'string'
  const hasType = typeof value.type === 'string'
  if (!hasName && !hasType) return false
  if (typeof value.timestamp !== 'number' && typeof value.timestamp !== 'string') return false
  return true
}

const isRecordData = (value: unknown): value is RecordData => {
  if (!isObject(value)) return false
  if (
    value.type !== 'order_submitted' &&
    value.type !== 'booking_submitted' &&
    value.type !== 'form_submission'
  ) {
    return false
  }
  if (!('payload' in value) && !('data' in value)) return false
  if (
    typeof value.created_at !== 'string' &&
    typeof value.timestamp !== 'number' &&
    typeof value.timestamp !== 'string'
  ) {
    return false
  }
  return true
}

export const isPreviewMessage = (msg: unknown): msg is PreviewMessage => {
  if (!isObject(msg)) return false
  if (msg.type !== 'instant-coffee:update') return false
  if (!isObject(msg.state)) return false
  if (!Array.isArray(msg.events) || !msg.events.every(isEventData)) return false
  if (!Array.isArray(msg.records) || !msg.records.every(isRecordData)) return false
  if (typeof msg.timestamp !== 'number') return false
  return true
}

const parseMessagePayload = (payload: unknown) => {
  if (typeof payload !== 'string') return payload
  try {
    return JSON.parse(payload) as unknown
  } catch {
    return payload
  }
}

const hasSubmitEvent = (events: EventData[]) =>
  events.some((event) => {
    const raw = typeof event.name === 'string' ? event.name : event.type
    if (typeof raw !== 'string') return false
    const lowered = raw.toLowerCase()
    return lowered.includes('submit') || lowered.includes('checkout')
  })

export function usePreviewBridge(
  iframeRef: RefObject<HTMLIFrameElement | null>,
  options: UsePreviewBridgeOptions = {}
): PreviewBridgeState {
  const { debounceMs = 100, onMessage, onConnect, onDisconnect, resetKey } = options

  const [data, setData] = useState<PreviewData>(() => buildEmptyData())
  const [connected, setConnected] = useState(false)
  const [lastUpdate, setLastUpdate] = useState<number | null>(null)

  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pendingDataRef = useRef<PreviewData | null>(null)
  const connectedRef = useRef(false)
  const unloadWindowRef = useRef<Window | null>(null)
  const resetKeyRef = useRef<string | undefined>(resetKey)

  const clearDebounce = useCallback(() => {
    if (debounceTimerRef.current !== null) {
      clearTimeout(debounceTimerRef.current)
      debounceTimerRef.current = null
    }
    pendingDataRef.current = null
  }, [])

  const markConnected = useCallback(() => {
    if (!connectedRef.current) {
      connectedRef.current = true
      setConnected(true)
      onConnect?.()
      return
    }
    setConnected(true)
  }, [onConnect])

  const resetData = useCallback(() => {
    clearDebounce()
    setData(buildEmptyData())
    setLastUpdate(null)
  }, [clearDebounce])

  const markDisconnected = useCallback(() => {
    resetData()
    if (connectedRef.current) {
      connectedRef.current = false
      setConnected(false)
      onDisconnect?.()
    } else {
      setConnected(false)
    }
  }, [onDisconnect, resetData])

  const updateData = useCallback(
    (newData: PreviewData, immediate = false) => {
      if (immediate) {
        clearDebounce()
        setData(newData)
        setLastUpdate(Date.now())
        onMessage?.(newData)
        return
      }
      pendingDataRef.current = newData
      if (debounceTimerRef.current !== null) {
        clearTimeout(debounceTimerRef.current)
      }
      debounceTimerRef.current = setTimeout(() => {
        if (!pendingDataRef.current) return
        const next = pendingDataRef.current
        pendingDataRef.current = null
        setData(next)
        setLastUpdate(Date.now())
        onMessage?.(next)
      }, debounceMs)
    },
    [clearDebounce, debounceMs, onMessage]
  )

  useEffect(() => {
    if (resetKeyRef.current === resetKey) return
    resetKeyRef.current = resetKey
    if (connectedRef.current) {
      connectedRef.current = false
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setConnected(false)
      onDisconnect?.()
    }
    resetData()
  }, [onDisconnect, resetData, resetKey])

  useEffect(() => {
    const iframe = iframeRef.current
    if (!iframe) return

    const handleMessage = (event: MessageEvent) => {
      if (import.meta.env.PROD && event.origin !== window.location.origin) {
        return
      }
      const payload = parseMessagePayload(event.data)
      if (!isPreviewMessage(payload)) return
      markConnected()
      updateData(
        {
          state: payload.state,
          events: payload.events,
          records: payload.records,
        },
        hasSubmitEvent(payload.events)
      )
    }

    const handleLoad = () => {
      markConnected()
      if (!iframe.contentWindow) return
      unloadWindowRef.current = iframe.contentWindow
      try {
        iframe.contentWindow.addEventListener('beforeunload', markDisconnected)
        iframe.contentWindow.addEventListener('unload', markDisconnected)
      } catch {
        // Cross-origin iframe, ignore unload binding.
      }
    }

    const handleUnload = () => {
      markDisconnected()
    }

    iframe.addEventListener('load', handleLoad)
    iframe.addEventListener('error', handleUnload)
    window.addEventListener('message', handleMessage)

    return () => {
      iframe.removeEventListener('load', handleLoad)
      iframe.removeEventListener('error', handleUnload)
      window.removeEventListener('message', handleMessage)
      if (unloadWindowRef.current) {
        try {
          unloadWindowRef.current.removeEventListener('beforeunload', markDisconnected)
          unloadWindowRef.current.removeEventListener('unload', markDisconnected)
        } catch {
          // ignore detach failures
        }
        unloadWindowRef.current = null
      }
      clearDebounce()
    }
  }, [clearDebounce, iframeRef, markConnected, markDisconnected, updateData])

  return {
    data,
    connected,
    lastUpdate,
  }
}
