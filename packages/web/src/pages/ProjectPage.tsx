import * as React from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Activity, ArrowLeft, Code, Database, FileText, History, Settings } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ChatPanel } from '@/components/custom/ChatPanel'
import type { WorkbenchTab } from '@/components/custom/WorkbenchPanel'
import { ThreadSelector } from '@/components/custom/ThreadSelector'
import { AbortDialog } from '@/components/custom/AbortDialog'
import { AppLayout, ContentArea, PageHeader } from '@/components/Layout'
import { ResizableSplitPane } from '@/components/Layout/ResizableSplitPane'
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

const WorkbenchPanel = React.lazy(() =>
  import('@/components/custom/WorkbenchPanel').then((module) => ({
    default: module.WorkbenchPanel,
  }))
)
const VersionPanel = React.lazy(() =>
  import('@/components/custom/VersionPanel').then((module) => ({
    default: module.VersionPanel,
  }))
)
const CodeDrawer = React.lazy(() =>
  import('@/components/custom/CodeDrawer').then((module) => ({
    default: module.CodeDrawer,
  }))
)
const DocDrawer = React.lazy(() =>
  import('@/components/custom/DocDrawer').then((module) => ({
    default: module.DocDrawer,
  }))
)
const DataDrawer = React.lazy(() =>
  import('@/components/custom/DataDrawer').then((module) => ({
    default: module.DataDrawer,
  }))
)

function PanelFallback({ label }: { label: string }) {
  return (
    <div className="flex h-full min-h-0 items-center justify-center bg-background text-sm text-muted-foreground">
      {label}
    </div>
  )
}

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
  const [isCodeDrawerOpen, setIsCodeDrawerOpen] = React.useState(false)
  const [isDocDrawerOpen, setIsDocDrawerOpen] = React.useState(false)
  const [isDataDrawerOpen, setIsDataDrawerOpen] = React.useState(false)
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

  const handleOpenBuildPreview = React.useCallback(() => {
    setWorkbenchTab('preview')
    setPreviewMode('build')
  }, [])

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
    <AppLayout className="h-screen min-h-0 min-w-0 overflow-hidden animate-in fade-in">
      <PageHeader
        className="min-w-0 shrink-0 flex-wrap gap-2 px-3 py-3 sm:flex-nowrap sm:px-6 sm:py-4"
        leading={
          <Button variant="ghost" size="icon" className="shrink-0" asChild aria-label="Back to home">
            <Link to="/">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
        }
        title={session?.title ?? `Project ${id ?? 'Untitled'}`}
        trailing={
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-1 sm:flex-nowrap sm:gap-2">
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0"
            onClick={() => setIsCodeDrawerOpen(true)}
            disabled={!sessionId}
            aria-label="Open code drawer"
          >
            <Code className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0"
            onClick={() => setIsDocDrawerOpen(true)}
            disabled={!sessionId}
            aria-label="Open product doc drawer"
          >
            <FileText className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0"
            onClick={() => setIsDataDrawerOpen(true)}
            disabled={!sessionId}
            aria-label="Open data and more drawer"
          >
            <Database className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0"
            onClick={() => setIsVersionPanelCollapsed((prev) => !prev)}
            disabled={!sessionId}
            aria-label="Toggle versions panel"
          >
            <History className="h-4 w-4" />
          </Button>
          {sessionId ? (
            <Button variant="ghost" size="icon" className="shrink-0" asChild aria-label="Execution flow">
              <Link to={`/project/${sessionId}/flow`}>
                <Activity className="h-4 w-4" />
              </Link>
            </Button>
          ) : null}
          <Button variant="ghost" size="icon" className="shrink-0" asChild aria-label="Open settings">
            <Link to="/settings">
              <Settings className="h-4 w-4" />
            </Link>
          </Button>
        </div>
        }
      />

      <ContentArea className="flex min-h-0 flex-col overflow-hidden lg:flex-row">
        <main className="flex min-h-0 min-w-0 flex-1">
          {error ? (
            <div className="mx-auto max-w-3xl p-6 text-sm text-destructive">
              {error}
            </div>
          ) : null}
          <ResizableSplitPane
            className="flex-1"
            leftClassName="bg-background"
            rightClassName="bg-background"
            left={
              <div className="flex h-full min-w-0 flex-col">
                <div className="flex min-h-16 shrink-0 flex-wrap items-center gap-2 border-b border-border px-2 py-2 sm:flex-nowrap sm:px-3">
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
                  <div className="flex shrink-0 items-center gap-0.5">
                    <AbortDialog disabled={!canAbort} onAbort={handleAbort} />
                  </div>
                </div>
                <ChatPanel
                  messages={messages}
                  sessionId={sessionId}
                  onSendMessage={chat.sendMessage}
                  onAssetUpload={chat.uploadAsset}
                  onInterviewAction={chat.handleInterviewAction}
                  onTabChange={setWorkbenchTab}
                  onOpenBuildPreview={handleOpenBuildPreview}
                  isLoading={isLoading || chat.isStreaming}
                  errorMessage={chat.error}
                  runStatus={chat.runStatus}
                  className="min-h-0 flex-1"
                  pages={pages}
                  tokenUsage={costData}
                />
              </div>
            }
            right={
              <React.Suspense fallback={<PanelFallback label="Loading workspace..." />}>
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
              </React.Suspense>
            }
          />
        </main>

        <aside className="min-h-40 shrink-0 border-t border-border lg:h-auto lg:border-l-0 lg:border-t-0 [&>div]:w-full lg:[&>div]:w-80">
          <React.Suspense fallback={<PanelFallback label="Loading versions..." />}>
            <VersionPanel
              sessionId={sessionId}
              sessionTitle={session?.title ?? null}
              selectedPageId={selectedPageId}
              selectedPageTitle={pages.find((p) => p.id === selectedPageId)?.title ?? null}
              activeTab={workbenchTab}
              isCollapsed={isVersionPanelCollapsed}
              onToggleCollapse={() => setIsVersionPanelCollapsed((prev) => !prev)}
            />
          </React.Suspense>
        </aside>
      </ContentArea>

      {sessionId ? (
        <React.Suspense fallback={null}>
          <CodeDrawer
            open={isCodeDrawerOpen}
            onOpenChange={setIsCodeDrawerOpen}
            sessionId={sessionId}
          />
          <DocDrawer
            open={isDocDrawerOpen}
            onOpenChange={setIsDocDrawerOpen}
            sessionId={sessionId}
            onBuild={handleBuildFromDoc}
            buildDisabled={chat.isStreaming || isBuildRunning || isBuildLoading}
            productDoc={productDoc}
            isLoading={isProductDocLoading}
            error={productDocError}
          />
          <DataDrawer
            open={isDataDrawerOpen}
            onOpenChange={setIsDataDrawerOpen}
            sessionId={sessionId}
          />
        </React.Suspense>
      ) : null}
    </AppLayout>
  )
}
