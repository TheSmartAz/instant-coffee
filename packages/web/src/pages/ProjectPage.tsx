import * as React from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Settings, Activity } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { ChatPanel } from '@/components/custom/ChatPanel'
import { PreviewPanel } from '@/components/custom/PreviewPanel'
import { VersionPanel } from '@/components/custom/VersionPanel'
import { EventList } from '@/components/EventFlow/EventList'
import { api } from '@/api/client'
import { useChat } from '@/hooks/useChat'
import { useSSE } from '@/hooks/useSSE'
import { useSession } from '@/hooks/useSession'
import { toast } from '@/hooks/use-toast'

const fallbackHtml = `
<!doctype html>
<html>
  <head>
    <style>
      body { margin: 0; font-family: Inter, sans-serif; background: #fff; }
      .hero { padding: 32px 20px; background: #f4f4f5; }
      .hero h1 { font-size: 28px; margin-bottom: 12px; }
      .card { margin: 16px 20px; padding: 16px; border: 1px solid #e4e4e7; border-radius: 16px; }
      .cta { margin-top: 16px; padding: 12px; background: #18181b; color: #fff; text-align: center; border-radius: 12px; }
    </style>
  </head>
  <body>
    <section class="hero">
      <h1>Drip & Bloom</h1>
      <p>Slow mornings, bold flavors, and a seat waiting for you.</p>
      <div class="cta">Book a table</div>
    </section>
    <div class="card">Daily Roast · Ethiopia Sidamo</div>
    <div class="card">Pastry Pairings · Almond croissant</div>
  </body>
</html>
`

export function ProjectPage() {
  const { id } = useParams()
  const [isVersionPanelCollapsed, setIsVersionPanelCollapsed] = React.useState(false)
  const [actionError, setActionError] = React.useState<string | null>(null)
  const [revertingId, setRevertingId] = React.useState<string | null>(null)
  const [isRefreshing, setIsRefreshing] = React.useState(false)
  const [isExporting, setIsExporting] = React.useState(false)
  const [activeTab, setActiveTab] = React.useState<'chat' | 'events'>('chat')
  const sessionId = id && id !== 'new' ? id : undefined
  const { session, messages, versions, isLoading, error, refresh, setMessages } =
    useSession(sessionId)
  const [previewHtml, setPreviewHtml] = React.useState(fallbackHtml)
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null)
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
      }
      if (isHttpUrl(payload.previewUrl)) {
        setPreviewUrl(payload.previewUrl)
      }
    },
  })

  const sse = useSSE({
    url: sessionId ? api.chat.streamUrl(sessionId) : '',
    autoConnect: activeTab === 'events' && Boolean(sessionId),
    onError: (err) => {
      toast({ title: 'SSE connection error', description: err.message })
    },
  })
  const { clearEvents } = sse

  const currentVersion = versions.find((version) => version.isCurrent) ?? versions[0]
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
    if (session?.previewHtml) {
      setPreviewHtml(session.previewHtml)
      setPreviewUrl(null)
      return
    }
    if (isHttpUrl(session?.previewUrl)) {
      setPreviewUrl(session.previewUrl)
    }
  }, [isHttpUrl, session?.previewHtml, session?.previewUrl])

  React.useEffect(() => {
    const active = versions.find((version) => version.isCurrent)
    if (active?.previewHtml) {
      setPreviewHtml(active.previewHtml)
      setPreviewUrl(null)
      return
    }
    if (isHttpUrl(active?.previewUrl)) {
      setPreviewUrl(active.previewUrl)
    }
  }, [isHttpUrl, versions])

  const handleSelectVersion = (versionId: string) => {
    const selected = versions.find((version) => version.id === versionId)
    if (!selected) return
    if (selected.previewHtml) {
      setPreviewHtml(selected.previewHtml)
      setPreviewUrl(null)
      return
    }
    if (isHttpUrl(selected.previewUrl)) {
      setPreviewUrl(selected.previewUrl)
      return
    }
    setPreviewHtml(fallbackHtml)
    setPreviewUrl(null)
  }

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
    setIsExporting(true)
    try {
      toast({ title: 'Export not available yet', description: 'Export API will be added later.' })
    } finally {
      setIsExporting(false)
    }
  }

  const handleRevertVersion = async (versionId: string) => {
    if (!sessionId) return
    setActionError(null)
    setRevertingId(versionId)
    try {
      const target = versions.find((version) => version.id === versionId)
      const response = (await api.sessions.revert(
        sessionId,
        target?.number ?? versionId
      )) as { preview_url?: string | null; preview_html?: string | null }
      if (response?.preview_html) {
        setPreviewHtml(response.preview_html)
        setPreviewUrl(null)
      } else if (response?.preview_url && isHttpUrl(response.preview_url)) {
        setPreviewUrl(response.preview_url)
      }
      await refresh()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to revert version'
      setActionError(message)
      toast({ title: 'Version revert failed', description: message })
    } finally {
      setRevertingId(null)
    }
  }

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
          {error || actionError ? (
            <div className="mx-auto max-w-3xl p-6 text-sm text-destructive">
              {error ?? actionError}
            </div>
          ) : null}
          {/* Chat Panel - 35% */}
          <div className="flex flex-col border-r border-border w-[35%] max-w-[45%] min-w-[300px]">
            <Tabs
              value={activeTab}
              onValueChange={(value) => setActiveTab(value as 'chat' | 'events')}
              className="flex h-full flex-col"
            >
              <div className="flex items-center justify-between border-b border-border px-4 py-2 shrink-0">
                <TabsList>
                  <TabsTrigger value="chat">Chat</TabsTrigger>
                  <TabsTrigger value="events">Events</TabsTrigger>
                </TabsList>
                <span className="text-xs text-muted-foreground">
                  {activeTab === 'chat' ? chatStatus : eventStatus}
                </span>
              </div>
              <TabsContent value="chat" className="mt-0 flex-1 min-h-0">
                <ChatPanel
                  messages={messages}
                  onSendMessage={chat.sendMessage}
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
          {/* Preview Panel - remaining space */}
          <div className="flex-1 min-w-0">
            <PreviewPanel
              htmlContent={previewHtml}
              previewUrl={previewUrl}
              onRefresh={handleRefreshPreview}
              onExport={handleExportPreview}
              isRefreshing={isRefreshing}
              isExporting={isExporting}
            />
          </div>
        </div>

        {/* Version Panel - fixed width on right */}
        <VersionPanel
          versions={versions}
          currentVersionId={currentVersion?.id ?? ''}
          onSelectVersion={handleSelectVersion}
          onRevertVersion={handleRevertVersion}
          isCollapsed={isVersionPanelCollapsed}
          onToggleCollapse={() => setIsVersionPanelCollapsed((prev) => !prev)}
          isLoading={isLoading}
          revertingId={revertingId}
        />
      </div>
    </div>
  )
}
