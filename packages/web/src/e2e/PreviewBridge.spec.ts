import { test, expect } from 'playwright/test'
import { setupProjectPageMocks, type MockTable } from './helpers/projectMocks'

const sessionId = 'preview-bridge-session'

const tables: MockTable[] = [
  {
    name: 'orders',
    columns: [
      { name: 'id', data_type: 'integer' },
      { name: 'status', data_type: 'text' },
    ],
  },
]

const records = [
  { id: 1, status: 'ready' },
  { id: 2, status: 'queued' },
]

test.describe('Preview Message Bridge E2E', () => {
  test.beforeEach(async ({ page }) => {
    await setupProjectPageMocks(page, {
      sessionId,
      title: 'Preview Bridge Test Session',
      pages: [
        {
          id: 'page-home',
          title: 'Home',
          slug: 'index',
        },
      ],
      previewHtmlByPageId: {
        'page-home':
          '<!doctype html><html><body><main><button id="refresh">Refresh data</button></main></body></html>',
      },
      tables,
      recordsByTable: {
        orders: records,
      },
      statsByTable: {
        orders: {
          table: 'orders',
          count: records.length,
          numeric: {},
          boolean: {},
        },
      },
    })
  })

  test('renders preview panel and iframe before switching to data', async ({ page }) => {
    await page.goto(`/project/${sessionId}`)

    await expect(page.getByTestId('preview-panel')).toBeVisible()
    await expect(page.getByTestId('preview-iframe')).toBeVisible()

    await page.getByRole('button', { name: 'Open data drawer' }).click()
    await expect(page.getByTestId('data-tab')).toBeVisible()
    await expect(page.getByTestId('data-view-table')).toBeVisible()
    await expect(page.getByTestId('data-grid-row')).toHaveCount(2)
  })

  test('ignores unrelated preview messages without breaking the data tab', async ({ page }) => {
    await page.goto(`/project/${sessionId}`)
    await expect(page.getByTestId('preview-iframe')).toBeVisible()

    await page.evaluate(() => {
      window.postMessage({ type: 'unknown-preview-message' }, '*')
      window.postMessage('not-json', '*')
    })

    await page.getByRole('button', { name: 'Open data drawer' }).click()
    await expect(page.getByTestId('data-tab')).toBeVisible()
    await expect(page.getByTestId('data-grid-row')).toHaveCount(2)
    await expect(page.getByTestId('data-tab')).toContainText('ready')
  })

  test('refreshes data when the preview bridge emits a data_changed message', async ({ page }) => {
    let ordersRequestCount = 0

    await page.route(`**/api/sessions/${sessionId}/data/orders?**`, (route) => {
      ordersRequestCount += 1
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          records,
          total: records.length,
          limit: 25,
          offset: 0,
        }),
      })
    })

    await page.goto(`/project/${sessionId}`)
    await page.getByRole('button', { name: 'Open data drawer' }).click()
    await expect(page.getByTestId('data-grid-row')).toHaveCount(2)

    const beforeMessage = ordersRequestCount
    await page.evaluate(() => {
      window.postMessage({ type: 'data_changed' }, '*')
    })

    await expect.poll(() => ordersRequestCount).toBeGreaterThan(beforeMessage)
  })

  test('can open dashboard view after preview iframe initialization', async ({ page }) => {
    await page.goto(`/project/${sessionId}`)
    await expect(page.getByTestId('preview-iframe')).toBeVisible()

    await page.getByRole('button', { name: 'Open data drawer' }).click()
    await page.getByTestId('data-view-dashboard').click()

    await expect(page.getByTestId('data-view-dashboard')).toHaveAttribute('class', /bg-primary/)
    await expect(page.getByTestId('data-dashboard-table-summary')).toBeVisible()
  })
})
