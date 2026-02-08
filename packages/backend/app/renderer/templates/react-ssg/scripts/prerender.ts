import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import React from 'react'
import { renderToString } from 'react-dom/server'
import App, { type AppProps } from '../src/App'
import type { PageSchema, HeadMeta } from '../src/lib/schema-renderer'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(__dirname, '..')
const distDir = path.join(rootDir, 'dist')
const dataDir = path.join(rootDir, 'src', 'data')

const fallbackSchema: PageSchema = {
  slug: 'index',
  title: 'Instant Coffee',
  layout: 'default',
  components: [],
}

function readJson<T>(filePath: string, fallback: T): T {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf-8')) as T
  } catch {
    return fallback
  }
}

function normalizeSlug(slug?: string) {
  if (!slug) return 'index'
  const cleaned = slug.replace(/^\/+/, '').replace(/\/+$/, '').replace(/\.html$/, '')
  return cleaned || 'index'
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function buildHeadTags(title: string | undefined, head: HeadMeta | undefined) {
  const tags: string[] = []

  if (title) {
    tags.push(`<meta property="og:title" content="${escapeHtml(title)}" />`)
  }

  if (head?.description) {
    tags.push(`<meta name="description" content="${escapeHtml(head.description)}" />`)
  }

  if (head?.keywords?.length) {
    tags.push(`<meta name="keywords" content="${escapeHtml(head.keywords.join(', '))}" />`)
  }

  if (head?.ogImage) {
    tags.push(`<meta property="og:image" content="${escapeHtml(head.ogImage)}" />`)
  }

  return tags.join('\n')
}

function injectHead(html: string, title: string | undefined, headTags: string) {
  let output = html

  if (title) {
    output = output.replace(/<title>(.*?)<\/title>/, `<title>${escapeHtml(title)}</title>`)
  }

  if (output.includes('<!--app-head-->')) {
    output = output.replace('<!--app-head-->', headTags)
  } else if (headTags) {
    output = output.replace('</head>', `${headTags}\n</head>`)
  }

  return output
}

function injectAppHtml(html: string, appHtml: string) {
  if (html.includes('<!--app-html-->')) {
    return html.replace('<!--app-html-->', appHtml)
  }

  const rootPattern = /<div id="root">([\s\S]*?)<\/div>/
  if (rootPattern.test(html)) {
    return html.replace(rootPattern, `<div id="root">${appHtml}</div>`)
  }

  return html
}

function rewriteAssetPaths(html: string, slug: string) {
  const prefix = slug === 'index' ? 'assets/' : '../../assets/'
  return html.replace(/(["'])\/assets\//g, `$1${prefix}`)
}

function ensureDir(filePath: string) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
}

function renderPageHtml(props: AppProps) {
  return renderToString(React.createElement(App, props))
}

const schemas = readJson<PageSchema[]>(path.join(dataDir, 'schemas.json'), [fallbackSchema])
const tokens = readJson<Record<string, any>>(path.join(dataDir, 'tokens.json'), {})
const assets = readJson<Record<string, any>>(path.join(dataDir, 'assets.json'), {})

if (!fs.existsSync(distDir)) {
  throw new Error('dist directory not found. Run `vite build` before prerender.')
}

const baseHtml = fs.readFileSync(path.join(distDir, 'index.html'), 'utf-8')
const pageList = Array.isArray(schemas) && schemas.length ? schemas : [fallbackSchema]

pageList.forEach((page) => {
  const slug = normalizeSlug(page.slug)
  const appHtml = renderPageHtml({
    pageSlug: slug,
    schemas: pageList,
    tokens,
    assets,
  })

  const headTags = buildHeadTags(page.title, page.head)
  let html = injectHead(baseHtml, page.title, headTags)
  html = injectAppHtml(html, appHtml)
  html = rewriteAssetPaths(html, slug)

  const outputPath =
    slug === 'index'
      ? path.join(distDir, 'index.html')
      : path.join(distDir, 'pages', slug, 'index.html')

  ensureDir(outputPath)
  fs.writeFileSync(outputPath, html, 'utf-8')
})

console.log(`Prerendered ${pageList.length} page(s).`)
