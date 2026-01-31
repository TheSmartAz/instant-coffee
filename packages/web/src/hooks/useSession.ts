import * as React from 'react'
import { api } from '@/api/client'
import type { Message, SessionDetail, Version } from '@/types'

type ApiSession = {
  id: string
  title?: string
  created_at?: string
  updated_at?: string
  current_version?: number
  preview_url?: string | null
  preview_html?: string | null
}

type ApiMessage = {
  id?: string
  role?: string
  content?: string
  message?: string
  created_at?: string
  timestamp?: string
}

type ApiVersion = {
  id?: string
  version?: number
  number?: number
  created_at?: string
  description?: string
  is_current?: boolean
  preview_url?: string | null
  preview_html?: string | null
}

const toDate = (value?: string) => (value ? new Date(value) : new Date())

const normalizePreviewUrl = (value?: string | null) =>
  value && /^https?:\/\//i.test(value) ? value : undefined

const mapSession = (session: ApiSession): SessionDetail => ({
  id: session.id,
  title: session.title ?? 'Untitled project',
  createdAt: toDate(session.created_at),
  updatedAt: toDate(session.updated_at),
  currentVersion: session.current_version,
  previewUrl: normalizePreviewUrl(session.preview_url),
  previewHtml: session.preview_html ?? undefined,
})

const mapMessage = (message: ApiMessage, index: number): Message => ({
  id: message.id ?? `m-${index}-${Date.now()}`,
  role: message.role === 'user' ? 'user' : 'assistant',
  content: message.content ?? message.message ?? '',
  timestamp: toDate(message.created_at ?? message.timestamp),
})

const mapVersion = (
  version: ApiVersion,
  currentVersion?: number
): Version => {
  const number = version.version ?? version.number ?? 0
  return {
    id: version.id ?? `v-${number}`,
    number,
    createdAt: toDate(version.created_at),
    isCurrent: version.is_current ?? number === currentVersion,
    description: version.description,
    previewUrl: normalizePreviewUrl(version.preview_url),
    previewHtml: version.preview_html ?? undefined,
  }
}

export function useSession(sessionId?: string) {
  const [session, setSession] = React.useState<SessionDetail | null>(null)
  const [messages, setMessages] = React.useState<Message[]>([])
  const [versions, setVersions] = React.useState<Version[]>([])
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const refresh = React.useCallback(async () => {
    if (!sessionId) return
    setIsLoading(true)
    setError(null)
    try {
      const [sessionResponse, messagesResponse, versionsResponse] =
        await Promise.all([
          api.sessions.get(sessionId),
          api.sessions.messages(sessionId),
          api.sessions.versions(sessionId),
        ])

      if (sessionResponse) {
        setSession(mapSession(sessionResponse as ApiSession))
      }

      const messagesList = Array.isArray(messagesResponse)
        ? messagesResponse
        : (messagesResponse as { messages?: ApiMessage[] })?.messages ?? []
      setMessages(messagesList.map(mapMessage))

      const versionsPayload = versionsResponse as {
        versions?: ApiVersion[]
        current_version?: number
      }
      const currentVersion = versionsPayload?.current_version
      const versionList = Array.isArray(versionsResponse)
        ? versionsResponse
        : versionsPayload?.versions ?? []
      setVersions(versionList.map((item) => mapVersion(item, currentVersion)))
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load session'
      setError(message)
      return false
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

  React.useEffect(() => {
    let active = true
    if (!sessionId) return
    const load = async () => {
      setIsLoading(true)
      try {
        const [sessionResponse, messagesResponse, versionsResponse] =
          await Promise.all([
            api.sessions.get(sessionId),
            api.sessions.messages(sessionId),
            api.sessions.versions(sessionId),
          ])
        if (!active) return

        if (sessionResponse) {
          setSession(mapSession(sessionResponse as ApiSession))
        }

        const messagesList = Array.isArray(messagesResponse)
          ? messagesResponse
          : (messagesResponse as { messages?: ApiMessage[] })?.messages ?? []
        setMessages(messagesList.map(mapMessage))

        const versionsPayload = versionsResponse as {
          versions?: ApiVersion[]
          current_version?: number
        }
        const currentVersion = versionsPayload?.current_version
        const versionList = Array.isArray(versionsResponse)
          ? versionsResponse
          : versionsPayload?.versions ?? []
        setVersions(versionList.map((item) => mapVersion(item, currentVersion)))
      } catch (err) {
        if (!active) return
        const message = err instanceof Error ? err.message : 'Failed to load session'
        setError(message)
      } finally {
        if (active) setIsLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [sessionId])

  return {
    session,
    messages,
    versions,
    isLoading,
    error,
    refresh,
    setMessages,
    setVersions,
    setSession,
  }
}
