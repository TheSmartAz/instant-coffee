import type { Page } from '@/types'

const MENTION_PATTERN = /@([A-Za-z0-9_-]+)/g

export const parsePageMentions = (message: string, pages?: Page[]): string[] => {
  if (!message) return []
  const matches = message.match(MENTION_PATTERN)
  if (!matches || matches.length === 0) return []

  const normalized = new Set<string>()
  const pageLookup = pages?.length
    ? new Map(pages.map((page) => [page.slug.toLowerCase(), page.slug]))
    : null

  for (const raw of matches) {
    const slug = raw.slice(1)
    const key = slug.toLowerCase()
    const resolved = pageLookup?.get(key) ?? key
    if (resolved) normalized.add(resolved)
  }

  return Array.from(normalized)
}

export const filterPages = (pages: Page[], query: string) => {
  const value = query.trim().toLowerCase()
  if (!value) return pages
  return pages.filter((page) => {
    const slug = page.slug.toLowerCase()
    const title = (page.title || '').toLowerCase()
    return slug.includes(value) || title.includes(value)
  })
}
