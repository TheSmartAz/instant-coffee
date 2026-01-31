import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });
  const page = await context.newPage();

  await page.goto('http://localhost:5173/', { waitUntil: 'load', timeout: 30000 });
  await page.waitForTimeout(2000);

  await page.screenshot({ path: '/tmp/homepage-with-header.png', fullPage: true });
  console.log('Screenshot saved: homepage-with-header.png');

  // Check if Header is visible
  const headerInfo = await page.evaluate(() => {
    const header = document.querySelector('header');
    if (header) {
      const rect = header.getBoundingClientRect();
      return {
        exists: true,
        height: Math.round(rect.height),
        width: Math.round(rect.width),
        hasLogo: header.textContent?.includes('Instant Coffee'),
        hasNewSession: header.textContent?.includes('新会话')
      };
    }
    return { exists: false };
  });

  console.log('\nHeader check:', headerInfo);

  await browser.close();
})();
