import * as React from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Settings, Activity } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ChatPanel } from '@/components/custom/ChatPanel'
import { WorkbenchPanel, type WorkbenchTab } from '@/components/custom/WorkbenchPanel'
import { VersionPanel } from '@/components/custom/VersionPanel'
import { ThreadSelector } from '@/components/custom/ThreadSelector'
import { AbortDialog } from '@/components/custom/AbortDialog'
import { api } from '@/api/client'
import { useChat } from '@/hooks/useChat'
import { useAestheticScore } from '@/hooks/useAestheticScore'
import { useBuildStatus } from '@/hooks/useBuildStatus'
import { useSession } from '@/hooks/useSession'
import { usePages } from '@/hooks/usePages'
import { useProductDoc } from '@/hooks/useProductDoc'
import { useThreads } from '@/hooks/useThreads'
import { useSessionCost } from '@/hooks/useCost'
import { usePreviewManager } from '@/hooks/usePreviewManager'
import { useAsyncAction } from '@/hooks/useAsyncAction'
import { toast } from '@/hooks/use-toast'

const LAST_PROJECT_KEY = 'instant-coffee:last-project-id'

export function ProjectPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [isVersionPanelCollapsed, setIsVersionPanelCollapsed] = React.useState(false)
  const [isRefreshing, setIsRefreshing] = React.useState(false)
  const [isExporting, setIsExporting] = React.useState(false)
  const [isAborting, setIsAborting] = React.useState(false)
  const [, setIsSwitchingThread] = React.useState(false)
  const [workbenchTab, setWorkbenchTab] = React.useState<WorkbenchTab>('preview')
  const [previewMode, setPreviewMode] = React.useState<'live' | 'build'>('live')
  const sessionId = id && id !== 'new' ? id : undefined
  const {
    threads,
    activeThreadId,
    createThread,
    deleteThread,
    switchThread,
    refresh: refreshThreads,
  } = useThreads(sessionId)
  const { session, messages, versions, isLoading, error, refresh, setMessages } =
    useSession(sessionId, activeThreadId ?? undefined)

  // Cost tracking
  const { data: costData } = useSessionCost(sessionId)

  // Multi-page support (v04) - use usePages hook
  const {
    pages,
    selectedPageId,
    selectPage,
    isLoading: isLoadingPages,
  } = usePages(sessionId, {
    onPageCreated: () => {
      // Auto-switch to preview tab when pages are generated
      setWorkbenchTab('preview')
    },
    onPageVersionCreated: (pageId) => {
      // Auto-switch to preview tab on page refinement
      if (pageId === selectedPageId) {
        setWorkbenchTab('preview')
      }
    },
    onPagePreviewReady: (pageId) => {
      // Load preview when ready
      if (pageId === selectedPageId) {
        void loadPagePreview(pageId, { bustCache: true })
      }
    },
  })
  const hasPages = pages.length > 0
  const [hasLoadedPages, setHasLoadedPages] = React.useState(false)
  const hasRequestedPagesRef = React.useRef(false)

  // ProductDoc state management - auto-switch on events
  const { productDoc, isLoading: isProductDocLoading, error: productDocError } = useProductDoc(sessionId, {
    onProductDocGenerated: () => {
      setWorkbenchTab('product-doc')
    },
    onProductDocUpdated: () => {
      setWorkbenchTab('product-doc')
    },
  })
  const { score: aestheticScore } = useAestheticScore(sessionId)
  const {
    build: buildState,
    isLoading: isBuildLoading,
    error: buildError,
    refresh: refreshBuildStatus,
    cancelBuild,
    selectedPage: selectedBuildPage,
    selectPage: selectBuildPage,
  } = useBuildStatus(sessionId)

  const buildPagePreviewUrl = React.useCallback(
    (pageId: string, options?: { bustCache?: boolean }) => {
      const baseUrl = api.pages.previewUrl(pageId)
      if (!options?.bustCache) return baseUrl
      return `${baseUrl}${baseUrl.includes('?') ? '&' : '?'}t=${Date.now()}`
    },
    []
  )

  const preview = usePreviewManager({
    sessionId,
    session,
    versions,
    pages,
    selectedPageId,
    hasLoadedPages,
    buildStatus: buildState.status,
    buildPagePreviewUrl,
    refresh,
  })

  const {
    previewHtml,
    previewUrl,
    pagePreviewVersion,
    appMode,
    setAppMode,
    buildPreviewStamp,
    setBuildPreviewStamp,
    loadPagePreview,
    handlePreview,
  } = preview
  const { runAction } = useAsyncAction()

  const extractBuildSlug = React.useCallback((pagePath: string) => {
    if (!pagePath) return null
    let normalized = pagePath.replace(/\\\\/g, '/')
    if (normalized.startsWith('pages/')) {
      normalized = normalized.slice(6)
    }
    if (normalized.endsWith('/index.html')) {
      normalized = normalized.slice(0, -'/index.html'.length)
    } else if (normalized.endsWith('index.html')) {
      normalized = normalized.slice(0, -'index.html'.length)
    }
    if (normalized.endsWith('.html')) {
      normalized = normalized.slice(0, -'.html'.length)
    }
    normalized = normalized.replace(/\/$/, '')
    if (!normalized) return 'index'
    return normalized
  }, [])

  const toBuildPath = React.useCallback((slug?: string | null) => {
    if (!slug) return null
    return slug === 'index' ? 'index.html' : `pages/${slug}/index.html`
  }, [])

  const chat = useChat({
    sessionId,
    threadId: activeThreadId ?? undefined,
    messages,
    setMessages,
    onSessionCreated: (newSessionId) => {
      if (id && id !== 'new') return
      navigate(`/project/${newSessionId}`, { replace: true })
    },
    onPreview: handlePreview,
    onTabChange: (tab) => {
      setWorkbenchTab(tab)
    },
    onPageSelect: async (slug) => {
      // Find the page with matching slug and select it
      const page = pages.find((p) => p.slug === slug)
      if (page) {
        selectPage(page.id)
        await loadPagePreview(page.id)
      }
    },
  })

  const isBuildRunning =
    buildState.status === 'building' || buildState.status === 'pending'

  // Refresh thread titles when messages change (backend auto-sets title on first message)
  const prevMessageCountRef = React.useRef(messages.length)
  React.useEffect(() => {
    const prevCount = prevMessageCountRef.current
    prevMessageCountRef.current = messages.length
    if (messages.length > prevCount && activeThreadId) {
      const activeThread = threads.find((t) => t.id === activeThreadId)
      if (activeThread && !activeThread.title) {
        refreshThreads()
      }
    }
  }, [messages.length, activeThreadId, threads, refreshThreads])

  // Remember the last visited project for the "Back" button in Settings
  React.useEffect(() => {
    if (!sessionId) return
    try {
      localStorage.setItem(LAST_PROJECT_KEY, sessionId)
    } catch {
      // ignore storage failures
    }
  }, [sessionId])

  React.useEffect(() => {
    if (!sessionId) {
      setHasLoadedPages(false)
      hasRequestedPagesRef.current = false
      return
    }
    if (isLoadingPages) {
      hasRequestedPagesRef.current = true
      return
    }
    if (hasRequestedPagesRef.current && !isLoadingPages) {
      setHasLoadedPages(true)
    }
  }, [sessionId, isLoadingPages])

  // Reset preview mode when session changes
  React.useEffect(() => {
    if (!sessionId) {
      setPreviewMode('live')
    }
  }, [sessionId])

  React.useEffect(() => {
    if (!selectedPageId || buildState.pages.length === 0) return
    const slug = pages.find((page) => page.id === selectedPageId)?.slug
    const path = toBuildPath(slug)
    if (!path) return
    if (buildState.pages.includes(path) && selectedBuildPage !== path) {
      selectBuildPage(path)
    }
  }, [
    buildState.pages,
    pages,
    selectedBuildPage,
    selectedPageId,
    selectBuildPage,
    toBuildPath,
  ])

  const lastBuildErrorRef = React.useRef<string | null>(null)

  React.useEffect(() => {
    if (!buildError) return
    if (buildError === lastBuildErrorRef.current) return
    lastBuildErrorRef.current = buildError
    toast({ title: 'Build error', description: buildError })
  }, [buildError])

  const handleRefreshPreview = React.useCallback(async () => {
    if (!sessionId) return
    if (previewMode === 'build') {
      setBuildPreviewStamp(Date.now())
      toast({ title: 'Build preview refreshed' })
      return
    }
    await runAction(
      async () => refresh(),
      {
        onStart: () => setIsRefreshing(true),
        onFinally: () => setIsRefreshing(false),
        successToast: (ok) =>
          ok
            ? { title: 'Preview refreshed' }
            : { title: 'Refresh failed', description: 'Unable to reload session.' },
        errorToast: { title: 'Refresh failed' },
      }
    )
  }, [previewMode, refresh, runAction, sessionId, setBuildPreviewStamp])

  const handleExportPreview = React.useCallback(async () => {
    if (!sessionId) return
    await runAction(
      async () => api.export.session(sessionId),
      {
        onStart: () => setIsExporting(true),
        onFinally: () => setIsExporting(false),
        successToast: (result) => {
          if (!result.success) {
            return { title: 'Export failed', description: 'Check the console for details.' }
          }

          let successCount = 0
          let failedCount = 0
          for (const page of result.manifest.pages) {
            if (page.status === 'success') {
              successCount += 1
            } else if (page.status === 'failed') {
              failedCount += 1
            }
          }

          let message = `Export succeeded! ${successCount} pages exported to ${result.export_dir}`
          if (failedCount > 0) {
            message += ` (${failedCount} pages failed)`
          }
          return { title: 'Export complete', description: message }
        },
        errorToast: { title: 'Export failed' },
      }
    )
  }, [runAction, sessionId])

  const canAbort = Boolean(sessionId) && !isAborting

  const handleNewThread = async () => {
    if (!sessionId) return
    setIsSwitchingThread(true)
    try {
      const thread = await createThread()
      if (thread) {
        setMessages([])
      }
    } finally {
      setIsSwitchingThread(false)
    }
  }

  const handleDeleteThread = async (threadId: string) => {
    if (!sessionId) return
    setIsSwitchingThread(true)
    try {
      const ok = await deleteThread(threadId)
      if (ok) {
        toast({ title: 'Thread deleted' })
      }
    } finally {
      setIsSwitchingThread(false)
    }
  }

  const handleAbort = async () => {
    if (!sessionId) return
    await runAction(
      async () => {
        await api.sessions.abort(sessionId)
        chat.stopStream()
      },
      {
        onStart: () => setIsAborting(true),
        onFinally: () => setIsAborting(false),
        successToast: { title: 'Execution aborted' },
        errorToast: { title: 'Abort failed' },
      }
    )
  }

  // Page selection handler for multi-page support
  const handleSelectPage = React.useCallback(
    async (pageId: string) => {
      selectPage(pageId)
      await loadPagePreview(pageId)
    },
    [selectPage, loadPagePreview]
  )

  // Refresh handler for individual page
  const handleRefreshPage = React.useCallback(
    async (pageId: string) => {
      if (previewMode === 'build') {
        setBuildPreviewStamp(Date.now())
        toast({ title: 'Build preview refreshed' })
        return
      }
      await runAction(
        async () => loadPagePreview(pageId, { bustCache: true }),
        {
          onStart: () => setIsRefreshing(true),
          onFinally: () => setIsRefreshing(false),
          successToast: { title: 'Page preview refreshed' },
          errorToast: { title: 'Refresh failed' },
        }
      )
    },
    [loadPagePreview, previewMode, runAction, setBuildPreviewStamp]
  )

  const buildPreviewPath = React.useMemo(() => {
    const buildPages = buildState.pages ?? []
    const selectedSlug = pages.find((page) => page.id === selectedPageId)?.slug
    const slugPath = toBuildPath(selectedSlug)
    if (slugPath && (buildPages.length === 0 || buildPages.includes(slugPath))) {
      return slugPath
    }
    if (selectedBuildPage) return selectedBuildPage
    if (buildPages.length > 0) return buildPages[0]
    return slugPath
  }, [buildState.pages, pages, selectedBuildPage, selectedPageId, toBuildPath])

  const handleBuildFromDoc = React.useCallback(async () => {
    if (!sessionId) return
    chat.sendMessage(
      'Build the pages based on the product doc. Generate all the HTML pages defined in the product document.',
      { generateNow: true }
    )
  }, [sessionId, chat])

  const handleBuildRetry = React.useCallback(() => {
    void handleBuildFromDoc()
  }, [handleBuildFromDoc])

  const handleBuildCancel = React.useCallback(async () => {
    if (!sessionId) return
    await runAction(
      async () => {
        await cancelBuild()
        void refreshBuildStatus()
      },
      {
        successToast: { title: 'Build cancelled' },
        errorToast: { title: 'Cancel failed' },
      }
    )
  }, [cancelBuild, refreshBuildStatus, runAction, sessionId])

  const handleBuildPageSelect = React.useCallback(
    (pagePath: string) => {
      if (!pagePath) return
      selectBuildPage(pagePath)
      if (pages.length === 0) return
      const slug = extractBuildSlug(pagePath)
      const matched =
        pages.find((page) => page.slug === slug) ??
        (slug === 'index' ? pages[0] : undefined)
      if (matched) {
        void handleSelectPage(matched.id)
      }
    },
    [extractBuildSlug, handleSelectPage, pages, selectBuildPage]
  )

  const activeSessionVersion =
    versions.find((version) => version.isCurrent)?.number ?? session?.currentVersion ?? null
  const previewVersionLabel = hasPages ? pagePreviewVersion : activeSessionVersion

  const buildPreviewUrl = React.useMemo(() => {
    if (!sessionId) return null
    if (buildState.pages.length === 0) return null
    const path = buildPreviewPath ?? 'index.html'
    const baseUrl = api.build.previewUrl(sessionId, path)
    if (!buildPreviewStamp) return baseUrl
    return `${baseUrl}${baseUrl.includes('?') ? '&' : '?'}t=${buildPreviewStamp}`
  }, [buildPreviewPath, buildPreviewStamp, buildState.pages.length, sessionId])

  return (
    <div className="flex h-screen flex-col animate-in fade-in">
      <header className="flex items-center justify-between border-b border-border px-6 py-4 shrink-0">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" asChild aria-label="Back to home">
            <Link to="/">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div className="text-sm font-semibold text-foreground">
            {session?.title ?? `Project ${id ?? 'Untitled'}`}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {sessionId ? (
            <Button variant="ghost" size="icon" asChild aria-label="Execution flow">
              <Link to={`/project/${sessionId}/flow`}>
                <Activity className="h-4 w-4" />
              </Link>
            </Button>
          ) : null}
          <Button variant="ghost" size="icon" asChild aria-label="Open settings">
            <Link to="/settings">
              <Settings className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Left: Chat + Preview (flex layout, no resizable) */}
        <div className="flex flex-1 min-w-0">
          {error ? (
            <div className="mx-auto max-w-3xl p-6 text-sm text-destructive">
              {error}
            </div>
          ) : null}
          {/* Chat Panel - 35% */}
          <div className="flex flex-col border-r border-border w-[35%] max-w-[45%] min-w-[300px]">
            <div className="flex h-16 items-center border-b border-border px-3 shrink-0 gap-2">
              <ThreadSelector
                threads={threads}
                activeThreadId={activeThreadId}
                onSwitchThread={async (threadId) => {
                  setIsSwitchingThread(true)
                  try {
                    await switchThread(threadId)
                  } finally {
                    setIsSwitchingThread(false)
                  }
                }}
                onNewThread={handleNewThread}
                onDeleteThread={handleDeleteThread}
              />
              {/* Actions */}
              <div className="flex items-center gap-0.5 shrink-0">
                <AbortDialog disabled={!canAbort} onAbort={handleAbort} />
              </div>
            </div>
            <ChatPanel
              messages={messages}
              onSendMessage={chat.sendMessage}
              onAssetUpload={chat.uploadAsset}
              onInterviewAction={chat.handleInterviewAction}
              onTabChange={setWorkbenchTab}
              isLoading={isLoading || chat.isStreaming}
              errorMessage={chat.error}
              className="flex-1 min-h-0"
              pages={pages}
              tokenUsage={costData}
            />
          </div>
          {/* Resize Handle (visual only) */}
          <div className="w-px bg-border hover:bg-accent cursor-col-resize active:cursor-col-resize" />
          {/* Workbench Panel - remaining space */}
          <div className="flex-1 min-w-0">
            <WorkbenchPanel
              sessionId={sessionId ?? ''}
              activeTab={workbenchTab}
              onTabChange={setWorkbenchTab}
              appMode={appMode}
              onAppModeChange={setAppMode}
              previewMode={previewMode}
              onPreviewModeChange={setPreviewMode}
              onBuildFromDoc={handleBuildFromDoc}
              buildDisabled={chat.isStreaming || isBuildRunning || isBuildLoading}
              previewVersion={previewVersionLabel}
              productDocVersion={productDoc?.version ?? null}
              productDoc={productDoc}
              isProductDocLoading={isProductDocLoading}
              productDocError={productDocError}
              pages={pages}
              selectedPageId={selectedPageId}
              onSelectPage={handleSelectPage}
              previewHtml={previewHtml}
              previewUrl={previewUrl}
              buildPreviewUrl={buildPreviewUrl}
              isRefreshing={isRefreshing}
              isExporting={isExporting}
              onRefresh={handleRefreshPreview}
              onRefreshPage={handleRefreshPage}
              onExport={handleExportPreview}
              aestheticScore={aestheticScore}
              buildState={buildState}
              onBuildRetry={handleBuildRetry}
              onBuildCancel={handleBuildCancel}
              onBuildPageSelect={handleBuildPageSelect}
              selectedBuildPage={selectedBuildPage}
            />
          </div>
        </div>

        {/* Version Panel - fixed width on right */}
        <VersionPanel
          sessionId={sessionId}
          sessionTitle={session?.title ?? null}
          selectedPageId={selectedPageId}
          selectedPageTitle={pages.find((p) => p.id === selectedPageId)?.title ?? null}
          activeTab={workbenchTab}
          isCollapsed={isVersionPanelCollapsed}
          onToggleCollapse={() => setIsVersionPanelCollapsed((prev) => !prev)}
        />
      </div>
    </div>
  )
}
