import * as React from 'react'
import { api } from '@/api/client'
import type { PageVersion } from '@/types'

type ApiPageVersion = {
  id?: number
  page_id?: string
  version?: number
  description?: string | null
  created_at?: string
  source?: 'auto' | 'manual' | 'rollback'
  is_pinned?: boolean
  is_released?: boolean
  available?: boolean
  fallback_used?: boolean
  previewable?: boolean
}

const toDate = (value?: string) => (value ? new Date(value) : new Date())

const normalizePageVersion = (data: unknown): PageVersion | null => {
  if (!data || typeof data !== 'object') return null
  const version = data as ApiPageVersion

  if (version.id === undefined) return null

  return {
    id: version.id,
    pageId: version.page_id ?? '',
    version: version.version ?? 1,
    description: version.description ?? null,
    createdAt: toDate(version.created_at),
    source: version.source,
    isPinned: version.is_pinned,
    isReleased: version.is_released,
    available: version.available,
    fallbackUsed: version.fallback_used,
    previewable: version.previewable,
  }
}

export interface UsePageVersionsOptions {
  enabled?: boolean
  includeReleased?: boolean
}

export interface UsePageVersionsReturn {
  versions: PageVersion[]
  currentVersionId: number | null
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
}

export function usePageVersions(
  pageId: string | null,
  options?: UsePageVersionsOptions
): UsePageVersionsReturn {
  const { enabled = true, includeReleased = false } = options ?? {}

  const [versions, setVersions] = React.useState<PageVersion[]>([])
  const [currentVersionId, setCurrentVersionId] = React.useState<number | null>(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const refresh = React.useCallback(async () => {
    if (!pageId || !enabled) return
    setIsLoading(true)
    setError(null)
    try {
      const response = await api.pages.getVersions(pageId, includeReleased)
      const normalizedVersions = (response.versions ?? [])
        .map((v) => normalizePageVersion(v))
        .filter((v): v is PageVersion => v !== null)
        .sort((a, b) => b.version - a.version) // Newest first

      setVersions(normalizedVersions)
      setCurrentVersionId(response.current_version_id ?? null)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load page versions'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [pageId, enabled, includeReleased])

  // Initial load
  React.useEffect(() => {
    let active = true
    if (!pageId || !enabled) return

    const load = async () => {
      setIsLoading(true)
      try {
        const response = await api.pages.getVersions(pageId, includeReleased)
        if (!active) return

        const normalizedVersions = (response.versions ?? [])
          .map((v) => normalizePageVersion(v))
          .filter((v): v is PageVersion => v !== null)
          .sort((a, b) => b.version - a.version) // Newest first

        setVersions(normalizedVersions)
        setCurrentVersionId(response.current_version_id ?? null)
      } catch (err) {
        if (!active) return
        const message = err instanceof Error ? err.message : 'Failed to load page versions'
        setError(message)
      } finally {
        if (active) setIsLoading(false)
      }
    }

    load()

    return () => {
      active = false
    }
  }, [pageId, enabled, includeReleased])

  // Handle page version events for real-time updates
  React.useEffect(() => {
    if (!enabled) return

    const handleEvent = (event: Event) => {
      const customEvent = event as CustomEvent
      const payload = customEvent.detail
      if (!payload || typeof payload !== 'object') return

      // Refresh versions when a new version is created for this page
      if (payload.type === 'page_version_created' && payload.page_id === pageId) {
        refresh()
      }
    }

    window.addEventListener('page-event', handleEvent)
    return () => window.removeEventListener('page-event', handleEvent)
  }, [enabled, pageId, refresh])

  return {
    versions,
    currentVersionId,
    isLoading,
    error,
    refresh,
  }
}
