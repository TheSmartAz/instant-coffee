import * as React from 'react'
import { api } from '@/api/client'
import { notifyAsyncError } from '@/lib/notifyAsyncError'
import type { Page } from '@/types'

type ApiPage = {
  id?: string
  session_id?: string
  title?: string
  slug?: string
  description?: string
  order_index?: number
  current_version_id?: number | null
  created_at?: string
  updated_at?: string
}

const toDate = (value?: string) => (value ? new Date(value) : new Date())

const normalizePage = (data: unknown): Page | null => {
  if (!data || typeof data !== 'object') return null
  const page = data as ApiPage

  if (!page.id) return null

  return {
    id: page.id,
    sessionId: page.session_id ?? '',
    title: page.title ?? '',
    slug: page.slug ?? '',
    description: page.description ?? '',
    orderIndex: page.order_index ?? 0,
    currentVersionId: page.current_version_id ?? null,
    createdAt: toDate(page.created_at),
    updatedAt: toDate(page.updated_at),
  }
}

export interface UsePagesOptions {
  enabled?: boolean
  onPageCreated?: (pageId: string) => void
  onPageVersionCreated?: (pageId: string) => void
  onPagePreviewReady?: (
    pageId: string,
    payload: { html?: string; previewUrl?: string }
  ) => void
}

export interface UsePagesReturn {
  pages: Page[]
  selectedPage: Page | null
  selectedPageId: string | null
  selectPage: (pageId: string) => void
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
  getPreviewHtml: (pageId: string) => Promise<string | null>
}

export function usePages(
  sessionId?: string,
  options?: UsePagesOptions
): UsePagesReturn {
  const {
    enabled = true,
    onPageCreated,
    onPageVersionCreated,
    onPagePreviewReady,
  } = options ?? {}

  const [pages, setPages] = React.useState<Page[]>([])
  const [selectedPageId, setSelectedPageId] = React.useState<string | null>(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const selectedPage = React.useMemo(
    () => pages.find((p) => p.id === selectedPageId) ?? null,
    [pages, selectedPageId]
  )

  const refresh = React.useCallback(async () => {
    if (!sessionId || !enabled) return
    setIsLoading(true)
    setError(null)
    try {
      const response = await api.pages.list(sessionId)
      const normalizedPages = (response.pages ?? [])
        .map((p) => normalizePage(p))
        .filter((p): p is Page => p !== null)
        .sort((a, b) => a.orderIndex - b.orderIndex)

      setPages(normalizedPages)

      // Auto-select first page if no page is selected
      if (normalizedPages.length > 0 && !selectedPageId) {
        setSelectedPageId(normalizedPages[0].id)
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load pages'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [sessionId, enabled, selectedPageId])

  const selectPage = React.useCallback((pageId: string) => {
    setSelectedPageId(pageId)
  }, [])

  const getPreviewHtml = React.useCallback(
    async (pageId: string): Promise<string | null> => {
      try {
        const response = await api.pages.getPreview(pageId)
        return response.html ?? null
      } catch (err) {
        notifyAsyncError(err, {
          title: 'Failed to load page preview',
          loggerPrefix: 'Failed to load page preview:',
        })
        return null
      }
    },
    []
  )

  // Initial load
  React.useEffect(() => {
    let active = true
    if (!sessionId || !enabled) return

    const load = async () => {
      setIsLoading(true)
      try {
        const response = await api.pages.list(sessionId)
        if (!active) return

        const normalizedPages = (response.pages ?? [])
          .map((p) => normalizePage(p))
          .filter((p): p is Page => p !== null)
          .sort((a, b) => a.orderIndex - b.orderIndex)

        setPages(normalizedPages)

        // Auto-select first page on initial load
        if (normalizedPages.length > 0) {
          setSelectedPageId(normalizedPages[0].id)
        }
      } catch (err) {
        if (!active) return
        const message = err instanceof Error ? err.message : 'Failed to load pages'
        setError(message)
      } finally {
        if (active) setIsLoading(false)
      }
    }

    load()

    return () => {
      active = false
    }
  }, [sessionId, enabled])

  // Handle SSE events for real-time updates
  React.useEffect(() => {
    if (!enabled) return

    const handleEvent = (event: Event) => {
      const customEvent = event as CustomEvent
      const payload = customEvent.detail
      if (!payload || typeof payload !== 'object') return

      switch (payload.type) {
        case 'page_created':
          onPageCreated?.(payload.page_id ?? '')
          refresh()
          break
        case 'page_version_created':
          onPageVersionCreated?.(payload.page_id ?? '')
          // Only refresh if it's the current page
          if (payload.page_id === selectedPageId) {
            refresh()
          }
          break
        case 'page_preview_ready':
          // Trigger preview refresh for the current page
          if (payload.page_id && payload.page_id === selectedPageId) {
            const baseUrl = api.pages.previewUrl(payload.page_id)
            const cacheBustedUrl = `${baseUrl}${baseUrl.includes('?') ? '&' : '?'}t=${Date.now()}`
            onPagePreviewReady?.(payload.page_id, { previewUrl: cacheBustedUrl })
            refresh()
          }
          break
      }
    }

    // Listen for custom events dispatched by the chat component
    window.addEventListener('page-event', handleEvent)

    return () => {
      window.removeEventListener('page-event', handleEvent)
    }
  }, [
    enabled,
    onPageCreated,
    onPageVersionCreated,
    onPagePreviewReady,
    refresh,
    selectedPageId,
  ])

  return {
    pages,
    selectedPage,
    selectedPageId,
    selectPage,
    isLoading,
    error,
    refresh,
    getPreviewHtml,
  }
}
