import * as React from 'react'
import { api, type RequestError } from '@/api/client'
import type { ProductDocHistory } from '@/types'

export interface UseProductDocHistoryOptions {
  enabled?: boolean
  includeReleased?: boolean
}

export interface UseProductDocHistoryReturn {
  history: ProductDocHistory[]
  pinnedCount: number
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
}

export function useProductDocHistory(
  sessionId?: string,
  options?: UseProductDocHistoryOptions
): UseProductDocHistoryReturn {
  const { enabled = true, includeReleased = false } = options ?? {}

  const [history, setHistory] = React.useState<ProductDocHistory[]>([])
  const [pinnedCount, setPinnedCount] = React.useState(0)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const refresh = React.useCallback(async () => {
    if (!sessionId || !enabled) return
    setIsLoading(true)
    setError(null)
    try {
      const response = await api.productDocHistory.getProductDocHistory(sessionId, {
        includeReleased,
      })
      const sorted = [...(response.history ?? [])].sort(
        (a, b) => b.version - a.version
      )
      setHistory(sorted)
      setPinnedCount(response.pinned_count ?? 0)
    } catch (err) {
      const status = (err as RequestError)?.status
      if (status === 404) {
        setHistory([])
        setPinnedCount(0)
        setError(null)
        return
      }
      const message =
        err instanceof Error ? err.message : 'Failed to load product doc history'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [sessionId, enabled, includeReleased])

  React.useEffect(() => {
    let active = true
    if (!sessionId || !enabled) return

    const load = async () => {
      setIsLoading(true)
      try {
        const response = await api.productDocHistory.getProductDocHistory(sessionId, {
          includeReleased,
        })
        if (!active) return
        const sorted = [...(response.history ?? [])].sort(
          (a, b) => b.version - a.version
        )
        setHistory(sorted)
        setPinnedCount(response.pinned_count ?? 0)
      } catch (err) {
        if (!active) return
        const status = (err as RequestError)?.status
        if (status === 404) {
          setHistory([])
          setPinnedCount(0)
          setError(null)
          return
        }
        const message =
          err instanceof Error ? err.message : 'Failed to load product doc history'
        setError(message)
      } finally {
        if (active) setIsLoading(false)
      }
    }

    load()

    return () => {
      active = false
    }
  }, [sessionId, enabled, includeReleased])

  React.useEffect(() => {
    if (!enabled) return

    const handleEvent = (event: Event) => {
      const customEvent = event as CustomEvent
      const payload = customEvent.detail
      if (!payload || typeof payload !== 'object') return

      switch (payload.type) {
        case 'product_doc_generated':
        case 'product_doc_updated':
        case 'product_doc_confirmed':
        case 'product_doc_outdated':
          refresh()
          break
      }
    }

    window.addEventListener('product-doc-event', handleEvent)
    return () => window.removeEventListener('product-doc-event', handleEvent)
  }, [enabled, refresh])

  return {
    history,
    pinnedCount,
    isLoading,
    error,
    refresh,
  }
}
