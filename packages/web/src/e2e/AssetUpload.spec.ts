/// <reference types="node" />

import { test, expect } from 'playwright/test'

type MockOptions = {
  sessionId: string
}

const mockSettings = {
  model: 'gpt-4o-mini',
  available_models: [{ id: 'gpt-4o-mini', label: 'GPT-4o Mini' }],
}

const setupApiMocks = async (page: import('playwright/test').Page, options: MockOptions) => {
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
        title: 'Test Session',
        created_at: now,
        updated_at: now,
        current_version: 0,
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
      body: JSON.stringify({ versions: [], current_version: 0 }),
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
}

test.describe('Asset Upload E2E', () => {
  const sessionId = 'test-session'

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, { sessionId })
  })

  test('1. Asset type selector renders all options', async ({ page }) => {
    await page.goto(`/project/${sessionId}`)
    await page.waitForSelector('[data-testid="chat-input"]')

    await page.click('[data-testid="asset-upload-button"]')
    await expect(page.locator('[data-testid="asset-type-dialog"]')).toBeVisible()

    await expect(page.locator('[data-testid="asset-type-option-logo"]')).toBeVisible()
    await expect(page.locator('[data-testid="asset-type-option-style_ref"]')).toBeVisible()
    await expect(page.locator('[data-testid="asset-type-option-background"]')).toBeVisible()
    await expect(page.locator('[data-testid="asset-type-option-product_image"]')).toBeVisible()
  })

  test('2. Upload flow renders asset thumbnail', async ({ page }) => {
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
          url: 'http://127.0.0.1:5173/assets/mock.png',
          type: 'image/png',
          width: 120,
          height: 60,
        }),
      })
    })

    await page.goto(`/project/${sessionId}`)
    await page.waitForSelector('[data-testid="chat-input"]')

    await page.click('[data-testid="asset-upload-button"]')
    await page.click('[data-testid="asset-type-option-logo"]')

    const fileInput = page.locator('[data-testid="asset-file-input"]')
    await fileInput.setInputFiles({
      name: 'logo.png',
      mimeType: 'image/png',
      buffer: Buffer.from('fake-image'),
    })

    await expect(page.locator('[data-testid="asset-upload-progress"]')).toBeVisible()
    await expect(
      page.locator('[data-testid="asset-thumbnail"][data-asset-id="asset:logo_abc123"]')
    ).toBeVisible()
  })
})
