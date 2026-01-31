import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });
  const page = await context.newPage();

  const pages = [
    { name: 'homepage', url: 'http://localhost:5173/' },
    { name: 'project', url: 'http://localhost:5173/project/demo-1' },
    { name: 'settings', url: 'http://localhost:5173/settings' }
  ];

  console.log('=== Taking Screenshots ===\n');

  for (const p of pages) {
    await page.goto(p.url, { waitUntil: 'load', timeout: 30000 });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `/tmp/${p.name}-final.png`, fullPage: true });
    console.log(`Screenshot saved: ${p.name}-final.png`);
  }

  await browser.close();
  console.log('\nAll screenshots saved to /tmp/');
})();
