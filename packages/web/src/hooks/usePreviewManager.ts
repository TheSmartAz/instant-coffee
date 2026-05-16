import * as React from 'react'
import { api, type RequestError } from '@/api/client'
import { notifyAsyncError } from '@/lib/notifyAsyncError'
import type { Page } from '@/types'
import type { SessionDetail, Version } from '@/types'

interface UsePreviewManagerOptions {
  sessionId?: string
  session?: SessionDetail | null
  versions?: Version[]
  pages: Page[]
  selectedPageId: string | null
  hasLoadedPages: boolean
  buildStatus: string
  buildPagePreviewUrl: (pageId: string, options?: { bustCache?: boolean }) => string
  refresh: () => Promise<boolean | undefined>
}

interface PreviewManagerState {
  previewUrl: string | null
  pagePreviewVersion: number | null
  appMode: boolean
  buildPreviewStamp: number
  setBuildPreviewStamp: (value: number) => void
  autoLoadedPreviewRef: React.MutableRefObject<Set<string>>
  handlePreview: (payload: { previewUrl?: string | null }) => void
  setPreviewUrl: (value: string | null) => void
  setPagePreviewVersion: (value: number | null) => void
  loadPagePreview: (pageId: string, options?: { bustCache?: boolean }) => Promise<void>
}

export function usePreviewManager({
  session,
  versions,
  selectedPageId,
  hasLoadedPages,
  buildStatus,
  buildPagePreviewUrl,
  refresh,
}: UsePreviewManagerOptions): PreviewManagerState {
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null)
  const [pagePreviewVersion, setPagePreviewVersion] = React.useState<number | null>(null)
  const appMode = true
  const [buildPreviewStamp, setBuildPreviewStamp] = React.useState(0)
  const autoLoadedPreviewRef = React.useRef<Set<string>>(new Set())
  const previousBuildStatusRef = React.useRef(buildStatus)
  void session
  void versions
  void hasLoadedPages

  const loadPagePreview = React.useCallback(
    async (pageId: string, options?: { bustCache?: boolean }) => {
      try {
        const preview = await api.pages.getPreview(pageId)
        setPagePreviewVersion(preview.version ?? null)
        const url = buildPagePreviewUrl(pageId, options)
        setPreviewUrl(url)
      } catch (err) {
        const status = (err as RequestError)?.status
        if (status === 404) {
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
    [buildPagePreviewUrl]
  )

  // Auto-load page preview on first selection
  React.useEffect(() => {
    if (!selectedPageId) return
    if (previewUrl) return
    if (autoLoadedPreviewRef.current.has(selectedPageId)) return
    autoLoadedPreviewRef.current.add(selectedPageId)
    void loadPagePreview(selectedPageId)
  }, [selectedPageId, previewUrl, loadPagePreview])

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
    (payload: { previewUrl?: string | null }) => {
      if (payload.previewUrl) {
        setPreviewUrl(payload.previewUrl)
      }
    },
    []
  )

  return {
    previewUrl,
    pagePreviewVersion,
    appMode,
    buildPreviewStamp,
    setBuildPreviewStamp,
    autoLoadedPreviewRef,
    handlePreview,
    setPreviewUrl,
    setPagePreviewVersion,
    loadPagePreview,
  }
}
