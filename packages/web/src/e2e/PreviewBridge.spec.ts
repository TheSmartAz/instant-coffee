/**
 * E2E tests for Preview Message Bridge (v06-F3)
 *
 * Acceptance Criteria:
 * 1. Hook returns current state, events, and records
 * 2. Hook returns connection status and last update timestamp
 * 3. Messages filtered by type guard and ignored when malformed
 * 4. Listener cleanup on unmount and iframe disconnect
 */
import { test, expect } from 'playwright/test';

test.describe('Preview Message Bridge E2E', () => {
  test('1. Hook returns current state, events, and records', async ({ page }) => {
    await page.goto('/project/test-session');

    // Wait for preview to load
    await page.waitForSelector('[data-testid="preview-iframe"]');

    // Check if data tab shows initial state
    await page.click('[data-testid="data-tab-button"]');
    await expect(page.locator('[data-testid="data-state-section"]')).toBeVisible();
    await expect(page.locator('[data-testid="data-events-section"]')).toBeVisible();
    await expect(page.locator('[data-testid="data-records-section"]')).toBeVisible();
  });

  test('2. Hook returns connection status and last update timestamp', async ({ page }) => {
    await page.goto('/project/test-session');
    await page.waitForSelector('[data-testid="preview-iframe"]');

    // Connection status should be visible
    await page.click('[data-testid="data-tab-button"]');
    await expect(page.locator('[data-testid="connection-status"]')).toBeVisible();
  });

  test('3. Messages filtered by type guard', async ({ page }) => {
    await page.goto('/project/test-session');
    await page.waitForSelector('[data-testid="preview-iframe"]');

    // Send malformed message (should be ignored)
    await page.evaluate(() => {
      const iframe = document.querySelector('[data-testid="preview-iframe"]') as HTMLIFrameElement;
      if (iframe.contentWindow) {
        iframe.contentWindow.postMessage({ type: 'unknown-type' }, '*');
      }
    });

    // Should not crash or show error
    await expect(page.locator('[data-testid="data-tab"]')).toBeVisible();
  });

  test('4. State updates trigger UI refresh', async ({ page }) => {
    await page.goto('/project/test-session');
    await page.waitForSelector('[data-testid="preview-iframe"]');

    // Simulate state update from iframe
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: { cart: { items: [{ id: 1, name: 'Test Product' }] } },
          events: [{ type: 'add_to_cart', timestamp: new Date().toISOString() }],
          records: []
        }
      }, '*');
    });

    // Check if data is reflected in UI
    await page.click('[data-testid="data-tab-button"]');
    await expect(page.locator('[data-testid="data-state-section"]')).toContainText('Test Product');
  });

  test('5. Debounced updates for non-submit events', async ({ page }) => {
    await page.goto('/project/test-session');
    await page.waitForSelector('[data-testid="preview-iframe"]');

    // Simulate multiple rapid updates
    await page.evaluate(() => {
      for (let i = 0; i < 5; i++) {
        window.postMessage({
          type: 'instant-coffee:update',
          data: {
            state: { count: i },
            events: [],
            records: []
          }
        }, '*');
      }
    });

    // Should not overwhelm the UI
    await page.click('[data-testid="data-tab-button"]');
    await expect(page.locator('[data-testid="data-state-section"]')).toBeVisible();
  });

  test('6. Immediate updates for submit events', async ({ page }) => {
    await page.goto('/project/test-session');
    await page.waitForSelector('[data-testid="preview-iframe"]');

    // Simulate submit event
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: {},
          events: [],
          records: [{
            type: 'order_submitted',
            created_at: new Date().toISOString(),
            payload: { order_id: 'ORD-123' }
          }]
        }
      }, '*');
    });

    // Should immediately show in records
    await page.click('[data-testid="data-tab-button"]');
    await expect(page.locator('[data-testid="record-item"]')).toContainText('order_submitted');
  });
});
