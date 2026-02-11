type AnyRecord = Record<string, unknown>

const toCamel = (value: string) =>
  value.replace(/_([a-z])/g, (_, char: string) => char.toUpperCase())

const toSnake = (value: string) =>
  value
    .replace(/([A-Z])/g, '_$1')
    .replace(/__+/g, '_')
    .toLowerCase()
    .replace(/^_/, '')

const resolveKeyCandidates = (key: string) => {
  const camel = toCamel(key)
  const snake = toSnake(key)
  return Array.from(new Set([key, camel, snake]))
}

export const getCaseValue = <T = unknown>(
  source: unknown,
  key: string,
  options?: { fallback?: T }
): T | undefined => {
  if (!source || typeof source !== 'object') return options?.fallback
  const record = source as AnyRecord
  for (const candidate of resolveKeyCandidates(key)) {
    if (candidate in record) {
      return record[candidate] as T
    }
  }
  return options?.fallback
}

export const getCaseString = (
  source: unknown,
  key: string,
  options?: { trim?: boolean }
): string | undefined => {
  const raw = getCaseValue<unknown>(source, key)
  if (typeof raw !== 'string') return undefined
  const trim = options?.trim ?? true
  const normalized = trim ? raw.trim() : raw
  return normalized.trim().length === 0 ? undefined : normalized
}

export const getCaseArray = <T = unknown>(
  source: unknown,
  key: string
): T[] | undefined => {
  const raw = getCaseValue<unknown>(source, key)
  return Array.isArray(raw) ? (raw as T[]) : undefined
}

