import type { InterviewBatch } from '@/types'

const STORAGE_PREFIX = 'instant-coffee:interview:'

const getKey = (sessionId: string) => `${STORAGE_PREFIX}${sessionId}`

export const loadInterviewBatch = (sessionId?: string): InterviewBatch | null => {
  if (!sessionId) return null
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(getKey(sessionId))
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    return parsed as InterviewBatch
  } catch {
    return null
  }
}

export const saveInterviewBatch = (sessionId: string, batch: InterviewBatch) => {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(getKey(sessionId), JSON.stringify(batch))
  } catch {
    // ignore storage failures (private mode / quota)
  }
}

export const clearInterviewBatch = (sessionId?: string) => {
  if (!sessionId) return
  if (typeof window === 'undefined') return
  try {
    window.localStorage.removeItem(getKey(sessionId))
  } catch {
    // ignore
  }
}
