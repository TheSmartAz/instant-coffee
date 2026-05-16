import { chromium } from 'playwright'
import { existsSync, mkdirSync } from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const args = new Map()
for (let i = 2; i < process.argv.length; i += 2) {
  args.set(process.argv[i], process.argv[i + 1])
}

const html = args.get('--html')
const out = args.get('--out')

if (!html || !out) {
  console.error('--html and --out are required')
  process.exit(2)
}

const htmlPath = path.resolve(html)
const outPath = path.resolve(out)

if (!existsSync(htmlPath)) {
  console.error(`HTML file not found: ${htmlPath}`)
  process.exit(2)
}

mkdirSync(path.dirname(outPath), { recursive: true })

const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  })
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: 'networkidle', timeout: 30000 })
  await page.screenshot({ path: outPath, fullPage: false })
} finally {
  await browser.close()
}
