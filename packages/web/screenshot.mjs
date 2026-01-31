import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });
  const page = await context.newPage();

  const pages = [
    { name: 'homepage', url: 'http://localhost:5174/' },
    { name: 'project', url: 'http://localhost:5174/project/demo-1' },
    { name: 'settings', url: 'http://localhost:5174/settings' }
  ];

  for (const p of pages) {
    try {
      await page.goto(p.url, { waitUntil: 'networkidle', timeout: 10000 });
      await page.screenshot({ path: `/tmp/${p.name}.png`, fullPage: true });
      console.log(`Screenshot saved: ${p.name}.png`);

      // Get page structure info
      const title = await page.title();
      console.log(`\n=== ${p.name.toUpperCase()} ===`);
      console.log(`Title: ${title}`);

      // Get layout info
      const header = await page.$('header');
      if (header) {
        const headerBox = await header.boundingBox();
        console.log(`Header: ${headerBox?.width}x${headerBox?.height}`);
      }

      // Get main content info
      const main = await page.$('main');
      if (main) {
        const mainBox = await main.boundingBox();
        console.log(`Main: ${mainBox?.width}x${mainBox?.height}`);
      }

    } catch (e) {
      console.log(`Error on ${p.name}: ${e.message}`);
    }
  }

  await browser.close();
})();
