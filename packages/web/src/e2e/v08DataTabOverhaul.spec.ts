/// <reference types="node" />

import { test, expect } from 'playwright/test'

type MockOptions = {
  sessionId: string
}

const mockSettings = {
  model: 'gpt-4o-mini',
  available_models: [{ id: 'gpt-4o-mini', label: 'GPT-4o Mini' }],
}

const setupCommonSessionMocks = async (
  page: import('playwright/test').Page,
  options: MockOptions
) => {
  const { sessionId } = options
  const now = new Date().toISOString()

  await page.route('**/api/settings', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockSettings),
    })
  )

  await page.route(`**/api/sessions/${sessionId}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: sessionId,
        title: 'Data Overhaul Test Session',
        created_at: now,
        updated_at: now,
        current_version: 1,
      }),
    })
  )

  await page.route(`**/api/sessions/${sessionId}/messages`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ messages: [] }),
    })
  )

  await page.route(`**/api/sessions/${sessionId}/versions**`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ versions: [], current_version: 1 }),
    })
  )

  await page.route(`**/api/sessions/${sessionId}/pages`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ pages: [], total: 0 }),
    })
  )

  await page.route(`**/api/sessions/${sessionId}/product-doc`, (route) =>
    route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Not found' }),
    })
  )

  await page.route(`**/api/sessions/${sessionId}/product-doc/history**`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ history: [], pinned_count: 0 }),
    })
  )

  await page.route(`**/api/sessions/${sessionId}/snapshots**`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ snapshots: [] }),
    })
  )

  await page.route('**/api/sessions/*/events**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ events: [], last_seq: 0, has_more: false }),
    })
  )

  await page.route(`**/api/sessions/${sessionId}/build/status`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'idle', pages: [] }),
    })
  )

  await page.route(`**/api/sessions/${sessionId}/build/stream**`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: 'data: [DONE]\n\n',
    })
  )
}

test.describe('v08 F1 Data Tab Overhaul', () => {
  const sessionId = 'f1-data-overhaul-session'

  test.beforeEach(async ({ page }) => {
    await setupCommonSessionMocks(page, { sessionId })

    let requestCounter = 0

    await page.route(`**/api/sessions/${sessionId}/data/tables`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          schema: `app_${sessionId}`,
          tables: [
            {
              name: 'orders',
              columns: [
                { name: 'id', data_type: 'integer', udt_name: 'int4' },
                { name: 'status', data_type: 'text', udt_name: 'text' },
                { name: 'total', data_type: 'numeric', udt_name: 'numeric' },
                { name: 'items', data_type: 'jsonb', udt_name: 'jsonb' },
              ],
            },
            {
              name: 'customers',
              columns: [
                { name: 'id', data_type: 'integer', udt_name: 'int4' },
                { name: 'name', data_type: 'text', udt_name: 'text' },
                { name: 'vip', data_type: 'boolean', udt_name: 'bool' },
              ],
            },
          ],
        }),
      })
    )

    await page.route(`**/api/sessions/${sessionId}/data/orders?**`, (route) => {
      const url = new URL(route.request().url())
      const offset = Number(url.searchParams.get('offset') ?? '0')
      const limit = Number(url.searchParams.get('limit') ?? '25')
      const pageIndex = Math.floor(offset / Math.max(1, limit))

      const records = Array.from({ length: Math.min(limit, 2) }).map((_, idx) => {
        const base = pageIndex * limit + idx + 1
        return {
          id: base,
          status: base % 2 === 0 ? 'paid' : 'pending',
          total: base * 10,
          items: [{ sku: `SKU-${base}`, qty: 1 }],
        }
      })

      requestCounter += 1

      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          records,
          total: 60,
          limit,
          offset,
          request_counter: requestCounter,
        }),
      })
    })

    await page.route(`**/api/sessions/${sessionId}/data/customers?**`, (route) => {
      const url = new URL(route.request().url())
      const limit = Number(url.searchParams.get('limit') ?? '25')
      const offset = Number(url.searchParams.get('offset') ?? '0')
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          records: [
            { id: 1 + offset, name: 'Alice', vip: true },
            { id: 2 + offset, name: 'Bob', vip: false },
          ],
          total: 2,
          limit,
          offset,
        }),
      })
    })

    await page.route(`**/api/sessions/${sessionId}/data/orders/stats`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          table: 'orders',
          count: 60,
          numeric: {
            total: { sum: 12340, avg: 205.6, min: 10, max: 800 },
          },
          boolean: {
            shipped: { true: 40, false: 20 },
          },
        }),
      })
    )

    await page.route(`**/api/sessions/${sessionId}/data/customers/stats`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          table: 'customers',
          count: 2,
          numeric: {},
          boolean: {
            vip: { true: 1, false: 1 },
          },
        }),
      })
    )
  })

  test('shows Data as top-level workbench tab', async ({ page }) => {
    await page.goto(`/project/${sessionId}`)
    await page.waitForSelector('[data-testid="workbench-tab-preview"]')

    await expect(page.locator('[data-testid="workbench-tab-preview"]')).toBeVisible()
    await expect(page.locator('[data-testid="workbench-tab-code"]')).toBeVisible()
    await expect(page.locator('[data-testid="workbench-tab-product-doc"]')).toBeVisible()
    await expect(page.locator('[data-testid="workbench-tab-data"]')).toBeVisible()
  })

  test('table view renders tables, rows and pagination', async ({ page }) => {
    await page.goto(`/project/${sessionId}`)
    await page.click('[data-testid="workbench-tab-data"]')

    await expect(page.locator('[data-testid="data-tab"]')).toBeVisible()
    await expect(page.locator('[data-testid="data-view-table"]')).toBeVisible()
    await expect(page.locator('[data-testid="data-table-tab-orders"]')).toBeVisible()
    await expect(page.locator('[data-testid="data-table-tab-customers"]')).toBeVisible()
    await expect(page.locator('[data-testid="data-grid"]')).toBeVisible()
    await expect(page.locator('[data-testid="data-grid-row"]')).toHaveCount(2)

    await page.getByRole('button', { name: '2' }).click()
    await expect(page.locator('[data-testid="data-grid-row"]')).toHaveCount(2)
  })

  test('dashboard view renders summaries and distributions', async ({ page }) => {
    await page.goto(`/project/${sessionId}`)
    await page.click('[data-testid="workbench-tab-data"]')
    await page.click('[data-testid="data-view-dashboard"]')

    await expect(page.locator('[data-testid="data-dashboard-table-summary"]')).toBeVisible()
    await expect(page.locator('[data-testid="data-dashboard-numeric"]')).toBeVisible()
    await expect(page.locator('[data-testid="data-dashboard-boolean"]')).toBeVisible()
    await expect(page.getByText('Numeric Aggregates (SUM)')).toBeVisible()
  })

  test('refreshes table data when receiving postMessage refresh signal', async ({ page }) => {
    let ordersRequestCount = 0
    await page.route(`**/api/sessions/${sessionId}/data/orders?**`, async (route) => {
      const url = new URL(route.request().url())
      const offset = Number(url.searchParams.get('offset') ?? '0')
      const limit = Number(url.searchParams.get('limit') ?? '25')
      const pageIndex = Math.floor(offset / Math.max(1, limit))

      const records = Array.from({ length: Math.min(limit, 2) }).map((_, idx) => {
        const base = pageIndex * limit + idx + 1
        return {
          id: base,
          status: base % 2 === 0 ? 'paid' : 'pending',
          total: base * 10,
          items: [{ sku: `SKU-${base}`, qty: 1 }],
        }
      })

      ordersRequestCount += 1

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          records,
          total: 60,
          limit,
          offset,
        }),
      })
    })

    await page.goto(`/project/${sessionId}`)
    await page.click('[data-testid="workbench-tab-data"]')

    await expect(page.locator('[data-testid="data-grid-row"]')).toHaveCount(2)
    const beforeRequests = ordersRequestCount

    await page.evaluate(() => {
      window.postMessage({ type: 'data_changed' }, '*')
    })

    await expect.poll(() => ordersRequestCount).toBeGreaterThan(beforeRequests)
  })
})
