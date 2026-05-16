import { expect, test } from 'playwright/test'
import { setupProjectPageMocks } from './helpers/projectMocks'

const sessionId = 'settings-execution-session'

test.describe('Settings and execution layout', () => {
  test('renders settings sections without mobile overflow', async ({ page }) => {
    await page.route('**/api/settings', (route) => {
      const body = {
        model: 'gpt-4o-mini',
        temperature: 0.7,
        max_tokens: 2048,
        output_dir: '~/instant-coffee-output',
        auto_save: true,
        available_models: [{ id: 'gpt-4o-mini', label: 'GPT-4o Mini' }],
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
      })
    })

    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/settings')

    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible()
    await page.getByRole('button', { name: 'Model' }).click()
    await expect(page.getByText('Model Configuration')).toBeVisible()
    await page.getByRole('button', { name: 'Preferences' }).click()
    await expect(page.getByText('Output Directory')).toBeVisible()

    const geometry = await page.evaluate(() => ({
      viewport: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth,
    }))
    expect(geometry.documentWidth).toBeLessThanOrEqual(geometry.viewport)
    expect(geometry.bodyWidth).toBeLessThanOrEqual(geometry.viewport)
  })

  test('renders execution flow with user-facing title and no mobile overflow', async ({ page }) => {
    await setupProjectPageMocks(page, {
      sessionId,
      title: 'Execution Layout Test',
    })

    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto(`/project/${sessionId}/flow`)

    await expect(page.getByText('Run Progress')).toBeVisible()
    await expect(page.getByText(`Project ${sessionId.slice(0, 8)}`)).toBeVisible()
    await expect(page.getByText(sessionId, { exact: true })).toHaveCount(0)

    const geometry = await page.evaluate(() => ({
      viewport: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth,
    }))
    expect(geometry.documentWidth).toBeLessThanOrEqual(geometry.viewport)
    expect(geometry.bodyWidth).toBeLessThanOrEqual(geometry.viewport)
  })
})
