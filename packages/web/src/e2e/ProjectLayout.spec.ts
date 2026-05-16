import { expect, test } from 'playwright/test'
import { setupProjectPageMocks } from './helpers/projectMocks'

const sessionId = 'project-layout-session'

test.describe('Project layout', () => {
  test.beforeEach(async ({ page }) => {
    await setupProjectPageMocks(page, {
      sessionId,
      title: 'Responsive Layout Test',
    })
  })

  test('lets the desktop chat pane resize wider without hiding the workspace', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.goto(`/project/${sessionId}`)

    const panels = page.locator('[data-panel]')
    await expect(panels).toHaveCount(2)

    const initialLeft = await panels.nth(0).boundingBox()
    const initialRight = await panels.nth(1).boundingBox()
    expect(initialLeft?.width).toBeGreaterThan(360)
    expect(initialLeft?.width).toBeLessThan(430)
    expect(initialRight?.width).toBeGreaterThan(780)

    const handle = page.getByRole('separator').first()
    const handleBox = await handle.boundingBox()
    expect(handleBox).not.toBeNull()

    await page.mouse.move(handleBox!.x + handleBox!.width / 2, handleBox!.y + handleBox!.height / 2)
    await page.mouse.down()
    await page.mouse.move(handleBox!.x + 220, handleBox!.y + handleBox!.height / 2, { steps: 8 })
    await page.mouse.up()

    const resizedLeft = await panels.nth(0).boundingBox()
    const resizedRight = await panels.nth(1).boundingBox()
    expect(resizedLeft?.width).toBeGreaterThan((initialLeft?.width ?? 0) + 120)
    expect(resizedRight?.width).toBeGreaterThan(320)
    await expect(page.getByTestId('chat-textarea')).toBeVisible()
    await expect(page.getByTestId('workbench-tab-preview')).toBeVisible()
  })

  test('keeps the mobile project shell within the viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto(`/project/${sessionId}`)

    await expect(page.getByRole('button', { name: 'Open code drawer' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Open data drawer' })).toBeVisible()
    await expect(page.getByTestId('chat-textarea')).toBeVisible()
    await expect(page.getByTestId('workbench-tab-preview')).toBeVisible()

    const geometry = await page.evaluate(() => ({
      viewport: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth,
    }))

    expect(geometry.documentWidth).toBeLessThanOrEqual(geometry.viewport)
    expect(geometry.bodyWidth).toBeLessThanOrEqual(geometry.viewport)
  })
})
