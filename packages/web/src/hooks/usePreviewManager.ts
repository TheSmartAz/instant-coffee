import * as React from 'react'
import { api, type RequestError } from '@/api/client'
import { notifyAsyncError } from '@/lib/notifyAsyncError'
import type { SessionDetail, Version, Page } from '@/types'

interface UsePreviewManagerOptions {
  sessionId?: string
  session: SessionDetail | null
  versions: Version[]
  pages: Page[]
  selectedPageId: string | null
  hasLoadedPages: boolean
  buildStatus: string
  buildPagePreviewUrl: (pageId: string, options?: { bustCache?: boolean }) => string
  refresh: () => Promise<boolean | undefined>
}

interface PreviewManagerState {
  previewHtml: string | null
  previewUrl: string | null
  pagePreviewVersion: number | null
  appMode: boolean
  setAppMode: (value: boolean) => void
  buildPreviewStamp: number
  setBuildPreviewStamp: (value: number) => void
  autoLoadedPreviewRef: React.MutableRefObject<Set<string>>
  handlePreview: (payload: { html?: string; previewUrl?: string | null }) => void
  setPreviewHtml: (value: string | null) => void
  setPreviewUrl: (value: string | null) => void
  setPagePreviewVersion: (value: number | null) => void
  loadPagePreview: (pageId: string, options?: { bustCache?: boolean }) => Promise<void>
}

export function usePreviewManager({
  sessionId,
  session,
  versions,
  pages,
  selectedPageId,
  hasLoadedPages,
  buildStatus,
  buildPagePreviewUrl,
  refresh,
}: UsePreviewManagerOptions): PreviewManagerState {
  const [previewHtml, setPreviewHtml] = React.useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null)
  const [pagePreviewVersion, setPagePreviewVersion] = React.useState<number | null>(null)
  const [appMode, setAppMode] = React.useState(false)
  const [buildPreviewStamp, setBuildPreviewStamp] = React.useState(0)
  const autoLoadedPreviewRef = React.useRef<Set<string>>(new Set())
  const previousBuildStatusRef = React.useRef(buildStatus)
  const hasPages = pages.length > 0

  const loadPagePreview = React.useCallback(
    async (pageId: string, options?: { bustCache?: boolean }) => {
      try {
        const preview = await api.pages.getPreview(pageId)
        setPagePreviewVersion(preview.version ?? null)
        if (appMode) {
          setPreviewHtml(preview.html ?? null)
          setPreviewUrl(null)
          return
        }
        const url = buildPagePreviewUrl(pageId, options)
        setPreviewUrl(url)
        setPreviewHtml(null)
      } catch (err) {
        const status = (err as RequestError)?.status
        if (status === 404) {
          setPreviewHtml(null)
          setPreviewUrl(null)
          setPagePreviewVersion(null)
          return
        }
        notifyAsyncError(err, {
          title: 'Preview load failed',
          loggerPrefix: 'Failed to load page preview:',
        })
      }
    },
    [appMode, buildPagePreviewUrl]
  )

  const isHttpUrl = React.useCallback(
    (value?: string | null) => (value ? /^https?:\/\//i.test(value) : false),
    []
  )

  // Session preview fallback (no pages)
  React.useEffect(() => {
    if (!hasLoadedPages || hasPages) return
    if (session?.previewHtml) {
      setPreviewHtml(session.previewHtml)
      setPreviewUrl(null)
      return
    }
    if (session?.previewUrl && isHttpUrl(session.previewUrl)) {
      setPreviewUrl(session.previewUrl)
    }
  }, [hasLoadedPages, hasPages, isHttpUrl, session?.previewHtml, session?.previewUrl])

  // Version preview fallback (no pages)
  React.useEffect(() => {
    if (!hasLoadedPages || hasPages) return
    const active = versions.find((version) => version.isCurrent)
    if (active?.previewHtml) {
      setPreviewHtml(active.previewHtml)
      setPreviewUrl(null)
      return
    }
    if (active?.previewUrl && isHttpUrl(active.previewUrl)) {
      setPreviewUrl(active.previewUrl)
    }
  }, [hasLoadedPages, hasPages, isHttpUrl, versions])

  // Clear session-level preview URL when pages exist
  React.useEffect(() => {
    if (!hasPages) return
    if (previewUrl && previewUrl.includes('/api/sessions/')) {
      setPreviewUrl(null)
    }
  }, [hasPages, previewUrl])

  // Reset page preview version on page change
  React.useEffect(() => {
    setPagePreviewVersion(null)
  }, [selectedPageId])

  // Auto-load page preview on first selection
  React.useEffect(() => {
    if (!selectedPageId) return
    if (previewUrl || previewHtml) return
    if (autoLoadedPreviewRef.current.has(selectedPageId)) return
    autoLoadedPreviewRef.current.add(selectedPageId)
    void loadPagePreview(selectedPageId)
  }, [selectedPageId, previewUrl, previewHtml, loadPagePreview])

  // Reload page preview on appMode change
  React.useEffect(() => {
    if (!selectedPageId) return
    void loadPagePreview(selectedPageId, { bustCache: true })
  }, [appMode, loadPagePreview, selectedPageId])

  // Load/persist appMode from localStorage
  React.useEffect(() => {
    if (!sessionId) {
      setAppMode(false)
      return
    }
    try {
      const key = `instant-coffee:app-mode:${sessionId}`
      const raw = window.localStorage.getItem(key)
      setAppMode(raw === 'true')
    } catch {
      setAppMode(false)
    }
  }, [sessionId])

  // Persist appMode to localStorage
  React.useEffect(() => {
    if (!sessionId) return
    try {
      const key = `instant-coffee:app-mode:${sessionId}`
      window.localStorage.setItem(key, appMode ? 'true' : 'false')
    } catch {
      // ignore storage failures
    }
  }, [appMode, sessionId])

  // Refresh preview on build success
  React.useEffect(() => {
    const previous = previousBuildStatusRef.current
    if (previous !== 'success' && buildStatus === 'success') {
      setBuildPreviewStamp(Date.now())
      if (selectedPageId) {
        void loadPagePreview(selectedPageId, { bustCache: true })
      } else {
        void refresh()
      }
    }
    previousBuildStatusRef.current = buildStatus
  }, [buildStatus, loadPagePreview, refresh, selectedPageId])

  // Callback for chat onPreview
  const handlePreview = React.useCallback(
    (payload: { html?: string; previewUrl?: string | null }) => {
      if (payload.html) {
        setPreviewHtml(payload.html)
        setPreviewUrl(null)
        return
      }
      if (payload.previewUrl && isHttpUrl(payload.previewUrl)) {
        const isPagePreview = payload.previewUrl.includes('/api/pages/')
        const allowSessionPreview = !hasPages && hasLoadedPages && versions.length > 0
        if (isPagePreview || allowSessionPreview) {
          setPreviewHtml(null)
          setPreviewUrl(payload.previewUrl)
        }
      }
    },
    [hasLoadedPages, hasPages, isHttpUrl, versions.length]
  )

  return {
    previewHtml,
    previewUrl,
    pagePreviewVersion,
    appMode,
    setAppMode,
    buildPreviewStamp,
    setBuildPreviewStamp,
    autoLoadedPreviewRef,
    handlePreview,
    setPreviewHtml,
    setPreviewUrl,
    setPagePreviewVersion,
    loadPagePreview,
  }
}
