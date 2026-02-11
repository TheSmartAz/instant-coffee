import type { ChatStep, Message } from '@/types'

type StoredChatStep = Omit<ChatStep, 'timestamp'> & { timestamp?: string }

type StoredMessage = Omit<Message, 'timestamp' | 'steps'> & {
  timestamp?: string
  steps?: StoredChatStep[]
}

export type PendingMessageRecord = {
  assistant: StoredMessage
  user?: {
    content?: string
    timestamp?: string
  }
  savedAt: string
}

const STORAGE_PREFIX = 'instant-coffee:pending-message:'

const getKey = (sessionId: string, threadId?: string) =>
  threadId
    ? `${STORAGE_PREFIX}${sessionId}:${threadId}`
    : `${STORAGE_PREFIX}${sessionId}`

export const toStoredChatStep = (step: ChatStep): StoredChatStep => ({
  ...step,
  timestamp: step.timestamp ? step.timestamp.toISOString() : undefined,
})

export const toStoredMessage = (message: Message): StoredMessage => ({
  ...message,
  timestamp: message.timestamp ? message.timestamp.toISOString() : undefined,
  steps: message.steps?.map(toStoredChatStep),
})

export const fromStoredMessage = (stored: StoredMessage): Message => ({
  ...stored,
  timestamp: stored.timestamp ? new Date(stored.timestamp) : undefined,
  steps: stored.steps?.map((step) => ({
    ...step,
    timestamp: step.timestamp ? new Date(step.timestamp) : undefined,
  })),
})

export const loadPendingMessage = (sessionId?: string, threadId?: string): PendingMessageRecord | null => {
  if (!sessionId) return null
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(getKey(sessionId, threadId))
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    return parsed as PendingMessageRecord
  } catch {
    return null
  }
}

export const savePendingMessage = (sessionId: string, record: PendingMessageRecord, threadId?: string) => {
  if (!sessionId) return
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(getKey(sessionId, threadId), JSON.stringify(record))
  } catch {
    // ignore storage failures
  }
}

export const clearPendingMessage = (sessionId?: string, threadId?: string) => {
  if (!sessionId) return
  if (typeof window === 'undefined') return
  try {
    window.localStorage.removeItem(getKey(sessionId, threadId))
  } catch {
    // ignore
  }
}
