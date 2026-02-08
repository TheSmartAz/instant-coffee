import { useEffect, useMemo, useState } from 'react'
import { SchemaRenderer, type PageSchema } from './lib/schema-renderer'
import { DataStore, initDataTabBridge } from './lib/data-store'

export interface AppProps {
  pageSlug?: string
  schemas?: PageSchema[]
  tokens?: Record<string, any>
  registry?: Record<string, any>
  assets?: Record<string, any>
}

const isBrowser = typeof window !== 'undefined'

const FALLBACK_SCHEMA: PageSchema = {
  slug: 'index',
  title: 'Instant Coffee',
  layout: 'default',
  components: [],
}

const hasGlob = typeof (import.meta as any).glob === 'function'
const bundledSchemas = (hasGlob
  ? import.meta.glob('./data/schemas.json', { eager: true, import: 'default' })
  : {}) as Record<string, PageSchema[]>
const bundledTokens = (hasGlob
  ? import.meta.glob('./data/tokens.json', { eager: true, import: 'default' })
  : {}) as Record<string, Record<string, any>>
const bundledAssets = (hasGlob
  ? import.meta.glob('./data/assets.json', { eager: true, import: 'default' })
  : {}) as Record<string, Record<string, any>>

const inlineSchemas = Object.values(bundledSchemas)[0]
const inlineTokens = Object.values(bundledTokens)[0]
const inlineAssets = Object.values(bundledAssets)[0]

async function fetchJson<T>(url: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(url)
    if (!response.ok) return fallback
    return (await response.json()) as T
  } catch {
    return fallback
  }
}

function normalizeSlug(slug?: string) {
  if (!slug) return 'index'
  const cleaned = slug.replace(/^\/+/, '').replace(/\/+$/, '').replace(/\.html$/, '')
  if (!cleaned || cleaned === 'index') return 'index'
  return cleaned
}

function slugFromPath(pathname: string) {
  const cleaned = pathname.replace(/\.html$/, '').replace(/\/+$/, '')
  if (!cleaned || cleaned === '/') return 'index'
  const parts = cleaned.split('/').filter(Boolean)
  const pagesIndex = parts.indexOf('pages')
  if (pagesIndex >= 0 && pagesIndex < parts.length - 1) {
    return normalizeSlug(parts[pagesIndex + 1])
  }
  return normalizeSlug(parts[parts.length - 1])
}

function applyStyleTokens(tokens?: Record<string, any>) {
  if (!isBrowser || !tokens) return

  const root = document.documentElement
  const palette = tokens.colors || tokens.palette || {}
  const typography = tokens.typography || {}

  const mapping: Record<string, string | undefined> = {
    '--ic-bg': palette.background,
    '--ic-text': palette.foreground || palette.text,
    '--ic-accent': palette.primary,
    '--ic-muted': palette.muted,
    '--ic-card': palette.card,
  }

  Object.entries(mapping).forEach(([key, value]) => {
    if (value) root.style.setProperty(key, value)
  })

  if (typography.fontFamily) {
    root.style.setProperty('--ic-font', typography.fontFamily)
  }
}

const App = ({ pageSlug, schemas: initialSchemas, tokens: initialTokens, assets: initialAssets }: AppProps) => {
  const [schemas, setSchemas] = useState<PageSchema[] | null>(initialSchemas || inlineSchemas || null)
  const [tokens, setTokens] = useState<Record<string, any> | null>(initialTokens || inlineTokens || null)
  const [assets, setAssets] = useState<Record<string, any> | null>(initialAssets || inlineAssets || null)

  const store = useMemo(() => new DataStore(), [])

  useEffect(() => {
    if (!isBrowser) return
    initDataTabBridge(store)
  }, [store])

  useEffect(() => {
    if (!isBrowser || initialSchemas || inlineSchemas) return
    fetchJson<PageSchema[]>('/data/schemas.json', [FALLBACK_SCHEMA]).then(setSchemas)
  }, [initialSchemas])

  useEffect(() => {
    if (!isBrowser || initialTokens || inlineTokens) return
    fetchJson<Record<string, any>>('/data/tokens.json', {}).then(setTokens)
  }, [initialTokens])

  useEffect(() => {
    if (!isBrowser || initialAssets || inlineAssets) return
    fetchJson<Record<string, any>>('/data/assets.json', {}).then(setAssets)
  }, [initialAssets])

  useEffect(() => {
    applyStyleTokens(tokens || undefined)
  }, [tokens])

  const resolvedSlug = normalizeSlug(pageSlug || (isBrowser ? slugFromPath(window.location.pathname) : 'index'))
  const availableSchemas = schemas || [FALLBACK_SCHEMA]
  const pageSchema =
    availableSchemas.find((schema) => normalizeSlug(schema.slug) === resolvedSlug) ||
    availableSchemas[0] ||
    FALLBACK_SCHEMA

  useEffect(() => {
    if (!isBrowser) return
    store.logEvent('page_view', { slug: pageSchema.slug, title: pageSchema.title }, pageSchema.slug)
  }, [pageSchema.slug])

  const dataContext = {
    ...store.getSnapshot(),
    tokens: tokens || undefined,
    assets: assets || undefined,
    page: pageSchema,
  }

  return (
    <div id="app" className={`page ${pageSchema.layout === 'fullscreen' ? 'w-full' : ''}`}>
      <div className="ic-shell">
        <SchemaRenderer schema={pageSchema} data={dataContext} />
      </div>
    </div>
  )
}

export default App
