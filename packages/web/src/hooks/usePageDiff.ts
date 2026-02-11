import * as React from 'react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface PageVersion {
  id: string
  version: number
  description: string
  created_at: string
}

export interface PageVersionsResponse {
  page_id: string
  page_slug: string
  page_title: string
  versions: PageVersion[]
}

export interface PageDiffResponse {
  page_id: string
  version_a: number
  version_b: number
  old_content: string
  new_content: string
  diff_unified: string
  stats: {
    old_lines: number
    new_lines: number
  }
}

export interface UsePageVersionsForDiffReturn {
  data: PageVersionsResponse | null
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
}

/**
 * Fetch all versions of a page for diff comparison.
 */
export function usePageVersionsForDiff(
  sessionId: string | undefined,
  pageId: string | undefined
): UsePageVersionsForDiffReturn {
  const [data, setData] = React.useState<PageVersionsResponse | null>(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const refresh = React.useCallback(async () => {
    if (!sessionId || !pageId) return
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch(
        `${API_BASE}/api/sessions/${sessionId}/pages/${pageId}/versions`
      )
      if (!res.ok) throw new Error('Failed to fetch page versions')
      const result = await res.json()
      setData(result)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch page versions'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [sessionId, pageId])

  React.useEffect(() => {
    let active = true
    if (!sessionId || !pageId) return

    const load = async () => {
      setIsLoading(true)
      try {
        const res = await fetch(
          `${API_BASE}/api/sessions/${sessionId}/pages/${pageId}/versions`
        )
        if (!res.ok) throw new Error('Failed to fetch page versions')
        const result = await res.json()
        if (!active) return
        setData(result)
      } catch (err) {
        if (!active) return
        const message = err instanceof Error ? err.message : 'Failed to fetch page versions'
        setError(message)
      } finally {
        if (active) setIsLoading(false)
      }
    }

    load()

    return () => {
      active = false
    }
  }, [sessionId, pageId])

  return { data, isLoading, error, refresh }
}

export interface UsePageDiffReturn {
  data: PageDiffResponse | null
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
}

/**
 * Fetch diff between two page versions.
 */
export function usePageDiff(
  sessionId: string | undefined,
  pageId: string | undefined,
  versionA: number | null = null,
  versionB: number | null = null,
): UsePageDiffReturn {
  const [data, setData] = React.useState<PageDiffResponse | null>(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const refresh = React.useCallback(async () => {
    if (!sessionId || !pageId || versionA === null || versionB === null) return
    setIsLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      params.set('version_a', String(versionA))
      params.set('version_b', String(versionB))

      const res = await fetch(
        `${API_BASE}/api/sessions/${sessionId}/pages/${pageId}/diff?${params}`
      )
      if (!res.ok) throw new Error('Failed to fetch page diff')
      const result = await res.json()
      setData(result)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch page diff'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [sessionId, pageId, versionA, versionB])

  React.useEffect(() => {
    let active = true
    if (!sessionId || !pageId || versionA === null || versionB === null) return

    const load = async () => {
      setIsLoading(true)
      try {
        const params = new URLSearchParams()
        params.set('version_a', String(versionA))
        params.set('version_b', String(versionB))

        const res = await fetch(
          `${API_BASE}/api/sessions/${sessionId}/pages/${pageId}/diff?${params}`
        )
        if (!res.ok) throw new Error('Failed to fetch page diff')
        const result = await res.json()
        if (!active) return
        setData(result)
      } catch (err) {
        if (!active) return
        const message = err instanceof Error ? err.message : 'Failed to fetch page diff'
        setError(message)
      } finally {
        if (active) setIsLoading(false)
      }
    }

    load()

    return () => {
      active = false
    }
  }, [sessionId, pageId, versionA, versionB])

  return { data, isLoading, error, refresh }
}
