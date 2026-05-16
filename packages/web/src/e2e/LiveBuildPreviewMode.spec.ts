import { test, expect, type Page } from 'playwright/test'
import { setupProjectPageMocks, type MockPageRecord } from './helpers/projectMocks'

const sessionId = 'live-build-preview-session'

const pages: MockPageRecord[] = [
  { id: 'page-home', title: 'Home', slug: 'index' },
  { id: 'page-pricing', title: 'Pricing', slug: 'pricing' },
  { id: 'page-contact', title: 'Contact', slug: 'contact' },
]

async function openProject(page: Page) {
  await setupProjectPageMocks(page, {
    sessionId,
    pages,
    build: {
      status: 'success',
      pages: ['index.html', 'pages/pricing/index.html', 'pages/contact/index.html'],
      dist_path: 'dist/live-build-preview-session',
      error: null,
    },
    previewHtmlByPageId: {
      'page-home': `<!doctype html>
        <html>
          <body>
            <main>
              <h1>Home page</h1>
              <a id="pricing-link" href="/pages/pricing/index.html">View pricing</a>
              <a id="contact-link" href="contact.html">Contact us</a>
            </main>
          </body>
        </html>`,
      'page-pricing': `<!doctype html>
        <html>
          <body>
            <main>
              <h1>Pricing page</h1>
              <a href="/index.html">Back home</a>
            </main>
          </body>
        </html>`,
      'page-contact': `<!doctype html>
        <html>
          <body>
            <main>
              <h1>Contact page</h1>
            </main>
          </body>
        </html>`,
    },
    buildPreviewHtmlByPath: {
      'index.html': `<!doctype html>
        <html>
          <body>
            <main>
              <h1>Built app home</h1>
              <button type="button" id="build-button">Interactive build button</button>
            </main>
          </body>
        </html>`,
    },
  })

  await page.goto(`/project/${sessionId}`)
  await expect(page.getByTestId('preview-panel')).toBeVisible()
}

test.describe('Live/build preview modes', () => {
  test('renders live mode as a multi-page iframe map with dashed connectors', async ({ page }) => {
    await openProject(page)

    await expect(page.getByTestId('live-page-map')).toBeVisible()
    await expect(page.getByTestId('live-page-frame')).toHaveCount(3)
    await expect(page.getByTestId('live-page-iframe')).toHaveCount(3)
    await expect(page.getByTestId('live-page-label')).toHaveCount(3)
    await expect(page.getByTestId('live-page-label')).toContainText(['Home', 'Pricing', 'Contact'])
    await expect(page.getByTestId('preview-iframe')).toHaveCount(0)

    await expect(page.getByTestId('live-link-overlay')).toBeVisible()
    await expect(page.getByTestId('live-link-connector').first()).toBeVisible()
    await expect(page.getByTestId('live-link-connector').first()).toHaveAttribute(
      'stroke-dasharray',
      /.+/
    )
  })

  test('inserts a page mention from a live page label without opening the mention popover', async ({
    page,
  }) => {
    await openProject(page)

    const textarea = page.getByTestId('chat-textarea')
    await textarea.fill('Update copy')
    await page.getByTestId('live-page-label').filter({ hasText: 'Pricing' }).click()

    await expect(textarea).toBeFocused()
    await expect(textarea).toHaveValue('Update copy @pricing ')
    await expect(page.getByTestId('page-mention-popover')).toHaveCount(0)
  })

  test('keeps build mode on a single interactive build iframe', async ({ page }) => {
    await openProject(page)

    await page.getByRole('button', { name: 'Build' }).click()

    await expect(page.getByTestId('live-page-map')).toHaveCount(0)
    await expect(page.getByTestId('live-link-overlay')).toHaveCount(0)
    await expect(page.getByTestId('live-link-connector')).toHaveCount(0)
    await expect(page.getByTestId('live-page-iframe')).toHaveCount(0)
    await expect(page.getByTestId('preview-iframe')).toHaveCount(1)
    await expect(page.getByTestId('preview-iframe')).toHaveAttribute(
      'src',
      new RegExp(`/preview/${sessionId}/index\\.html`)
    )

    const buildButton = page.frameLocator('[data-testid="preview-iframe"]').locator('#build-button')
    await expect(buildButton).toBeVisible()
    await buildButton.click()
  })
})
