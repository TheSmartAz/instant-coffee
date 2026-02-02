import * as React from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Settings, Activity, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { ChatPanel } from '@/components/custom/ChatPanel'
import { WorkbenchPanel, type WorkbenchTab } from '@/components/custom/WorkbenchPanel'
import { VersionPanel } from '@/components/custom/VersionPanel'
import { EventList } from '@/components/EventFlow/EventList'
import { api, type RequestError } from '@/api/client'
import { useChat } from '@/hooks/useChat'
import { useSSE } from '@/hooks/useSSE'
import { useSession } from '@/hooks/useSession'
import { usePages } from '@/hooks/usePages'
import { useProductDoc } from '@/hooks/useProductDoc'
import { toast } from '@/hooks/use-toast'

export function ProjectPage() {
  const { id } = useParams()
  const [isVersionPanelCollapsed, setIsVersionPanelCollapsed] = React.useState(false)
  const [isRefreshing, setIsRefreshing] = React.useState(false)
  const [isExporting, setIsExporting] = React.useState(false)
  const [activeTab, setActiveTab] = React.useState<'chat' | 'events'>('chat')
  const [workbenchTab, setWorkbenchTab] = React.useState<WorkbenchTab>('preview')
  const [appMode, setAppMode] = React.useState(false)
  const sessionId = id && id !== 'new' ? id : undefined
  const { session, messages, versions, isLoading, error, refresh, setMessages } =
    useSession(sessionId)

  const [previewHtml, setPreviewHtml] = React.useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null)
  const autoLoadedPreviewRef = React.useRef<Set<string>>(new Set())

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
    onPagePreviewReady: (pageId, payload) => {
      // Load preview when ready
      if (pageId === selectedPageId) {
        if (appMode) {
          void loadPagePreview(pageId, { bustCache: true })
          return
        }
        if (payload.previewUrl) {
          setPreviewUrl(payload.previewUrl)
          setPreviewHtml(null)
        } else if (payload.html) {
          setPreviewHtml(payload.html)
          setPreviewUrl(null)
        }
      }
    },
  })
  const hasPages = pages.length > 0
  const [hasLoadedPages, setHasLoadedPages] = React.useState(false)
  const hasRequestedPagesRef = React.useRef(false)

  // ProductDoc state management - auto-switch on events
  useProductDoc(sessionId, {
    onProductDocGenerated: () => {
      setWorkbenchTab('product-doc')
    },
    onProductDocUpdated: () => {
      setWorkbenchTab('product-doc')
    },
  })

  const buildPagePreviewUrl = React.useCallback(
    (pageId: string, options?: { bustCache?: boolean }) => {
      const baseUrl = api.pages.previewUrl(pageId)
      if (!options?.bustCache) return baseUrl
      return `${baseUrl}${baseUrl.includes('?') ? '&' : '?'}t=${Date.now()}`
    },
    []
  )

  // Function to load page preview (prefer preview_url)
  const loadPagePreview = React.useCallback(
    async (pageId: string, options?: { bustCache?: boolean }) => {
      try {
        const preview = await api.pages.getPreview(pageId)
        if (appMode) {
          setPreviewHtml(preview.html ?? null)
          setPreviewUrl(null)
          return
        }
        const previewUrl = buildPagePreviewUrl(pageId, options)
        setPreviewUrl(previewUrl)
        setPreviewHtml(null)
      } catch (err) {
        const status = (err as RequestError)?.status
        if (status === 404) {
          setPreviewHtml(null)
          setPreviewUrl(null)
          return
        }
        console.error('Failed to load page preview:', err)
      }
    },
    [appMode, buildPagePreviewUrl]
  )
  const isHttpUrl = React.useCallback(
    (value?: string | null) => (value ? /^https?:\/\//i.test(value) : false),
    []
  )
  const chat = useChat({
    sessionId,
    messages,
    setMessages,
    onPreview: (payload) => {
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

  const sse = useSSE({
    url: sessionId ? api.chat.streamUrl(sessionId) : '',
    sessionId,
    autoConnect: activeTab === 'events' && Boolean(sessionId),
    loadHistory: activeTab === 'events' && Boolean(sessionId),
    onError: (err) => {
      toast({ title: 'SSE connection error', description: err.message })
    },
  })
  const { clearEvents } = sse

  const chatStatus = chat.isStreaming
    ? 'Streaming'
    : chat.connectionState === 'open'
      ? 'Live'
      : chat.connectionState === 'connecting'
        ? 'Connecting'
        : chat.connectionState === 'error'
          ? 'Connection lost'
          : undefined
  const eventStatus =
    sse.connectionState === 'open'
      ? 'Live'
      : sse.connectionState === 'connecting'
        ? 'Connecting'
        : sse.connectionState === 'error'
          ? 'Connection lost'
          : undefined

  React.useEffect(() => {
    setActiveTab('chat')
    clearEvents()
  }, [sessionId, clearEvents])

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
  }, [
    hasLoadedPages,
    hasPages,
    isHttpUrl,
    session?.previewHtml,
    session?.previewUrl,
  ])

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

  React.useEffect(() => {
    if (!hasPages) return
    if (previewUrl && previewUrl.includes('/api/sessions/')) {
      setPreviewUrl(null)
    }
  }, [hasPages, previewUrl])

  React.useEffect(() => {
    if (!selectedPageId) return
    if (previewUrl || previewHtml) return
    if (autoLoadedPreviewRef.current.has(selectedPageId)) return
    autoLoadedPreviewRef.current.add(selectedPageId)
    void loadPagePreview(selectedPageId)
  }, [selectedPageId, previewUrl, previewHtml, loadPagePreview])

  React.useEffect(() => {
    if (!selectedPageId) return
    void loadPagePreview(selectedPageId, { bustCache: true })
  }, [appMode, loadPagePreview, selectedPageId])

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

  React.useEffect(() => {
    if (!sessionId) return
    try {
      const key = `instant-coffee:app-mode:${sessionId}`
      window.localStorage.setItem(key, appMode ? 'true' : 'false')
    } catch {
      // ignore storage failures
    }
  }, [appMode, sessionId])

  const handleRefreshPreview = async () => {
    if (!sessionId) return
    setIsRefreshing(true)
    try {
      const ok = await refresh()
      if (ok) {
        toast({ title: 'Preview refreshed' })
      } else {
        toast({ title: 'Refresh failed', description: 'Unable to reload session.' })
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to refresh preview'
      toast({ title: 'Refresh failed', description: message })
    } finally {
      setIsRefreshing(false)
    }
  }

  const handleExportPreview = async () => {
    if (!sessionId) return
    setIsExporting(true)
    try {
      const result = await api.export.session(sessionId)
      if (result.success) {
        const successCount = result.manifest.pages.filter((p) => p.status === 'success').length
        const failedCount = result.manifest.pages.filter((p) => p.status === 'failed').length

        let message = `Export succeeded! ${successCount} pages exported to ${result.export_dir}`
        if (failedCount > 0) {
          message += ` (${failedCount} pages failed)`
        }
        toast({ title: 'Export complete', description: message })
      } else {
        toast({ title: 'Export failed', description: 'Check the console for details.' })
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Export failed. Please retry.'
      toast({ title: 'Export failed', description: message })
    } finally {
      setIsExporting(false)
    }
  }

  const canClearChat = Boolean(sessionId) && (messages.length > 0 || chat.isStreaming)

  const handleClearChat = async () => {
    if (!sessionId) return
    try {
      await chat.clearThread()
      toast({ title: 'Chat cleared' })
    } catch {
      // Error toast handled in hook
    }
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
      setIsRefreshing(true)
      try {
        await loadPagePreview(pageId, { bustCache: true })
        toast({ title: 'Page preview refreshed' })
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to refresh page preview'
        toast({ title: 'Refresh failed', description: message })
      } finally {
        setIsRefreshing(false)
      }
    },
    [loadPagePreview]
  )

  const handleBuildFromDoc = React.useCallback(() => {
    if (!sessionId) return
    void chat.sendMessage('Start building', { generateNow: true })
  }, [chat.sendMessage, sessionId])

  return (
    <div className="flex h-screen flex-col animate-in fade-in">
      <header className="flex items-center justify-between border-b border-border px-6 py-4 shrink-0">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" asChild>
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
          <Button variant="ghost" size="icon" asChild>
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
            <Tabs
              value={activeTab}
              onValueChange={(value) => setActiveTab(value as 'chat' | 'events')}
              className="flex h-full flex-col"
            >
              <div className="flex h-14 items-center justify-between border-b border-border px-4 shrink-0">
                <TabsList>
                  <TabsTrigger value="chat">Chat</TabsTrigger>
                  <TabsTrigger value="events">Events</TabsTrigger>
                </TabsList>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    {activeTab === 'chat' ? chatStatus : eventStatus}
                  </span>
                  {activeTab === 'chat' ? (
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          disabled={!canClearChat}
                          aria-label="Clear chat"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Clear chat?</AlertDialogTitle>
                          <AlertDialogDescription>
                            This will delete all chat messages for the current session. ProductDoc / Pages / Versions will be kept.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction onClick={handleClearChat}>
                            Clear chat
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  ) : null}
                </div>
              </div>
              <TabsContent value="chat" className="mt-0 flex-1 min-h-0">
                <ChatPanel
                  messages={messages}
                  onSendMessage={chat.sendMessage}
                  onInterviewAction={chat.handleInterviewAction}
                  onTabChange={setWorkbenchTab}
                  onDisambiguationSelect={(option) => {
                    // Find the page and select it, then send a follow-up message
                    const page = pages.find((p) => p.slug === option.slug)
                    if (page) {
                      selectPage(page.id)
                      void loadPagePreview(page.id)
                      setWorkbenchTab('preview')
                      // Send a follow-up message with the selected page
                      void chat.sendMessage(`I choose: ${option.title}`)
                    }
                  }}
                  isLoading={isLoading || chat.isStreaming}
                  title={session?.title ?? 'Chat'}
                  status={chatStatus}
                  errorMessage={chat.error}
                  showHeader={false}
                  showBorder={false}
                  className="h-full"
                />
              </TabsContent>
              <TabsContent value="events" className="mt-0 flex-1 min-h-0">
                <EventList
                  events={sse.events}
                  isLoading={sse.isLoading}
                  className="h-full"
                  emptyMessage="Waiting for execution events..."
                />
              </TabsContent>
            </Tabs>
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
              onBuildFromDoc={handleBuildFromDoc}
              buildDisabled={chat.isStreaming}
              pages={pages}
              selectedPageId={selectedPageId}
              onSelectPage={handleSelectPage}
              previewHtml={previewHtml}
              previewUrl={previewUrl}
              isRefreshing={isRefreshing}
              isExporting={isExporting}
              onRefresh={handleRefreshPreview}
              onRefreshPage={handleRefreshPage}
              onExport={handleExportPreview}
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
