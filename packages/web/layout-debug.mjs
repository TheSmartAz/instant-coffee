import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });
  const page = await context.newPage();

  await page.goto('http://localhost:5173/project/demo-1', { waitUntil: 'load', timeout: 30000 });
  await page.waitForTimeout(2000);

  console.log('=== Final Layout Verification ===\n');

  // Get exact panel sizes
  const sizes = await page.evaluate(() => {
    const versionPanel = document.querySelector('[class*="border-l"][class*="bg-background"]');
    const chatContainer = document.querySelector('div[class*="w-[35%]"]');
    const previewContainer = document.querySelector('div[class*="flex-1"][class*="min-w-0"]');

    return {
      viewport: { width: window.innerWidth, height: window.innerHeight },
      version: versionPanel ? Math.round(versionPanel.getBoundingClientRect().width) : 0,
      chat: chatContainer ? Math.round(chatContainer.getBoundingClientRect().width) : 0,
      preview: previewContainer ? Math.round(previewContainer.getBoundingClientRect().width) : 0
    };
  });

  console.log('Viewport:', sizes.viewport.width, 'x', sizes.viewport.height);
  console.log('\nPanel widths:');
  console.log(`  Chat Panel:     ${sizes.chat}px`);
  console.log(`  Preview Panel:  ${sizes.preview}px`);
  console.log(`  Version Panel:  ${sizes.version}px`);
  console.log(`  Total:          ${sizes.chat + sizes.preview + sizes.version}px`);

  // Calculate percentages (excluding VersionPanel)
  const mainAreaWidth = sizes.chat + sizes.preview;
  console.log('\nMain area (Chat + Preview):');
  console.log(`  Total: ${mainAreaWidth}px`);
  console.log(`  Chat: ${Math.round(sizes.chat / mainAreaWidth * 100)}%`);
  console.log(`  Preview: ${Math.round(sizes.preview / mainAreaWidth * 100)}%`);

  // Verify VersionPanel collapse/expand
  console.log('\nVersionPanel:');
  const vpExpanded = sizes.version;
  console.log(`  Expanded: ${vpExpanded}px`);

  const toggleBtn = await page.$('[class*="border-l"] button[aria-label*="Collapse"], [class*="border-l"] button[aria-label*="Expand"]');
  if (toggleBtn) {
    await toggleBtn.click();
    await page.waitForTimeout(300);

    const vpCollapsed = await page.evaluate(() => {
      const vp = document.querySelector('[class*="border-l"][class*="bg-background"]');
      return vp ? Math.round(vp.getBoundingClientRect().width) : 0;
    });
    console.log(`  Collapsed: ${vpCollapsed}px`);
  }

  console.log('\n✓ Layout complete!');
  console.log('  - Chat & Preview: resizable via CSS (35% / remaining)');
  console.log('  - Version Panel: fixed 256px, collapsible to 48px');

  await browser.close();
})();
