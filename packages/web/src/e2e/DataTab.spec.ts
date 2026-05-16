import { test, expect } from 'playwright/test'
import { setupProjectPageMocks, type MockTable } from './helpers/projectMocks'

const sessionId = 'data-tab-session'

const tables: MockTable[] = [
  {
    name: 'orders',
    columns: [
      { name: 'id', data_type: 'integer' },
      { name: 'status', data_type: 'text' },
      { name: 'total', data_type: 'numeric' },
      { name: 'paid', data_type: 'boolean' },
    ],
  },
  {
    name: 'customers',
    columns: [
      { name: 'id', data_type: 'integer' },
      { name: 'email', data_type: 'text' },
    ],
  },
]

const orderRecords = [
  { id: 1, status: 'paid', total: 42, paid: true },
  { id: 2, status: 'pending', total: 18, paid: false },
]

test.describe('Data Tab E2E', () => {
  test.beforeEach(async ({ page }) => {
    await setupProjectPageMocks(page, {
      sessionId,
      title: 'Data Tab Test Session',
      tables,
      recordsByTable: {
        orders: orderRecords,
        customers: [
          { id: 1, email: 'ada@example.com' },
          { id: 2, email: 'grace@example.com' },
        ],
      },
      statsByTable: {
        orders: {
          table: 'orders',
          count: orderRecords.length,
          numeric: {
            total: { sum: 60, avg: 30, min: 18, max: 42 },
          },
          boolean: {
            paid: { true: 1, false: 1 },
          },
        },
        customers: {
          table: 'customers',
          count: 2,
          numeric: {},
          boolean: {},
        },
      },
    })
  })

  test('renders from the project header data drawer with table data', async ({ page }) => {
    await page.goto(`/project/${sessionId}`)

    await expect(page.getByTestId('workbench-tab-data')).toHaveCount(0)
    await page.getByRole('button', { name: 'Open data drawer' }).click()

    await expect(page.getByTestId('data-tab')).toBeVisible()
    await expect(page.getByTestId('data-view-table')).toBeVisible()
    await expect(page.getByTestId('data-view-dashboard')).toBeVisible()
    await expect(page.getByTestId('data-refresh')).toBeVisible()
    await expect(page.getByTestId('data-grid-row')).toHaveCount(2)
    await expect(page.getByTestId('data-tab')).toContainText('paid')
    await expect(page.getByTestId('data-tab')).toContainText('pending')
  })

  test('switches tables in table view', async ({ page }) => {
    await page.goto(`/project/${sessionId}`)
    await page.getByRole('button', { name: 'Open data drawer' }).click()

    await expect(page.getByTestId('data-grid-row')).toHaveCount(2)
    await page.getByTestId('data-table-tab-customers').click()

    await expect(page.getByTestId('data-grid-row')).toHaveCount(2)
    await expect(page.getByTestId('data-tab')).toContainText('ada@example.com')
    await expect(page.getByTestId('data-tab')).toContainText('grace@example.com')
  })

  test('renders dashboard summaries for the active table', async ({ page }) => {
    await page.goto(`/project/${sessionId}`)
    await page.getByRole('button', { name: 'Open data drawer' }).click()
    await page.getByTestId('data-view-dashboard').click()

    await expect(page.getByTestId('data-view-dashboard')).toHaveAttribute('class', /bg-primary/)
    await expect(page.getByTestId('data-dashboard-table-summary')).toBeVisible()
    await expect(page.getByTestId('data-dashboard-numeric')).toBeVisible()
    await expect(page.getByTestId('data-dashboard-boolean')).toBeVisible()
    await expect(page.getByTestId('data-tab')).toContainText('Numeric Aggregates (SUM)')
  })

  test('refresh button reloads table records', async ({ page }) => {
    let ordersRequestCount = 0

    await page.route(`**/api/sessions/${sessionId}/data/orders?**`, (route) => {
      ordersRequestCount += 1
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          records: orderRecords,
          total: orderRecords.length,
          limit: 25,
          offset: 0,
        }),
      })
    })

    await page.goto(`/project/${sessionId}`)
    await page.getByRole('button', { name: 'Open data drawer' }).click()
    await expect(page.getByTestId('data-grid-row')).toHaveCount(2)

    const beforeRefresh = ordersRequestCount
    await page.getByTestId('data-refresh').click()

    await expect.poll(() => ordersRequestCount).toBeGreaterThan(beforeRefresh)
  })
})
