import { formatDistanceToNow } from 'date-fns'

type RelativeDateInput = Date | string | number | null | undefined

const toDate = (value: RelativeDateInput): Date => {
  if (value instanceof Date) return value
  if (typeof value === 'string' || typeof value === 'number') {
    const parsed = new Date(value)
    if (!Number.isNaN(parsed.getTime())) return parsed
  }
  return new Date()
}

export const formatRelativeDate = (value: RelativeDateInput): string =>
  formatDistanceToNow(toDate(value), { addSuffix: true })

