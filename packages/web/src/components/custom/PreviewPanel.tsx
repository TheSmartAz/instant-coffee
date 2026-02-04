import * as React from 'react'
import { RefreshCw, Download, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { DataTab } from './DataTab'
import { PhoneFrame } from './PhoneFrame'
import { PageSelector } from './PageSelector'

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

const APP_MODE_SOURCE = 'ic-app-mode'

const APP_MODE_SCRIPT = `<script id="ic-app-mode-runtime">
(function () {
  var SOURCE = '${APP_MODE_SOURCE}';
  var NAV_EVENT = 'ic_nav';
  var STATE_EVENT = 'ic_state';
  var READY_EVENT = 'ic_ready';
  var STATE_INIT = 'ic_state_init';
  var DATA_EVENT = 'instant-coffee:update';
  var MAX_EVENTS = 100;
  var MAX_RECORDS = 200;
  var appState = {};
  var eventLog = [];
  var recordLog = [];
  var applying = false;

  function isExternalHref(href) {
    if (!href) return true;
    if (href.indexOf('#') === 0) return true;
    if (href.indexOf('//') === 0) return true;
    return /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(href);
  }

  function normalizeSlug(href) {
    if (!href) return null;
    if (isExternalHref(href)) return null;
    var raw = href.split('#')[0].split('?')[0];
    if (!raw) return null;
    if (raw.indexOf('./') === 0) raw = raw.slice(2);
    if (raw.indexOf('/') === 0) raw = raw.slice(1);
    if (raw === 'index' || raw === 'index.html') return 'index';
    if (raw.indexOf('pages/') === 0) raw = raw.slice(6);
    if (raw.slice(-5) === '.html') raw = raw.slice(0, -5);
    if (!raw) return null;
    if (raw.indexOf('/') !== -1) return null;
    return raw;
  }

  function getKey(el) {
    if (!el) return null;
    return el.getAttribute('data-ic-key') || el.name || el.id || null;
  }

  function readValue(el) {
    if (!el) return undefined;
    var tag = el.tagName;
    if (tag === 'INPUT') {
      var type = el.type || 'text';
      if (type === 'checkbox') return !!el.checked;
      if (type === 'radio') return el.checked ? el.value : undefined;
      if (type === 'file') return undefined;
      return el.value;
    }
    if (tag === 'SELECT') {
      if (el.multiple) {
        var values = [];
        for (var i = 0; i < el.options.length; i += 1) {
          var opt = el.options[i];
          if (opt.selected) values.push(opt.value);
        }
        return values;
      }
      return el.value;
    }
    if (tag === 'TEXTAREA') {
      return el.value;
    }
    return undefined;
  }

  function writeValue(el, value) {
    if (value === undefined || value === null) return;
    var tag = el.tagName;
    if (tag === 'INPUT') {
      var type = el.type || 'text';
      if (type === 'checkbox') {
        el.checked = !!value;
        return;
      }
      if (type === 'radio') {
        el.checked = String(value) === el.value;
        return;
      }
      if (type === 'file') return;
      el.value = String(value);
      return;
    }
    if (tag === 'SELECT') {
      if (el.multiple && Array.isArray(value)) {
        for (var i = 0; i < el.options.length; i += 1) {
          el.options[i].selected = value.indexOf(el.options[i].value) !== -1;
        }
        return;
      }
      el.value = String(value);
      return;
    }
    if (tag === 'TEXTAREA') {
      el.value = String(value);
    }
  }

  function applyState() {
    applying = true;
    try {
      var fields = document.querySelectorAll('input, select, textarea');
      for (var i = 0; i < fields.length; i += 1) {
        var el = fields[i];
        var key = getKey(el);
        if (!key || !(key in appState)) continue;
        writeValue(el, appState[key]);
      }
    } finally {
      applying = false;
    }
  }

  function emitUpdate() {
    if (!window.parent) return;
    window.parent.postMessage(
      {
        type: DATA_EVENT,
        state: appState,
        events: eventLog,
        records: recordLog,
        timestamp: Date.now(),
      },
      '*'
    );
  }

  function pushEvent(name, data) {
    if (!name) return;
    eventLog.unshift({
      name: String(name),
      data: data === undefined ? null : data,
      timestamp: Date.now(),
    });
    if (eventLog.length > MAX_EVENTS) {
      eventLog.length = MAX_EVENTS;
    }
    emitUpdate();
  }

  function pushRecord(type, payload) {
    var recordType =
      type === 'order_submitted' || type === 'booking_submitted' || type === 'form_submission'
        ? type
        : 'form_submission';
    recordLog.unshift({
      type: recordType,
      payload: payload,
      created_at: new Date().toISOString(),
    });
    if (recordLog.length > MAX_RECORDS) {
      recordLog.length = MAX_RECORDS;
    }
    emitUpdate();
  }

  function toSerializable(value) {
    if (!value) return value;
    if (typeof File !== 'undefined' && value instanceof File) {
      return { name: value.name, size: value.size, type: value.type };
    }
    return value;
  }

  function collectFormData(form) {
    var data = {};
    if (!form || typeof FormData === 'undefined') return data;
    var formData = new FormData(form);
    formData.forEach(function (value, key) {
      var cleaned = toSerializable(value);
      if (data[key] === undefined) {
        data[key] = cleaned;
      } else if (Array.isArray(data[key])) {
        data[key].push(cleaned);
      } else {
        data[key] = [data[key], cleaned];
      }
    });
    return data;
  }

  function inferRecordType(form) {
    if (!form || !form.getAttribute) return 'form_submission';
    var candidate =
      form.getAttribute('data-ic-record-type') ||
      form.getAttribute('data-record-type') ||
      form.getAttribute('data-record');
    if (candidate === 'order_submitted' || candidate === 'booking_submitted' || candidate === 'form_submission') {
      return candidate;
    }
    return 'form_submission';
  }

  function emitState() {
    if (!window.parent) return;
    window.parent.postMessage(
      { source: SOURCE, type: STATE_EVENT, state: appState },
      '*'
    );
  }

  function updateState(key, value) {
    if (!key) return;
    appState[key] = value;
    emitState();
    pushEvent('state_update', { key: key, value: value });
  }

  document.addEventListener('input', function (event) {
    if (applying) return;
    var target = event.target;
    var key = getKey(target);
    if (!key) return;
    var value = readValue(target);
    if (value === undefined) return;
    updateState(key, value);
  }, true);

  document.addEventListener('change', function (event) {
    if (applying) return;
    var target = event.target;
    var key = getKey(target);
    if (!key) return;
    var value = readValue(target);
    if (value === undefined) return;
    updateState(key, value);
  }, true);

  document.addEventListener('submit', function (event) {
    var target = event.target;
    if (!target || target.tagName !== 'FORM') return;
    var recordPayload = collectFormData(target);
    var recordType = inferRecordType(target);
    pushRecord(recordType, recordPayload);
    pushEvent('form_submit', { type: recordType });
  }, true);

  document.addEventListener('click', function (event) {
    var target = event.target;
    if (!target || !target.closest) return;
    var anchor = target.closest('a');
    if (!anchor) return;
    var href = anchor.getAttribute('href');
    var slug = normalizeSlug(href);
    if (!slug) return;
    event.preventDefault();
    pushEvent('navigate', { slug: slug, href: href });
    if (window.parent) {
      window.parent.postMessage(
        { source: SOURCE, type: NAV_EVENT, slug: slug },
        '*'
      );
    }
  }, true);

  window.addEventListener('message', function (event) {
    var data = event.data || {};
    if (!data || data.source !== SOURCE) return;
    if (data.type === STATE_INIT) {
      appState = data.state && typeof data.state === 'object' ? data.state : {};
      applyState();
      emitUpdate();
    }
  });

  window.IC_APP = {
    getState: function () {
      return appState;
    },
    setState: function (keyOrState, value) {
      if (typeof keyOrState === 'string') {
        updateState(keyOrState, value);
        return;
      }
      if (keyOrState && typeof keyOrState === 'object') {
        for (var key in keyOrState) {
          if (Object.prototype.hasOwnProperty.call(keyOrState, key)) {
            appState[key] = keyOrState[key];
          }
        }
        emitState();
        pushEvent('state_sync', { keys: Object.keys(keyOrState) });
      }
    },
    navigate: function (slug) {
      if (!slug || !window.parent) return;
      window.parent.postMessage(
        { source: SOURCE, type: NAV_EVENT, slug: slug },
        '*'
      );
    }
  };

  if (window.parent) {
    window.parent.postMessage({ source: SOURCE, type: READY_EVENT }, '*');
    emitUpdate();
  }
})();
</script>`;

const injectAppModeRuntime = (html: string) => {
  if (!html) return html
  if (html.includes('id="ic-app-mode-runtime"')) return html
  if (html.includes('</body>')) {
    return html.replace('</body>', `${APP_MODE_SCRIPT}</body>`)
  }
  if (html.includes('</head>')) {
    return html.replace('</head>', `${APP_MODE_SCRIPT}</head>`)
  }
  return `${html}${APP_MODE_SCRIPT}`
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
  htmlContent?: string
  previewUrl?: string | null
  onRefresh?: () => void
  onExport?: () => void
  isRefreshing?: boolean
  isExporting?: boolean
  // Multi-page props (optional)
  pages?: PageInfo[]
  selectedPageId?: string | null
  onSelectPage?: (pageId: string) => void
  onRefreshPage?: (pageId: string) => void
}

type PreviewTab = 'preview' | 'data'

export function PreviewPanel({
  sessionId,
  appMode = false,
  onAppModeChange,
  htmlContent,
  previewUrl,
  onRefresh,
  onExport,
  isRefreshing = false,
  isExporting = false,
  pages,
  selectedPageId,
  onSelectPage,
  onRefreshPage,
}: PreviewPanelProps) {
  const containerRef = React.useRef<HTMLDivElement | null>(null)
  const iframeRef = React.useRef<HTMLIFrameElement | null>(null)
  const [activeTab, setActiveTab] = React.useState<PreviewTab>('preview')
  const [scale, setScale] = React.useState(1)
  const [currentHtml, setCurrentHtml] = React.useState<string | null>(htmlContent ?? null)
  const [currentUrl, setCurrentUrl] = React.useState<string | null>(previewUrl ?? null)
  const [appState, setAppState] = React.useState<Record<string, unknown>>({})

  const storageKey = sessionId ? `instant-coffee:app-state:${sessionId}` : null

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
    const withRuntime = appMode ? injectAppModeRuntime(currentHtml) : currentHtml
    return injectHideScrollbarStyle(withRuntime)
  }, [appMode, currentHtml])
  const htmlValue = currentHtml?.trim() ? injectedHtml : EMPTY_PREVIEW_HTML

  // Update current preview when props change
  React.useEffect(() => {
    setCurrentHtml(htmlContent ?? null)
  }, [htmlContent])

  React.useEffect(() => {
    setCurrentUrl(appMode ? null : previewUrl ?? null)
  }, [appMode, previewUrl])

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
    if (!appMode) return
    const frame = iframeRef.current
    if (!frame || !frame.contentWindow) return
    frame.contentWindow.postMessage(
      { source: APP_MODE_SOURCE, type: 'ic_state_init', state: appState },
      '*'
    )
  }, [appMode, appState])

  React.useEffect(() => {
    if (!appMode) return
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
  }, [appMode, onSelectPage, pages, sendStateToIframe])

  React.useEffect(() => {
    if (!appMode) return
    sendStateToIframe()
  }, [appMode, sendStateToIframe])

  React.useEffect(() => {
    if (!containerRef.current) return

    const updateScale = () => {
      if (!containerRef.current) return
      if (activeTab !== 'preview') return
      const width = containerRef.current.clientWidth
      const nextScale = Math.min(1, Math.max(0.6, width / 460))
      setScale(nextScale)
    }

    updateScale()
    const observer = new ResizeObserver(updateScale)
    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [activeTab])

  const previewLabel =
    isMultiPage && selectedPageId
      ? `Preview: ${pages.find((p) => p.id === selectedPageId)?.title ?? 'Page'}`
      : 'Preview'

  return (
    <Tabs
      value={activeTab}
      onValueChange={(value) => setActiveTab(value as PreviewTab)}
      className="flex h-full flex-col"
    >
      <div className="flex items-center justify-between border-b border-border px-6 py-4">
        <div className="flex items-center gap-4">
          <TabsList className="h-8">
            <TabsTrigger value="preview" className="text-xs">
              Preview
            </TabsTrigger>
            <TabsTrigger value="data" className="text-xs">
              Data
            </TabsTrigger>
          </TabsList>
          <span className="text-sm font-semibold text-foreground">
            {activeTab === 'preview' ? previewLabel : 'Preview data'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {onAppModeChange ? (
            <Button
              type="button"
              size="sm"
              variant={appMode ? 'default' : 'outline'}
              onClick={() => onAppModeChange(!appMode)}
              aria-pressed={appMode}
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

      <TabsContent value="preview" forceMount className="mt-0 flex-1">
        <div className="flex h-full flex-col">
          {/* Page Selector - only show when multi-page */}
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
              <iframe
                ref={iframeRef}
                key={`${selectedPageId ?? 'preview'}-${appMode ? 'app' : 'static'}`}
                title="Preview"
                className="h-full w-full border-0"
                sandbox="allow-scripts allow-same-origin"
                onLoad={sendStateToIframe}
                {...(currentUrl && !appMode ? { src: currentUrl } : { srcDoc: htmlValue })}
              />
            </PhoneFrame>
          </div>
        </div>
      </TabsContent>

      <TabsContent value="data" forceMount className="mt-0 flex-1">
        <DataTab iframeRef={iframeRef} key={sessionId ?? 'preview-data'} />
      </TabsContent>
    </Tabs>
  )
}
