import * as React from 'react'
import { RefreshCw, Download, Loader2, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { cn } from '@/lib/utils'
import { APP_MODE_SOURCE, injectAppModeRuntime } from '@/lib/appModeRuntime'
import { api } from '@/api/client'
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
  pending: 'bg-warning-muted text-warning-muted-foreground',
  building: 'bg-info-muted text-info-muted-foreground',
  success: 'bg-success-muted text-success-muted-foreground',
  failed: 'bg-danger-muted text-danger-muted-foreground',
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
  onMentionPage?: (page: PageInfo) => void
  onRefreshPage?: (pageId: string) => void
}

interface LiveLinkConnector {
  id: string
  sourcePageId: string
  targetPageId: string
  color: string
  x1: number
  y1: number
  x2: number
  y2: number
}

const CONNECTOR_COLORS = [
  '#dc2626',
  '#2563eb',
  '#16a34a',
  '#d97706',
  '#7c3aed',
  '#0891b2',
  '#be123c',
  '#4f46e5',
]

const stableColor = (value: string) => {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0
  }
  return CONNECTOR_COLORS[hash % CONNECTOR_COLORS.length]
}

const normalizeLinkSlug = (href: string, knownSlugs: Set<string>) => {
  const trimmed = href.trim()
  if (!trimmed || trimmed.startsWith('#')) return null

  let url: URL
  try {
    url = new URL(trimmed, window.location.origin)
  } catch {
    return null
  }

  if (url.origin !== window.location.origin) return null

  const path = decodeURIComponent(url.pathname)
    .replace(/^\/+|\/+$/g, '')
    .replace(/\\/g, '/')
  if (!path) return knownSlugs.has('index') ? 'index' : null

  const withoutHtml = path.replace(/\.html$/i, '')
  const candidates = new Set<string>()
  candidates.add(withoutHtml)
  candidates.add(withoutHtml.replace(/^pages\//, '').replace(/\/index$/i, ''))
  candidates.add(withoutHtml.replace(/\/index$/i, ''))

  if (/^index$/i.test(withoutHtml)) {
    candidates.add('index')
  }

  for (const candidate of candidates) {
    const normalized = candidate.replace(/^\/+|\/+$/g, '')
    if (knownSlugs.has(normalized)) return normalized
  }
  return null
}

interface LivePageMapProps {
  pages: PageInfo[]
  refreshKey: number
  onSelectPage?: (pageId: string) => void
  onMentionPage?: (page: PageInfo) => void
}

function LivePageMap({ pages, refreshKey, onSelectPage, onMentionPage }: LivePageMapProps) {
  const mapRef = React.useRef<HTMLDivElement | null>(null)
  const frameRefs = React.useRef(new Map<string, HTMLDivElement>())
  const iframeRefs = React.useRef(new Map<string, HTMLIFrameElement>())
  const [connectors, setConnectors] = React.useState<LiveLinkConnector[]>([])
  const [overlaySize, setOverlaySize] = React.useState({ width: 0, height: 0 })
  const [htmlByPageId, setHtmlByPageId] = React.useState<Record<string, string>>({})

  const pageBySlug = React.useMemo(() => {
    const map = new Map<string, PageInfo>()
    for (const page of pages) {
      map.set(page.slug, page)
    }
    return map
  }, [pages])

  React.useEffect(() => {
    let cancelled = false
    const loadPreviews = async () => {
      const entries = await Promise.all(
        pages.map(async (page) => {
          try {
            const preview = await api.pages.getPreview(page.id)
            return [page.id, preview.html] as const
          } catch {
            return [page.id, EMPTY_PREVIEW_HTML] as const
          }
        })
      )
      if (cancelled) return
      setHtmlByPageId(Object.fromEntries(entries))
    }

    void loadPreviews()
    return () => {
      cancelled = true
    }
  }, [pages, refreshKey])

  const measureConnectors = React.useCallback(() => {
    const mapEl = mapRef.current
    if (!mapEl) return

    const mapRect = mapEl.getBoundingClientRect()
    const knownSlugs = new Set(pageBySlug.keys())
    const next: LiveLinkConnector[] = []

    for (const page of pages) {
      const iframe = iframeRefs.current.get(page.id)
      if (!iframe) continue

      let doc: Document | null = null
      try {
        doc = iframe.contentDocument
      } catch {
        doc = null
      }
      if (!doc) continue

      const iframeRect = iframe.getBoundingClientRect()
      const links = Array.from(doc.querySelectorAll<HTMLAnchorElement>('a[href]'))

      links.forEach((link, index) => {
        const href = link.getAttribute('href') ?? ''
        const targetSlug = normalizeLinkSlug(href, knownSlugs)
        if (!targetSlug) return

        const targetPage = pageBySlug.get(targetSlug)
        if (!targetPage || targetPage.id === page.id) return

        const targetFrame = frameRefs.current.get(targetPage.id)
        if (!targetFrame) return

        const linkRect = link.getBoundingClientRect()
        if (linkRect.width === 0 || linkRect.height === 0) return

        const targetRect = targetFrame.getBoundingClientRect()
        const sourceX = iframeRect.left - mapRect.left + mapEl.scrollLeft + linkRect.left + linkRect.width / 2
        const sourceY = iframeRect.top - mapRect.top + mapEl.scrollTop + linkRect.top + linkRect.height / 2
        const targetX = targetRect.left - mapRect.left + mapEl.scrollLeft + targetRect.width / 2
        const targetY = targetRect.top - mapRect.top + mapEl.scrollTop + 18
        const id = `${page.id}:${targetPage.id}:${index}:${href}`

        next.push({
          id,
          sourcePageId: page.id,
          targetPageId: targetPage.id,
          color: stableColor(id),
          x1: sourceX,
          y1: sourceY,
          x2: targetX,
          y2: targetY,
        })
      })
    }

    setOverlaySize({ width: mapEl.scrollWidth, height: mapEl.scrollHeight })
    setConnectors(next)
  }, [pageBySlug, pages])

  React.useEffect(() => {
    const mapEl = mapRef.current
    if (!mapEl) return

    const observer = new ResizeObserver(measureConnectors)
    observer.observe(mapEl)
    for (const frame of frameRefs.current.values()) {
      observer.observe(frame)
    }

    window.addEventListener('resize', measureConnectors)
    mapEl.addEventListener('scroll', measureConnectors, { passive: true })

    measureConnectors()

    return () => {
      observer.disconnect()
      window.removeEventListener('resize', measureConnectors)
      mapEl.removeEventListener('scroll', measureConnectors)
    }
  }, [measureConnectors])

  React.useEffect(() => {
    const timeout = window.setTimeout(measureConnectors, 80)
    return () => window.clearTimeout(timeout)
  }, [measureConnectors, refreshKey])

  return (
    <div
      ref={mapRef}
      data-testid="live-page-map"
      className="relative h-full w-full overflow-auto bg-muted/30 p-5 sm:p-8"
    >
      <svg
        data-testid="live-link-overlay"
        className="pointer-events-none absolute left-0 top-0 z-20"
        width={overlaySize.width}
        height={overlaySize.height}
        viewBox={`0 0 ${overlaySize.width} ${overlaySize.height}`}
        aria-hidden="true"
      >
        {connectors.map((connector) => (
          <path
            key={connector.id}
            data-testid="live-link-connector"
            d={`M ${connector.x1} ${connector.y1} C ${connector.x1} ${connector.y1 + 80}, ${connector.x2} ${connector.y2 - 80}, ${connector.x2} ${connector.y2}`}
            fill="none"
            stroke={connector.color}
            strokeWidth={6}
            strokeDasharray="12 10"
            strokeLinecap="round"
            opacity={0.92}
          />
        ))}
      </svg>

      <div className="relative z-10 grid min-w-0 grid-cols-1 justify-items-center gap-x-10 gap-y-12 xl:grid-cols-2 2xl:grid-cols-3">
        {pages.map((page) => {
          const html = htmlByPageId[page.id]
          const srcDoc = html ? injectHideScrollbarStyle(html) : EMPTY_PREVIEW_HTML
          return (
            <div
              key={page.id}
              ref={(node) => {
                if (node) frameRefs.current.set(page.id, node)
                else frameRefs.current.delete(page.id)
              }}
              data-testid="live-page-frame"
              className="flex w-[260px] flex-col items-center gap-3 sm:w-[300px]"
            >
              <div className="relative w-full">
                <PhoneFrame>
                  <iframe
                    ref={(node) => {
                      if (node) iframeRefs.current.set(page.id, node)
                      else iframeRefs.current.delete(page.id)
                    }}
                    title={`${page.title} preview`}
                    data-testid="live-page-iframe"
                    className="h-full w-full border-0"
                    sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
                    srcDoc={srcDoc}
                    onLoad={measureConnectors}
                  />
                  <div className="absolute inset-0 z-10 bg-transparent" aria-hidden="true" />
                </PhoneFrame>
              </div>
              <button
                type="button"
                data-testid="live-page-label"
                className="max-w-full rounded-full border border-border bg-background px-3 py-1.5 text-center text-xs font-semibold text-foreground shadow-sm transition hover:border-primary hover:text-primary"
                onClick={() => {
                  onSelectPage?.(page.id)
                  onMentionPage?.(page)
                }}
              >
                <span className="block truncate">{page.title || page.slug}</span>
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export const PreviewPanel = React.memo(function PreviewPanel({
  sessionId,
  appMode = true,
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
  onMentionPage,
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
  const [liveRefreshKey, setLiveRefreshKey] = React.useState(0)

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
    setCurrentUrl(effectiveAppMode ? null : previewUrl ?? null)
  }, [buildPreviewUrl, effectiveAppMode, htmlContent, previewUrl, isBuildPreview])

  // Reset scroll position when page changes
  React.useEffect(() => {
    if (selectedPageId) {
      setCurrentHtml(null)
      setCurrentUrl(null)
    }
  }, [selectedPageId])

  const isMultiPage = pages && pages.length > 1
  const showLivePageMap = !isBuildPreview && Boolean(isMultiPage)

  const handleRefresh = React.useCallback(() => {
    if (showLivePageMap) {
      setLiveRefreshKey((key) => key + 1)
      onRefresh?.()
    } else if (isMultiPage && selectedPageId && onRefreshPage) {
      onRefreshPage(selectedPageId)
    } else if (onRefresh) {
      onRefresh()
    }
  }, [isMultiPage, selectedPageId, onRefreshPage, onRefresh, showLivePageMap])

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
    <div className="flex h-full flex-col" data-testid="preview-panel">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-3 py-3 sm:px-6 sm:py-4">
        <div className="flex min-w-0 items-center gap-3 sm:gap-4">
          <span className="truncate text-sm font-semibold text-foreground">{previewLabel}</span>
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
        <div className="flex max-w-full items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
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
          <Button
            variant="ghost"
            size="icon"
            onClick={handleRefresh}
            aria-label="Refresh preview"
            disabled={isRefreshing || !onRefresh}
            className="shrink-0"
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
            className="shrink-0"
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
          {isMultiPage && onSelectPage && !showLivePageMap && (
            <PageSelector
              pages={pages}
              selectedPageId={selectedPageId ?? null}
              onSelectPage={onSelectPage}
            />
          )}

          <div
            ref={containerRef}
            className="flex flex-1 items-center justify-center bg-muted/30 p-3 sm:p-6"
          >
            {showLivePageMap && pages ? (
              <LivePageMap
                pages={pages}
                refreshKey={liveRefreshKey}
                onSelectPage={onSelectPage}
                onMentionPage={onMentionPage}
              />
            ) : (
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
                      Run a build to generate the preview.
                    </span>
                  </div>
                </div>
              ) : (
                <iframe
                  ref={iframeRef}
                  key={`${selectedPageId ?? 'preview'}-${previewMode}-${effectiveAppMode ? 'app' : 'static'}`}
                  title="Preview"
                  data-testid="preview-iframe"
                  className="h-full w-full border-0"
                  sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
                  onLoad={sendStateToIframe}
                  src={currentUrl ?? undefined}
                  srcDoc={currentUrl ? undefined : htmlValue}
                />
              )}
            </PhoneFrame>
            )}
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
