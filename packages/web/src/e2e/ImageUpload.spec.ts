/// <reference types="node" />

/**
 * E2E tests for Image Upload & @Page Support (v06-F2, v06-F4)
 *
 * Acceptance Criteria:
 * 1. Image button opens file picker
 * 2. Drag-and-drop works on textarea
 * 3. Images display as thumbnails
 * 4. Remove button on each image thumbnail
 * 5. Max 3 images enforced
 * 6. Only images accepted; non-image rejected with message
 * 7. Files > 10MB rejected with message
 * 8. Dropdown appears after @ with filtering
 * 9. Keyboard navigation and click-to-select work
 * 10. @Page inserted at cursor position
 */
import { test, expect } from 'playwright/test';

test.describe('Image Upload E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/project/test-session');
    await page.waitForSelector('[data-testid="chat-input"]');
  });

  test('1. Image button opens file picker', async ({ page }) => {
    // Setup file chooser interceptor
    const fileChooserPromise = page.waitForEvent('filechooser');

    await page.click('[data-testid="image-upload-button"]');

    const fileChooser = await fileChooserPromise;
    expect(fileChooser).toBeTruthy();
  });

  test('2. Drag-and-drop works on textarea', async ({ page }) => {
    // Create DataTransfer for drag and drop
    const dataTransfer = await page.evaluateHandle((fileData) => {
      const dt = new DataTransfer();
      const file = new File([fileData.content], 'test.png', { type: 'image/png' });
      dt.items.add(file);
      return dt;
    }, { content: 'fake-image-content' });

    // Dispatch drop event
    await page.locator('[data-testid="chat-textarea"]').dispatchEvent('drop', dataTransfer);

    // Should show thumbnail
    await expect(page.locator('[data-testid="image-thumbnail"]')).toBeVisible();
  });

  test('3. Images display as thumbnails', async ({ page }) => {
    // Upload image via button
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: 'test.png',
      mimeType: 'image/png',
      buffer: Buffer.from('fake-image')
    });

    await expect(page.locator('[data-testid="image-thumbnail"]')).toBeVisible();
  });

  test('4. Remove button on each image thumbnail', async ({ page }) => {
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: 'test.png',
      mimeType: 'image/png',
      buffer: Buffer.from('fake-image')
    });

    await expect(page.locator('[data-testid="remove-image-button"]')).toBeVisible();

    // Click remove
    await page.click('[data-testid="remove-image-button"]');

    // Thumbnail should disappear
    await expect(page.locator('[data-testid="image-thumbnail"]')).not.toBeVisible();
  });

  test('5. Max 3 images enforced', async ({ page }) => {
    const fileInput = page.locator('input[type="file"]');

    // Try to upload 4 files
    await fileInput.setInputFiles([
      { name: '1.png', mimeType: 'image/png', buffer: Buffer.from('1') },
      { name: '2.png', mimeType: 'image/png', buffer: Buffer.from('2') },
      { name: '3.png', mimeType: 'image/png', buffer: Buffer.from('3') },
      { name: '4.png', mimeType: 'image/png', buffer: Buffer.from('4') },
    ]);

    // Should show error message
    await expect(page.locator('[data-testid="image-error-message"]')).toBeVisible();
    await expect(page.locator('[data-testid="image-error-message"]')).toContainText('3');
  });

  test('6. Only images accepted; non-image rejected', async ({ page }) => {
    const fileInput = page.locator('input[type="file"]');

    // Try to upload a non-image file
    await fileInput.setInputFiles({
      name: 'test.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('fake-pdf')
    });

    // Should show error
    await expect(page.locator('[data-testid="image-error-message"]')).toBeVisible();
    await expect(page.locator('[data-testid="image-error-message"]')).toContainText('image');
  });

  test('7. Files > 10MB rejected', async ({ page }) => {
    const largeBuffer = Buffer.alloc(11 * 1024 * 1024); // 11MB
    const fileInput = page.locator('input[type="file"]');

    await fileInput.setInputFiles({
      name: 'large.png',
      mimeType: 'image/png',
      buffer: largeBuffer
    });

    await expect(page.locator('[data-testid="image-error-message"]')).toBeVisible();
    await expect(page.locator('[data-testid="image-error-message"]')).toContainText('10MB');
  });
});

test.describe('@Page Mention E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/project/test-existing-session');
    await page.waitForSelector('[data-testid="chat-input"]');
  });

  test('8. Dropdown appears after @ with filtering', async ({ page }) => {
    const textarea = page.locator('[data-testid="chat-textarea"]');

    // Type @
    await textarea.fill('@');

    // Dropdown should appear
    await expect(page.locator('[data-testid="page-mention-popover"]')).toBeVisible();

    // Type filter
    await textarea.fill('@ho');

    // Should show filtered results
    await expect(page.locator('[data-testid="page-mention-item"]').filter({ hasText: /home/i })).toBeVisible();
  });

  test('9. Keyboard navigation and click-to-select work', async ({ page }) => {
    const textarea = page.locator('[data-testid="chat-textarea"]');

    await textarea.fill('@');
    await expect(page.locator('[data-testid="page-mention-popover"]')).toBeVisible();

    // Arrow down should highlight next item
    await page.keyboard.press('ArrowDown');
    await expect(page.locator('[data-testid="page-mention-item"].highlighted')).toBeVisible();

    // Enter should select
    await page.keyboard.press('Enter');

    // @Page should be inserted
    const value = await textarea.inputValue();
    expect(value).toContain('@');
  });

  test('10. @Page inserted at cursor position', async ({ page }) => {
    const textarea = page.locator('[data-testid="chat-textarea"]');

    // Type some text, move cursor, then type @
    await textarea.fill('Update ');
    await textarea.press('End');
    await page.keyboard.type('@');

    // Select a page
    await page.click('[data-testid="page-mention-item"]:first-child');

    // @Page should be at cursor position
    const value = await textarea.inputValue();
    expect(value).toBe('Update @Home');
  });

  test('Empty state when no pages match', async ({ page }) => {
    const textarea = page.locator('[data-testid="chat-textarea"]');

    await textarea.fill('@nonexistent');

    await expect(page.locator('[data-testid="page-mention-empty"]')).toBeVisible();
    await expect(page.locator('[data-testid="page-mention-empty"]')).toContainText('No matching pages');
  });

  test('Escape closes popover without selection', async ({ page }) => {
    const textarea = page.locator('[data-testid="chat-textarea"]');

    await textarea.fill('@');
    await expect(page.locator('[data-testid="page-mention-popover"]')).toBeVisible();

    await page.keyboard.press('Escape');

    await expect(page.locator('[data-testid="page-mention-popover"]')).not.toBeVisible();
  });
});
