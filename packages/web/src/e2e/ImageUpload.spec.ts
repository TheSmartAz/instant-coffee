/// <reference types="node" />

/**
 * E2E tests for image attachments and @page mentions.
 *
 * Images are attached from textarea paste/drop. There is no dedicated image
 * upload button for chat attachments.
 */
import { test, expect, type Page } from 'playwright/test'
import { setupProjectPageMocks, type MockPageRecord } from './helpers/projectMocks'

const sessionId = 'image-upload-session'
const tinyPngBase64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+4Z6cAAAAASUVORK5CYII='

const mockPages: MockPageRecord[] = [
  { id: 'page-home', title: 'Home Page', slug: 'home' },
  { id: 'page-about', title: 'About Us', slug: 'about' },
  { id: 'page-pricing', title: 'Pricing', slug: 'pricing' },
]

type BrowserFile = {
  name: string
  mimeType: string
  base64?: string
  size?: number
}

async function createFileTransfer(page: Page, files: BrowserFile[]) {
  return page.evaluateHandle((items) => {
    const transfer = new DataTransfer()

    for (const item of items) {
      let content: BlobPart
      if (item.base64) {
        const binary = atob(item.base64)
        const bytes = new Uint8Array(binary.length)
        for (let i = 0; i < binary.length; i += 1) {
          bytes[i] = binary.charCodeAt(i)
        }
        content = bytes
      } else {
        content = new Uint8Array(item.size ?? 1)
      }

      transfer.items.add(new File([content], item.name, { type: item.mimeType }))
    }

    return transfer
  }, files)
}

async function dropFiles(page: Page, files: BrowserFile[]) {
  const dataTransfer = await createFileTransfer(page, files)
  await page.getByTestId('chat-textarea').dispatchEvent('drop', { dataTransfer })
  await dataTransfer.dispose()
}

async function pasteFiles(page: Page, files: BrowserFile[]) {
  await page.getByTestId('chat-textarea').evaluate((textarea, items) => {
    const transfer = new DataTransfer()

    for (const item of items) {
      let content: BlobPart
      if (item.base64) {
        const binary = atob(item.base64)
        const bytes = new Uint8Array(binary.length)
        for (let i = 0; i < binary.length; i += 1) {
          bytes[i] = binary.charCodeAt(i)
        }
        content = bytes
      } else {
        content = new Uint8Array(item.size ?? 1)
      }

      transfer.items.add(new File([content], item.name, { type: item.mimeType }))
    }

    const event = new ClipboardEvent('paste', {
      bubbles: true,
      cancelable: true,
    })
    Object.defineProperty(event, 'clipboardData', { value: transfer })
    textarea.dispatchEvent(event)
  }, files)
}

async function openProject(page: Page) {
  await setupProjectPageMocks(page, {
    sessionId,
    pages: mockPages,
  })
  await page.goto(`/project/${sessionId}`)
  await page.waitForSelector('[data-testid="chat-input"]')
}

const imageFile = (name: string): BrowserFile => ({
  name,
  mimeType: 'image/png',
  base64: tinyPngBase64,
})

test.describe('Image attachments', () => {
  test.beforeEach(async ({ page }) => {
    await openProject(page)
  })

  test('drop displays an image thumbnail', async ({ page }) => {
    await dropFiles(page, [imageFile('dropped.png')])

    await expect(page.getByTestId('image-thumbnail')).toHaveCount(1)
    await expect(page.getByRole('img', { name: 'dropped.png' })).toBeVisible()
  })

  test('paste displays an image thumbnail', async ({ page }) => {
    await pasteFiles(page, [imageFile('pasted.png')])

    await expect(page.getByTestId('image-thumbnail')).toHaveCount(1)
    await expect(page.getByRole('img', { name: 'pasted.png' })).toBeVisible()
  })

  test('removes a thumbnail', async ({ page }) => {
    await dropFiles(page, [imageFile('remove-me.png')])
    await expect(page.getByTestId('image-thumbnail')).toHaveCount(1)

    await page.getByTestId('remove-image-button').click()

    await expect(page.getByTestId('image-thumbnail')).toHaveCount(0)
  })

  test('enforces the three image limit', async ({ page }) => {
    await dropFiles(page, [
      imageFile('one.png'),
      imageFile('two.png'),
      imageFile('three.png'),
      imageFile('four.png'),
    ])

    await expect(page.getByTestId('image-thumbnail')).toHaveCount(3)
    await expect(page.getByText('Image limit reached', { exact: true })).toBeVisible()
    await expect(
      page.getByText('Only 3 more images allowed.', { exact: true })
    ).toBeVisible()

    await dropFiles(page, [imageFile('extra.png')])
    await expect(page.getByTestId('image-thumbnail')).toHaveCount(3)
    await expect(
      page.getByText('You can upload up to 3 images.', { exact: true })
    ).toBeVisible()
  })

  test('rejects non-image files with a toast', async ({ page }) => {
    await dropFiles(page, [
      { name: 'brief.pdf', mimeType: 'application/pdf', size: 128 },
    ])

    await expect(page.getByTestId('image-thumbnail')).toHaveCount(0)
    await expect(page.getByText('Invalid file type', { exact: true })).toBeVisible()
    await expect(
      page.getByText('brief.pdf is not an image.', { exact: true })
    ).toBeVisible()
  })

  test('rejects files over 10MB with a toast', async ({ page }) => {
    await dropFiles(page, [
      {
        name: 'large.png',
        mimeType: 'image/png',
        size: 11 * 1024 * 1024,
      },
    ])

    await expect(page.getByTestId('image-thumbnail')).toHaveCount(0)
    await expect(page.getByText('File too large', { exact: true })).toBeVisible()
    await expect(
      page.getByText('large.png exceeds 10MB.', { exact: true })
    ).toBeVisible()
  })
})

test.describe('@page mentions', () => {
  test.beforeEach(async ({ page }) => {
    await openProject(page)
  })

  test('opens after @ and filters pages', async ({ page }) => {
    const textarea = page.getByTestId('chat-textarea')

    await textarea.fill('@')

    await expect(page.getByTestId('page-mention-popover')).toBeVisible()
    await expect(page.getByTestId('page-mention-item')).toHaveCount(3)

    await textarea.fill('@ho')

    await expect(page.getByTestId('page-mention-item')).toHaveCount(1)
    await expect(page.getByTestId('page-mention-item')).toContainText('@home')
  })

  test('supports keyboard navigation and selection', async ({ page }) => {
    const textarea = page.getByTestId('chat-textarea')

    await textarea.fill('@')
    await expect(page.getByTestId('page-mention-popover')).toBeVisible()

    await page.keyboard.press('ArrowDown')
    await expect(page.getByTestId('page-mention-item').nth(1)).toHaveAttribute(
      'data-active',
      'true'
    )

    await page.keyboard.press('Enter')

    await expect(textarea).toHaveValue('@about ')
    await expect(page.getByTestId('page-mention-popover')).not.toBeVisible()
  })

  test('inserts clicked page mention at the cursor', async ({ page }) => {
    const textarea = page.getByTestId('chat-textarea')

    await textarea.fill('Update ')
    await textarea.press('End')
    await page.keyboard.type('@')
    await page.getByTestId('page-mention-item').filter({ hasText: '@home' }).click()

    await expect(textarea).toHaveValue('Update @home ')
  })

  test('closes the popover with Escape', async ({ page }) => {
    const textarea = page.getByTestId('chat-textarea')

    await textarea.fill('@')
    await expect(page.getByTestId('page-mention-popover')).toBeVisible()

    await textarea.dispatchEvent('keydown', { key: 'Escape' })

    await expect(page.getByTestId('page-mention-popover')).not.toBeVisible()
    await expect(textarea).toHaveValue('@')
  })

  test('shows an empty state when no pages match', async ({ page }) => {
    await page.getByTestId('chat-textarea').fill('@nonexistent')

    await expect(page.getByTestId('page-mention-empty')).toBeVisible()
    await expect(page.getByTestId('page-mention-empty')).toContainText(
      'No matching pages'
    )
  })
})
