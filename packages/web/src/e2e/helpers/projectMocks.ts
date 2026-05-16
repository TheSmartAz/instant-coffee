/// <reference types="node" />

import type { Page as PlaywrightPage, Route } from 'playwright/test'

export const mockNow = '2026-05-13T10:00:00.000Z'

export const mockSettings = {
  model: 'gpt-4o-mini',
  available_models: [{ id: 'gpt-4o-mini', label: 'GPT-4o Mini' }],
}

export type MockPageRecord = {
  id: string
  title: string
  slug: string
  description?: string
  order_index?: number
  current_version_id?: number | null
}

export type MockTable = {
  name: string
  columns: Array<{
    name: string
    data_type?: string
    udt_name?: string
    nullable?: boolean
    default?: unknown
  }>
}

export type MockTableStats = {
  table?: string
  count?: number
  numeric?: Record<
    string,
    {
      sum?: number | string | null
      avg?: number | string | null
      min?: number | string | null
      max?: number | string | null
    }
  >
  boolean?: Record<string, Record<string, number>>
}

export type ProjectPageMockOptions = {
  sessionId: string
  title?: string
  currentVersion?: number
  pages?: MockPageRecord[]
  messages?: unknown[]
  versions?: unknown[]
  tables?: MockTable[]
  recordsByTable?: Record<string, Array<Record<string, unknown>>>
  statsByTable?: Record<string, MockTableStats>
  totalsByTable?: Record<string, number>
  productDoc?: unknown | null
  build?: unknown
  events?: unknown[]
  runs?: unknown[]
  threadId?: string
  previewHtmlByPageId?: Record<string, string>
  buildPreviewHtmlByPath?: Record<string, string>
}

export const jsonResponse = (body: unknown, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
})

export const eventStreamResponse = (events: unknown[]) => ({
  status: 200,
  contentType: 'text/event-stream',
  headers: { 'Cache-Control': 'no-cache' },
  body: `${events
    .map((event) => `data: ${typeof event === 'string' ? event : JSON.stringify(event)}`)
    .join('\n\n')}\n\n`,
})

const fulfillJson = (route: Route, body: unknown, status = 200) =>
  route.fulfill(jsonResponse(body, status))

const normalizePage = (sessionId: string, page: MockPageRecord, index: number) => ({
  id: page.id,
  session_id: sessionId,
  title: page.title,
  slug: page.slug,
  description: page.description ?? '',
  order_index: page.order_index ?? index,
  current_version_id: page.current_version_id ?? 1,
  created_at: mockNow,
  updated_at: mockNow,
})

const defaultStatsFor = (
  table: string,
  records: Array<Record<string, unknown>>,
  total?: number
): MockTableStats => ({
  table,
  count: total ?? records.length,
  numeric: {},
  boolean: {},
})

export async function setupProjectPageMocks(
  page: PlaywrightPage,
  options: ProjectPageMockOptions
) {
  const {
    sessionId,
    title = 'Test Session',
    currentVersion = 1,
    messages = [],
    versions = [],
    pages = [],
    tables = [],
    recordsByTable = {},
    statsByTable = {},
    totalsByTable = {},
    productDoc = null,
    build = { status: 'idle', pages: [] },
    events = [],
    runs = [],
    threadId = 'thread-1',
    previewHtmlByPageId = {},
    buildPreviewHtmlByPath = {},
  } = options
  const normalizedPages = pages.map((item, index) => normalizePage(sessionId, item, index))

  await page.addInitScript(() => {
    window.localStorage.clear()
    window.sessionStorage.clear()
  })

  await page.route('**/api/settings', (route) => fulfillJson(route, mockSettings))

  await page.route(`**/api/sessions/${sessionId}`, (route) =>
    fulfillJson(route, {
      id: sessionId,
      title,
      created_at: mockNow,
      updated_at: mockNow,
      current_version: currentVersion,
    })
  )

  await page.route(`**/api/sessions/${sessionId}/metadata`, (route) =>
    fulfillJson(route, { id: sessionId, aesthetic_scores: null })
  )

  await page.route(`**/api/sessions/${sessionId}/messages**`, (route) =>
    fulfillJson(route, { messages })
  )

  await page.route(`**/api/sessions/${sessionId}/versions**`, (route) =>
    fulfillJson(route, { versions, current_version: currentVersion })
  )

  await page.route(`**/api/sessions/${sessionId}/threads`, (route) =>
    fulfillJson(route, {
      threads: [
        {
          id: threadId,
          session_id: sessionId,
          title: 'Main',
          created_at: mockNow,
          updated_at: mockNow,
          message_count: messages.length,
        },
      ],
    })
  )

  await page.route(`**/api/sessions/${sessionId}/cost`, (route) =>
    fulfillJson(route, {
      session_id: sessionId,
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
      cost_usd: 0,
      by_agent: {},
    })
  )

  await page.route(`**/api/sessions/${sessionId}/pages`, (route) =>
    fulfillJson(route, { pages: normalizedPages, total: normalizedPages.length })
  )

  await page.route('**/api/pages/*/preview**', (route) => {
    const url = new URL(route.request().url())
    const parts = url.pathname.split('/')
    const pageId = parts[parts.indexOf('pages') + 1]
    const matched = normalizedPages.find((item) => item.id === pageId)
    const html =
      previewHtmlByPageId[pageId] ??
      '<!doctype html><html><body><main>Preview ready</main></body></html>'
    const acceptsHtml = route.request().headers().accept?.includes('text/html')
    if (acceptsHtml) {
      return route.fulfill({
        status: 200,
        contentType: 'text/html',
        body: html,
      })
    }
    return fulfillJson(route, {
      page_id: pageId,
      slug: matched?.slug ?? 'preview',
      html,
      version: 1,
    })
  })

  await page.route('**/api/pages/*/versions**', (route) =>
    fulfillJson(route, { versions: [], current_version: 1 })
  )

  await page.route(`**/api/sessions/${sessionId}/product-doc`, (route) => {
    if (productDoc === null) {
      return route.fulfill(jsonResponse({ detail: 'Not found' }, 404))
    }
    return fulfillJson(route, productDoc)
  })

  await page.route(`**/api/sessions/${sessionId}/product-doc/history**`, (route) =>
    fulfillJson(route, { history: [], pinned_count: 0 })
  )

  await page.route(`**/api/sessions/${sessionId}/snapshots**`, (route) =>
    fulfillJson(route, { snapshots: [] })
  )

  await page.route(`**/api/sessions/${sessionId}/build/status`, (route) =>
    fulfillJson(route, build)
  )

  await page.route(`**/api/sessions/${sessionId}/build/stream**`, (route) =>
    route.fulfill(eventStreamResponse(['[DONE]']))
  )

  await page.route(`**/preview/${sessionId}/**`, (route) => {
    const url = new URL(route.request().url())
    const prefix = `/preview/${sessionId}/`
    const path = decodeURIComponent(url.pathname.slice(prefix.length)) || 'index.html'
    return route.fulfill({
      status: 200,
      contentType: 'text/html',
      body:
        buildPreviewHtmlByPath[path] ??
        '<!doctype html><html><body><main>Build preview ready</main></body></html>',
    })
  })

  await page.route(`**/api/sessions/${sessionId}/events**`, (route) =>
    fulfillJson(route, { events, last_seq: events.length, has_more: false })
  )

  await page.route(`**/api/sessions/${sessionId}/data/tables`, (route) =>
    fulfillJson(route, { schema: `app_${sessionId}`, tables })
  )

  for (const table of tables) {
    await page.route(`**/api/sessions/${sessionId}/data/${table.name}?**`, (route) => {
      const url = new URL(route.request().url())
      const offset = Number(url.searchParams.get('offset') ?? '0')
      const limit = Number(url.searchParams.get('limit') ?? '25')
      const records = recordsByTable[table.name] ?? []
      const total = totalsByTable[table.name] ?? records.length
      return fulfillJson(route, {
        records: records.slice(offset, offset + limit),
        total,
        limit,
        offset,
      })
    })

    await page.route(`**/api/sessions/${sessionId}/data/${table.name}/stats`, (route) =>
      fulfillJson(
        route,
        statsByTable[table.name] ??
          defaultStatsFor(table.name, recordsByTable[table.name] ?? [], totalsByTable[table.name])
      )
    )
  }

  await page.route(/\/api\/runs\?/, (route) =>
    fulfillJson(route, { runs, total: runs.length })
  )

  await page.route('**/api/chat/stream**', (route) =>
    route.fulfill(eventStreamResponse(['[DONE]']))
  )
}
