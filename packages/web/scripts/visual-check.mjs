import { chromium } from 'playwright'
import { existsSync, mkdirSync } from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const args = new Map()
for (let i = 2; i < process.argv.length; i += 2) {
  args.set(process.argv[i], process.argv[i + 1])
}

const dist = args.get('--dist')
const pagePath = args.get('--page') || 'index.html'
const outDir = args.get('--out') || path.join(process.cwd(), '.visual-check')

if (!dist) {
  console.log(JSON.stringify({
    status: 'failed',
    passed: false,
    errors: ['--dist is required'],
    checks: [],
  }))
  process.exit(0)
}

const targetPath = path.resolve(dist, pagePath)
const screenshotPath = path.resolve(outDir, 'mobile.png')
const checks = []
const errors = []
const warnings = []
const consoleErrors = []
const pageErrors = []

function record(name, passed, details = {}) {
  checks.push({ name, passed, details })
  if (!passed) errors.push(`${name} failed`)
}

function qualityScore(checks, warnings) {
  if (!checks.length) return 0
  const weights = {
    page_loads: 25,
    body_not_blank: 20,
    layout_has_area: 20,
    console_clean: 20,
    touch_targets: 15,
  }
  const raw = checks.reduce((total, check) => {
    const weight = weights[check.name] ?? 10
    return total + (check.passed ? weight : 0)
  }, 0)
  const max = checks.reduce((total, check) => total + (weights[check.name] ?? 10), 0)
  const warningPenalty = Math.min(warnings.length * 5, 15)
  return Math.max(0, Math.min(100, Math.round((raw / max) * 100 - warningPenalty)))
}

if (!existsSync(targetPath)) {
  record('page_exists', false, { path: targetPath })
  console.log(JSON.stringify({
    status: 'failed',
    passed: false,
    errors,
    warnings,
    checks,
  }))
  process.exit(0)
}

mkdirSync(outDir, { recursive: true })

const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  })

  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', (error) => {
    pageErrors.push(error.message)
  })

  await page.goto(pathToFileURL(targetPath).href, { waitUntil: 'networkidle', timeout: 30000 })
  await page.screenshot({ path: screenshotPath, fullPage: true })

  const bodyText = await page.locator('body').innerText({ timeout: 5000 }).catch(() => '')
  const bodyBox = await page.locator('body').boundingBox().catch(() => null)
  const buttonCount = await page.locator('button, a, input, textarea, select, [role="button"]').count()
  const smallTargets = await page
    .locator('button, a, input, textarea, select, [role="button"]')
    .evaluateAll((nodes) =>
      nodes
        .map((node) => {
          const rect = node.getBoundingClientRect()
          const label =
            node.getAttribute('aria-label') ||
            node.textContent?.trim() ||
            node.getAttribute('href') ||
            node.tagName
          return { label, width: rect.width, height: rect.height }
        })
        .filter((item) => item.width > 0 && item.height > 0 && (item.width < 44 || item.height < 44))
        .slice(0, 10),
    )

  record('page_loads', true, { path: targetPath })
  record('body_not_blank', bodyText.trim().length >= 40, { text_length: bodyText.trim().length })
  record('layout_has_area', Boolean(bodyBox && bodyBox.width >= 320 && bodyBox.height >= 400), bodyBox || {})
  record('console_clean', consoleErrors.length === 0 && pageErrors.length === 0, {
    console_errors: consoleErrors.slice(0, 10),
    page_errors: pageErrors.slice(0, 10),
  })
  record('touch_targets', smallTargets.length === 0, {
    checked_count: buttonCount,
    small_targets: smallTargets,
  })

  if (buttonCount === 0) {
    warnings.push('No interactive controls were found.')
  }
} catch (error) {
  record('visual_check_runtime', false, { message: error instanceof Error ? error.message : String(error) })
} finally {
  await browser.close()
}

const passed = checks.length > 0 && checks.every((check) => check.passed)
console.log(JSON.stringify({
  status: passed ? 'passed' : 'failed',
  passed,
  quality_score: qualityScore(checks, warnings),
  page: pagePath,
  screenshot_path: screenshotPath,
  errors,
  warnings,
  checks,
}, null, 2))
