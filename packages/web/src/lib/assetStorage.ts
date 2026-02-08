import type { ChatAsset } from '@/types'

const STORAGE_PREFIX = 'instant-coffee:chat-assets:'

const getKey = (sessionId: string) => `${STORAGE_PREFIX}${sessionId}`

export const loadChatAssets = (sessionId?: string): ChatAsset[] => {
  if (!sessionId) return []
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(getKey(sessionId))
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (item): item is ChatAsset => Boolean(item && typeof item.id === 'string')
    )
  } catch {
    return []
  }
}

export const saveChatAssets = (sessionId: string, assets: ChatAsset[]) => {
  if (!sessionId) return
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(getKey(sessionId), JSON.stringify(assets))
  } catch {
    // ignore storage failures
  }
}

export const clearChatAssets = (sessionId?: string) => {
  if (!sessionId) return
  if (typeof window === 'undefined') return
  try {
    window.localStorage.removeItem(getKey(sessionId))
  } catch {
    // ignore
  }
}
