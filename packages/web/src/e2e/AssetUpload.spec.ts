/// <reference types="node" />

import { test, expect } from 'playwright/test'
import { setupProjectPageMocks } from './helpers/projectMocks'

test.describe('Asset Upload E2E', () => {
  const sessionId = 'asset-upload-session'

  test.beforeEach(async ({ page }) => {
    await setupProjectPageMocks(page, { sessionId })
  })

  test('renders the asset type selector options', async ({ page }) => {
    await page.goto(`/project/${sessionId}`)
    await page.waitForSelector('[data-testid="chat-input"]')

    await page.getByTestId('asset-upload-button').click()

    await expect(page.getByTestId('asset-type-dialog')).toBeVisible()
    await expect(page.getByTestId('asset-type-option-logo')).toBeVisible()
    await expect(page.getByTestId('asset-type-option-style_ref')).toBeVisible()
    await expect(page.getByTestId('asset-type-option-background')).toBeVisible()
    await expect(page.getByTestId('asset-type-option-product_image')).toBeVisible()
  })

  test('uploads an asset and renders it in the chat log', async ({ page }) => {
    const tinyPng = Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+4Z6cAAAAASUVORK5CYII=',
      'base64'
    )

    await page.route('**/assets/mock.png', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'image/png',
        body: tinyPng,
      })
    )

    await page.route(`**/api/sessions/${sessionId}/assets**`, async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 150))
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'asset:logo_abc123',
          url: '/assets/mock.png',
          type: 'image/png',
          width: 120,
          height: 60,
        }),
      })
    })

    await page.goto(`/project/${sessionId}`)
    await page.waitForSelector('[data-testid="chat-input"]')

    await page.getByTestId('asset-upload-button').click()
    await page.getByTestId('asset-type-option-logo').click()

    await page.getByTestId('asset-file-input').setInputFiles({
      name: 'logo.png',
      mimeType: 'image/png',
      buffer: Buffer.from('fake-image'),
    })

    await expect(page.getByTestId('asset-upload-progress')).toBeVisible()
    await expect(
      page.locator('[data-testid="asset-thumbnail"][data-asset-id="asset:logo_abc123"]')
    ).toBeVisible()
    await expect(page.getByText('Uploaded Logo')).toBeVisible()
  })
})
