const HOME_PROMPT_PREFIX = 'instant-coffee:home-prompt:'

const keyFor = (sessionId: string) => `${HOME_PROMPT_PREFIX}${sessionId}`

export const saveHomePrompt = (sessionId: string, prompt: string) => {
  if (!sessionId || typeof window === 'undefined') return
  try {
    window.sessionStorage.setItem(keyFor(sessionId), prompt)
  } catch {
    // ignore storage failures
  }
}

export const consumeHomePrompt = (sessionId?: string): string | null => {
  if (!sessionId || typeof window === 'undefined') return null
  try {
    const key = keyFor(sessionId)
    const value = window.sessionStorage.getItem(key)
    window.sessionStorage.removeItem(key)
    return value
  } catch {
    return null
  }
}
