import { expect, test } from 'playwright/test'
import { mockNow, setupProjectPageMocks, type MockTable } from './helpers/projectMocks'

const sessionId = 'project-drawers-session'

const tables: MockTable[] = [
  {
    name: 'orders',
    columns: [
      { name: 'id', data_type: 'integer' },
      { name: 'status', data_type: 'text' },
    ],
  },
]

test.describe('Project drawers', () => {
  test.beforeEach(async ({ page }) => {
    await setupProjectPageMocks(page, {
      sessionId,
      title: 'Drawer Test Session',
      productDoc: {
        id: 'doc-1',
        session_id: sessionId,
        content: '# Drawer Product Doc\n\nUse the drawer to inspect requirements.',
        structured: {},
        version: 2,
        status: 'draft',
        created_at: mockNow,
        updated_at: mockNow,
      },
      tables,
      recordsByTable: {
        orders: [
          { id: 1, status: 'paid' },
          { id: 2, status: 'pending' },
        ],
      },
    })

    await page.route(`**/api/sessions/${sessionId}/files`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          tree: [
            {
              name: 'index.html',
              path: 'index.html',
              type: 'file',
              size: 32,
            },
          ],
        }),
      })
    )

    await page.route(`**/api/sessions/${sessionId}/files/index.html`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          path: 'index.html',
          content: '<main>Drawer code file</main>',
          language: 'html',
          size: 29,
        }),
      })
    )
  })

  test('opens code, product doc, and data drawers from the project header', async ({ page }) => {
    await page.goto(`/project/${sessionId}`)

    await page.getByRole('button', { name: 'Open code drawer' }).click()
    const codeDialog = page.getByRole('dialog', { name: 'Code' })
    await expect(codeDialog).toBeVisible()
    await expect(codeDialog.getByText('index.html')).toBeVisible()
    await page.getByRole('button', { name: 'Close drawer' }).click()

    await page.getByRole('button', { name: 'Open product doc drawer' }).click()
    const docDialog = page.getByRole('dialog', { name: 'Product Doc' })
    await expect(docDialog).toBeVisible()
    await expect(docDialog.getByText('Drawer Product Doc')).toBeVisible()
    await page.getByRole('button', { name: 'Close drawer' }).click()

    await page.getByRole('button', { name: 'Open data and more drawer' }).click()
    const dataDialog = page.getByRole('dialog', { name: 'Data' })
    await expect(dataDialog).toBeVisible()
    await expect(dataDialog.getByTestId('data-tab')).toBeVisible()
    await expect(dataDialog.getByTestId('data-grid-row')).toHaveCount(2)
  })
})
