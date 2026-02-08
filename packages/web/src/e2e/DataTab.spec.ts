/**
 * E2E tests for Data Tab UI (v06-F1)
 *
 * Acceptance Criteria:
 * 1. Component renders in Preview panel
 * 2. Three sections visible by default
 * 3. Each section collapsible
 * 4. Empty state shown when no data
 * 5. JSON formatted and readable
 * 6. Copy button works
 * 7. Large objects can be collapsed
 * 8. Events display in reverse chronological order
 * 9. Timestamps formatted human-readable
 * 10. Data truncated when too long
 * 11. Auto-scrolls to newest events
 * 12. Records show type/date and key data
 * 13. Export downloads JSON
 */
import { test, expect } from 'playwright/test';

test.describe('Data Tab E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to a project page with preview
    await page.goto('/project/test-session');
    // Wait for preview to load
    await page.waitForSelector('[data-testid="preview-panel"]');
    // Click on Data tab
    await page.click('[data-testid="data-tab-button"]');
  });

  test('1. Component renders in Preview panel', async ({ page }) => {
    await expect(page.locator('[data-testid="data-tab"]')).toBeVisible();
  });

  test('2. Three sections visible by default', async ({ page }) => {
    await expect(page.locator('[data-testid="data-state-section"]')).toBeVisible();
    await expect(page.locator('[data-testid="data-events-section"]')).toBeVisible();
    await expect(page.locator('[data-testid="data-records-section"]')).toBeVisible();
  });

  test('3. Each section collapsible', async ({ page }) => {
    // Collapse State section
    await page.click('[data-testid="data-state-section"] [data-testid="collapse-button"]');
    await expect(page.locator('[data-testid="data-state-section"] .collapsed')).toBeVisible();

    // Collapse Events section
    await page.click('[data-testid="data-events-section"] [data-testid="collapse-button"]');
    await expect(page.locator('[data-testid="data-events-section"] .collapsed')).toBeVisible();

    // Collapse Records section
    await page.click('[data-testid="data-records-section"] [data-testid="collapse-button"]');
    await expect(page.locator('[data-testid="data-records-section"] .collapsed')).toBeVisible();
  });

  test('4. Empty state shown when no data', async ({ page }) => {
    await expect(page.locator('[data-testid="data-state-empty"]')).toBeVisible();
    await expect(page.locator('[data-testid="data-events-empty"]')).toBeVisible();
    await expect(page.locator('[data-testid="data-records-empty"]')).toBeVisible();
  });

  test('5. JSON formatted and readable', async ({ page }) => {
    // Simulate receiving data from preview
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: { cart: { items: [] } },
          events: [],
          records: []
        }
      }, '*');
    });

    // Should show formatted JSON
    await expect(page.locator('[data-testid="json-viewer"]')).toBeVisible();
    const jsonText = await page.locator('[data-testid="json-viewer"]').textContent();
    expect(jsonText).toContain('{');
    expect(jsonText).toContain('}');
  });

  test('6. Copy button works', async ({ page }) => {
    // Setup data first
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: { test: 'data' },
          events: [],
          records: []
        }
      }, '*');
    });

    // Click copy button
    const clipboardPromise = page.evaluate(() => {
      return new Promise(resolve => {
        navigator.clipboard.readText().then(resolve);
      });
    });

    await page.click('[data-testid="copy-state-button"]');

    const clipboardText = await clipboardPromise;
    expect(clipboardText).toContain('test');
  });

  test('7. Large objects can be collapsed', async ({ page }) => {
    // Send large object
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: {
            nested: { very: { deep: { object: { with: { many: 'levels' } } } } }
          },
          events: [],
          records: []
        }
      }, '*');
    });

    // Should have expand/collapse buttons
    await expect(page.locator('[data-testid="expand-node"]')).toBeVisible();
    await page.click('[data-testid="expand-node"]');
    // After clicking, should show nested content
  });

  test('8. Events display in reverse chronological order', async ({ page }) => {
    // Send multiple events
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: {},
          events: [
            { type: 'event1', timestamp: '2026-02-04T10:00:00Z' },
            { type: 'event2', timestamp: '2026-02-04T11:00:00Z' },
            { type: 'event3', timestamp: '2026-02-04T12:00:00Z' },
          ],
          records: []
        }
      }, '*');
    });

    // First event in list should be the latest
    const firstEvent = await page.locator('[data-testid="event-item"]').first().textContent();
    expect(firstEvent).toContain('event3');
  });

  test('9. Timestamps formatted human-readable', async ({ page }) => {
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: {},
          events: [
            { type: 'test_event', timestamp: '2026-02-04T12:30:45Z' }
          ],
          records: []
        }
      }, '*');
    });

    const eventText = await page.locator('[data-testid="event-item"]').textContent();
    // Should contain formatted time
    expect(eventText).toMatch(/\d{1,2}:\d{2}/);
  });

  test('10. Data truncated when too long', async ({ page }) => {
    // Send very long string
    const longString = 'x'.repeat(1000);

    await page.evaluate((s) => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: { long: s },
          events: [],
          records: []
        }
      }, '*');
    }, longString);

    // Should have truncate indicator
    const stateText = await page.locator('[data-testid="data-state-section"]').textContent();
    expect(stateText).toContain('...');
  });

  test('11. Auto-scrolls to newest events', async ({ page }) => {
    const eventsList = page.locator('[data-testid="events-list"]');

    // Send initial events
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: {},
          events: Array(20).fill(null).map((_, i) => ({
            type: `event${i}`,
            timestamp: new Date(i * 1000).toISOString()
          })),
          records: []
        }
      }, '*');
    });

    // Wait for scroll to complete
    await page.waitForTimeout(100);

    // Add new event
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: {},
          events: [
            ...Array(20).fill(null).map((_, i) => ({
              type: `event${i}`,
              timestamp: new Date(i * 1000).toISOString()
            })),
            { type: 'latest_event', timestamp: new Date().toISOString() }
          ],
          records: []
        }
      }, '*');
    });

    // Scroll should be at bottom
    const metrics = await eventsList.evaluate((el) => ({
      scrollTop: el.scrollTop,
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight
    }));
    expect(metrics.scrollTop + metrics.clientHeight).toBeGreaterThanOrEqual(
      metrics.scrollHeight - 4
    );
  });

  test('12. Records show type/date and key data', async ({ page }) => {
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: {},
          events: [],
          records: [
            {
              type: 'order_submitted',
              created_at: '2026-02-04T12:00:00Z',
              payload: { order_id: 'ORD-123', total: 99.99 }
            }
          ]
        }
      }, '*');
    });

    await expect(page.locator('[data-testid="record-item"]')).toBeVisible();
    const recordText = await page.locator('[data-testid="record-item"]').textContent();
    expect(recordText).toContain('order_submitted');
    expect(recordText).toContain('ORD-123');
  });

  test('13. Export downloads JSON', async ({ page }) => {
    // Setup download handler
    const downloadPromise = page.waitForEvent('download');

    // Click export button
    await page.click('[data-testid="export-records-button"]');

    const download = await downloadPromise;
    expect(download.suggestedFilename()).toContain('.json');
  });
});
