import * as React from 'react'
import { RefreshCw, Download, Loader2, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { cn } from '@/lib/utils'
import { APP_MODE_SOURCE, injectAppModeRuntime } from '@/lib/appModeRuntime'
import { PhoneFrame } from './PhoneFrame'
import { PageSelector } from './PageSelector'
import { AestheticScoreCard } from './AestheticScoreCard'
import type { AestheticScore } from '@/types/aesthetic'
import type { BuildState, BuildStatusType } from '@/types/build'

const HIDE_SCROLLBAR_STYLE = `<style id="ic-hide-scrollbar">
html, body {
  height: 100%;
  overflow: auto;
  -ms-overflow-style: none;
  scrollbar-width: none;
}
html::-webkit-scrollbar,
body::-webkit-scrollbar {
  width: 0;
  height: 0;
  display: none;
}
</style>`

const injectHideScrollbarStyle = (html: string) => {
  if (!html) return html
  if (html.includes('id="ic-hide-scrollbar"')) return html
  if (html.includes('</head>')) {
    return html.replace('</head>', `${HIDE_SCROLLBAR_STYLE}</head>`)
  }
  if (/<head[^>]*>/i.test(html)) {
    return html.replace(/<head[^>]*>/i, (match) => `${match}${HIDE_SCROLLBAR_STYLE}`)
  }
  return `${HIDE_SCROLLBAR_STYLE}${html}`
}

const BUILD_STATUS_LABELS: Record<BuildStatusType, string> = {
  idle: 'Ready',
  pending: 'Pending',
  building: 'Building',
  success: 'Complete',
  failed: 'Failed',
}

const BUILD_STATUS_TONES: Record<BuildStatusType, string> = {
  idle: 'bg-muted text-muted-foreground',
  pending: 'bg-amber-100 text-amber-700',
  building: 'bg-blue-100 text-blue-700',
  success: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-rose-100 text-rose-700',
}


const EMPTY_PREVIEW_HTML = `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      :root {
        color-scheme: light;
      }
      html, body {
        height: 100%;
        margin: 0;
      }
      body {
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: #ffffff;
        color: #111827;
      }
      .wrap {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 10px;
      }
      .logo {
        width: 40px;
        height: 40px;
        color: #d97706;
      }
      .text {
        font-size: 16px;
        font-weight: 600;
        letter-spacing: 0.2px;
      }
    </style>
  </head>
  <body>
    <div class="wrap">
      <svg class="logo" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M10 2v2" />
        <path d="M14 2v2" />
        <path d="M6 8h11a4 4 0 0 1 0 8H7a4 4 0 0 1 0-8" />
        <path d="M5 8h12v5a6 6 0 0 1-6 6H8a6 6 0 0 1-6-6V8z" />
      </svg>
      <div class="text">Instant Coffee</div>
    </div>
  </body>
</html>`

export interface PageInfo {
  id: string
  title: string
  slug: string
}

export interface PreviewPanelProps {
  sessionId?: string
  appMode?: boolean
  onAppModeChange?: (next: boolean) => void
  previewMode?: 'live' | 'build'
  onPreviewModeChange?: (next: 'live' | 'build') => void
  htmlContent?: string
  previewUrl?: string | null
  buildPreviewUrl?: string | null
  onRefresh?: () => void
  onExport?: () => void
  isRefreshing?: boolean
  isExporting?: boolean
  aestheticScore?: AestheticScore | null
  buildState?: BuildState | null
  onBuildRetry?: () => void
  onBuildCancel?: () => void
  onBuildPageSelect?: (page: string) => void
  selectedBuildPage?: string | null
  // Multi-page props (optional)
  pages?: PageInfo[]
  selectedPageId?: string | null
  onSelectPage?: (pageId: string) => void
  onRefreshPage?: (pageId: string) => void
}

export const PreviewPanel = React.memo(function PreviewPanel({
  sessionId,
  appMode = false,
  onAppModeChange,
  previewMode = 'live',
  onPreviewModeChange,
  htmlContent,
  previewUrl,
  buildPreviewUrl,
  onRefresh,
  onExport,
  isRefreshing = false,
  isExporting = false,
  aestheticScore,
  buildState,
  pages,
  selectedPageId,
  onSelectPage,
  onRefreshPage,
}: PreviewPanelProps) {
  const containerRef = React.useRef<HTMLDivElement | null>(null)
  const iframeRef = React.useRef<HTMLIFrameElement | null>(null)
  const [scale, setScale] = React.useState(1)
  const [currentHtml, setCurrentHtml] = React.useState<string | null>(htmlContent ?? null)
  const [currentUrl, setCurrentUrl] = React.useState<string | null>(previewUrl ?? null)
  const [appState, setAppState] = React.useState<Record<string, unknown>>({})
  const scoreStorageKey = sessionId ? `instant-coffee:aesthetic-score:${sessionId}` : null
  const [scoreExpanded, setScoreExpanded] = React.useState(false)
  const buildStatus: BuildStatusType = buildState?.status ?? 'idle'
  const showBuildStatus = Boolean(buildState) && Boolean(sessionId)
  const isBuildActive = buildStatus === 'building' || buildStatus === 'pending'
  const isBuildPreview = previewMode === 'build'
  const effectiveAppMode = appMode && !isBuildPreview

  const storageKey = sessionId ? `instant-coffee:app-state:${sessionId}` : null

  React.useEffect(() => {
    if (!scoreStorageKey) {
      setScoreExpanded(false)
      return
    }
    try {
      const raw = window.localStorage.getItem(scoreStorageKey)
      if (!raw) {
        setScoreExpanded(Boolean(aestheticScore))
        return
      }
      const parsed = JSON.parse(raw)
      if (!parsed || typeof parsed !== 'object') {
        setScoreExpanded(Boolean(aestheticScore))
        return
      }
      setScoreExpanded(Boolean((parsed as { expanded?: boolean }).expanded))
    } catch {
      setScoreExpanded(Boolean(aestheticScore))
    }
  }, [scoreStorageKey, aestheticScore])

  React.useEffect(() => {
    if (!scoreStorageKey) return
    try {
      window.localStorage.setItem(
        scoreStorageKey,
        JSON.stringify({ expanded: scoreExpanded })
      )
    } catch {
      // ignore storage failures
    }
  }, [scoreExpanded, scoreStorageKey])

  React.useEffect(() => {
    if (!storageKey) {
      setAppState({})
      return
    }
    try {
      const raw = window.localStorage.getItem(storageKey)
      if (!raw) {
        setAppState({})
        return
      }
      const parsed = JSON.parse(raw)
      if (!parsed || typeof parsed !== 'object') {
        setAppState({})
        return
      }
      setAppState(parsed as Record<string, unknown>)
    } catch {
      setAppState({})
    }
  }, [storageKey])

  React.useEffect(() => {
    if (!storageKey) return
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(appState))
    } catch {
      // ignore storage failures
    }
  }, [appState, storageKey])
  const injectedHtml = React.useMemo(() => {
    if (!currentHtml) return ''
    const withRuntime = effectiveAppMode ? injectAppModeRuntime(currentHtml) : currentHtml
    return injectHideScrollbarStyle(withRuntime)
  }, [currentHtml, effectiveAppMode])
  const htmlValue = currentHtml?.trim() ? injectedHtml : EMPTY_PREVIEW_HTML

  // Update current preview when props change
  React.useEffect(() => {
    if (isBuildPreview) {
      setCurrentHtml(null)
      setCurrentUrl(buildPreviewUrl ?? null)
      return
    }
    setCurrentHtml(htmlContent ?? null)
  }, [buildPreviewUrl, htmlContent, isBuildPreview])

  React.useEffect(() => {
    if (isBuildPreview) return
    setCurrentUrl(effectiveAppMode ? null : previewUrl ?? null)
  }, [effectiveAppMode, isBuildPreview, previewUrl])

  // Reset scroll position when page changes
  React.useEffect(() => {
    if (selectedPageId) {
      setCurrentHtml(null)
      setCurrentUrl(null)
    }
  }, [selectedPageId])

  const isMultiPage = pages && pages.length > 1

  const handleRefresh = React.useCallback(() => {
    if (isMultiPage && selectedPageId && onRefreshPage) {
      onRefreshPage(selectedPageId)
    } else if (onRefresh) {
      onRefresh()
    }
  }, [isMultiPage, selectedPageId, onRefreshPage, onRefresh])

  const sendStateToIframe = React.useCallback(() => {
    if (!effectiveAppMode) return
    const frame = iframeRef.current
    if (!frame || !frame.contentWindow) return
    frame.contentWindow.postMessage(
      { source: APP_MODE_SOURCE, type: 'ic_state_init', state: appState },
      '*'
    )
  }, [appState, effectiveAppMode])

  React.useEffect(() => {
    if (!effectiveAppMode) return
    const handleMessage = (event: MessageEvent) => {
      const payload = event.data as { source?: string; type?: string; slug?: string; state?: unknown }
      if (!payload || payload.source !== APP_MODE_SOURCE) return
      if (payload.type === 'ic_nav') {
        if (!pages || !onSelectPage || !payload.slug) return
        const target = pages.find((page) => page.slug === payload.slug)
        if (target) {
          onSelectPage(target.id)
        }
        return
      }
      if (payload.type === 'ic_state') {
        if (payload.state && typeof payload.state === 'object') {
          setAppState(payload.state as Record<string, unknown>)
        }
        return
      }
      if (payload.type === 'ic_ready') {
        sendStateToIframe()
      }
    }

    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [effectiveAppMode, onSelectPage, pages, sendStateToIframe])

  React.useEffect(() => {
    if (!effectiveAppMode) return
    sendStateToIframe()
  }, [effectiveAppMode, sendStateToIframe])

  React.useEffect(() => {
    if (!containerRef.current) return

    const updateScale = () => {
      if (!containerRef.current) return
      const width = containerRef.current.clientWidth
      const nextScale = Math.min(1, Math.max(0.6, width / 460))
      setScale(nextScale)
    }

    updateScale()
    const observer = new ResizeObserver(updateScale)
    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  const previewBaseLabel = isBuildPreview ? 'Build output' : 'Preview'
  const previewLabel =
    isMultiPage && selectedPageId
      ? `${previewBaseLabel}: ${pages.find((p) => p.id === selectedPageId)?.title ?? 'Page'}`
      : previewBaseLabel
  const showBuildPlaceholder = isBuildPreview && !currentUrl && !isBuildActive

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-6 py-4">
        <div className="flex items-center gap-4">
          <span className="text-sm font-semibold text-foreground">{previewLabel}</span>
          {showBuildStatus ? (
            <span
              className={cn(
                'rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
                BUILD_STATUS_TONES[buildStatus]
              )}
            >
              {BUILD_STATUS_LABELS[buildStatus]}
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {onPreviewModeChange ? (
            <div className="inline-flex items-center rounded-full border border-border bg-background p-0.5 text-[11px] font-semibold">
              <button
                type="button"
                onClick={() => onPreviewModeChange('live')}
                aria-pressed={!isBuildPreview}
                className={cn(
                  'h-7 rounded-full px-3 transition',
                  !isBuildPreview
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                Live
              </button>
              <button
                type="button"
                onClick={() => onPreviewModeChange('build')}
                aria-pressed={isBuildPreview}
                title={!buildPreviewUrl ? 'Build output not ready yet' : undefined}
                className={cn(
                  'h-7 rounded-full px-3 transition',
                  isBuildPreview
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                Build
              </button>
            </div>
          ) : null}
          {onAppModeChange ? (
            <Button
              type="button"
              size="sm"
              variant={appMode ? 'default' : 'outline'}
              onClick={() => onAppModeChange(!appMode)}
              aria-pressed={appMode}
              disabled={isBuildPreview}
              title={isBuildPreview ? 'App mode is available for live preview only' : undefined}
              className="h-8 w-[96px] rounded-full text-[11px] font-semibold"
            >
              {appMode ? 'App Mode' : 'Static Mode'}
            </Button>
          ) : null}
          <Button
            variant="ghost"
            size="icon"
            onClick={handleRefresh}
            aria-label="Refresh preview"
            disabled={isRefreshing || !onRefresh}
          >
            {isRefreshing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={onExport}
            aria-label="Export preview"
            disabled={isExporting || !onExport}
          >
            {isExporting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      <div className="mt-0 flex-1">
        <div className="flex h-full flex-col">
          {isMultiPage && onSelectPage && (
            <PageSelector
              pages={pages}
              selectedPageId={selectedPageId ?? null}
              onSelectPage={onSelectPage}
            />
          )}

          <div
            ref={containerRef}
            className="flex flex-1 items-center justify-center bg-muted/30 p-6"
          >
            <PhoneFrame scale={scale}>
              {isBuildActive ? (
                <div className="flex h-full w-full items-center justify-center bg-background">
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span className="text-xs">
                      {buildState?.progress?.step ??
                        buildState?.progress?.message ??
                        'Building preview...'}
                    </span>
                  </div>
                </div>
              ) : showBuildPlaceholder ? (
                <div className="flex h-full w-full items-center justify-center bg-background">
                  <div className="flex max-w-[240px] flex-col items-center gap-2 text-center text-muted-foreground">
                    <span className="text-xs font-semibold text-foreground">
                      Build output not available
                    </span>
                    <span className="text-xs">
                      Run a build to generate the static preview.
                    </span>
                  </div>
                </div>
              ) : (
                <iframe
                  ref={iframeRef}
                  key={`${selectedPageId ?? 'preview'}-${previewMode}-${effectiveAppMode ? 'app' : 'static'}`}
                  title="Preview"
                  className="h-full w-full border-0"
                  sandbox="allow-scripts allow-same-origin"
                  onLoad={sendStateToIframe}
                  {...(currentUrl ? { src: currentUrl } : { srcDoc: htmlValue })}
                />
              )}
            </PhoneFrame>
          </div>

          {aestheticScore ? (
            <div className="border-t border-border bg-background">
              <Collapsible open={scoreExpanded} onOpenChange={setScoreExpanded}>
                <div className="flex items-center justify-between px-6 py-3">
                  <div className="flex flex-col">
                    <span className="text-xs font-semibold uppercase text-muted-foreground">
                      Aesthetic score
                    </span>
                    <span className="text-[11px] text-muted-foreground">
                      Overall {Math.round(aestheticScore.overall)} / 100
                    </span>
                  </div>
                  <CollapsibleTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      aria-label={scoreExpanded ? 'Collapse aesthetic score' : 'Expand aesthetic score'}
                    >
                      <ChevronDown
                        className={`h-4 w-4 transition-transform ${scoreExpanded ? 'rotate-180' : ''}`}
                      />
                    </Button>
                  </CollapsibleTrigger>
                </div>
                <CollapsibleContent className="px-6 pb-6">
                  <AestheticScoreCard score={aestheticScore} expanded />
                </CollapsibleContent>
              </Collapsible>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
})

PreviewPanel.displayName = 'PreviewPanel'
