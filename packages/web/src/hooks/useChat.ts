import * as React from 'react'
import { api } from '@/api/client'
import { toast } from '@/hooks/use-toast'
import type { ChatResponse, Message } from '@/types'

type ConnectionState = 'idle' | 'connecting' | 'open' | 'error' | 'closed'

const createId = () => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const safeJsonParse = (value: string) => {
  try {
    return JSON.parse(value)
  } catch {
    return null
  }
}

export interface UseChatOptions {
  sessionId?: string
  initialMessages?: Message[]
  messages?: Message[]
  setMessages?: React.Dispatch<React.SetStateAction<Message[]>>
  onPreview?: (payload: { html?: string; previewUrl?: string | null }) => void
}

export function useChat({
  sessionId,
  initialMessages = [],
  messages: controlledMessages,
  setMessages: setControlledMessages,
  onPreview,
}: UseChatOptions) {
  const [localMessages, setLocalMessages] = React.useState<Message[]>(initialMessages)
  const [isStreaming, setIsStreaming] = React.useState(false)
  const [connectionState, setConnectionState] = React.useState<ConnectionState>('idle')
  const [error, setError] = React.useState<string | null>(null)
  const eventSourceRef = React.useRef<EventSource | null>(null)
  const streamMessageIdRef = React.useRef<string | null>(null)
  const pendingMessageRef = React.useRef<string | null>(null)
  const receivedEventRef = React.useRef(false)

  const messages = controlledMessages ?? localMessages
  const setMessages = setControlledMessages ?? setLocalMessages

  React.useEffect(() => {
    if (controlledMessages) return
    setLocalMessages(initialMessages)
  }, [controlledMessages, initialMessages])

  const updateMessageById = React.useCallback(
    (id: string, updater: (message: Message) => Message) => {
      setMessages((prev) =>
        prev.map((message) => (message.id === id ? updater(message) : message))
      )
    },
    [setMessages]
  )

  const finishStream = React.useCallback(() => {
    const messageId = streamMessageIdRef.current
    if (messageId) {
      updateMessageById(messageId, (message) => ({
        ...message,
        isStreaming: false,
      }))
    }
    streamMessageIdRef.current = null
    pendingMessageRef.current = null
    receivedEventRef.current = false
    setIsStreaming(false)
    setConnectionState('closed')
  }, [updateMessageById])

  const stopStream = React.useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    finishStream()
  }, [finishStream])

  const fallbackSend = React.useCallback(
    async (content: string) => {
      if (!sessionId || !content.trim()) return
      try {
        const response = (await api.chat.send(sessionId, content.trim())) as ChatResponse
        const messageId = streamMessageIdRef.current
        if (response?.message && messageId) {
          updateMessageById(messageId, (message) => ({
            ...message,
            content: response.message ?? message.content,
          }))
        }
        if (response?.preview_html || response?.preview_url) {
          onPreview?.({
            html: response.preview_html ?? undefined,
            previewUrl: response.preview_url ?? undefined,
          })
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to send message'
        setError(message)
        toast({ title: 'Message failed', description: message })
        const messageId = streamMessageIdRef.current
        if (messageId) {
          updateMessageById(messageId, (message) => ({
            ...message,
            content: message.content || 'Sorry, something went wrong.',
            isStreaming: false,
          }))
        }
      } finally {
        finishStream()
      }
    },
    [finishStream, onPreview, sessionId, updateMessageById]
  )

  const startStream = React.useCallback(
    (content: string) => {
      if (!sessionId) return
      if (!content.trim()) return
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    const eventSource = new EventSource(api.chat.streamUrl(sessionId, content))
    eventSourceRef.current = eventSource
    setConnectionState('connecting')

    eventSource.onopen = () => {
      setConnectionState('open')
    }

    eventSource.onmessage = (event) => {
      if (event.data === '[DONE]') {
        stopStream()
        return
      }

      const payload = safeJsonParse(event.data)
      if (!payload || typeof payload !== 'object') return
      receivedEventRef.current = true

      const messageId = streamMessageIdRef.current
      const contentDelta =
        payload.delta ?? payload.token ?? payload.content ?? payload.message ?? payload.text
      const fullContent =
        payload.full_content ?? payload.fullContent ?? payload.output ?? payload.result
      const done = payload.done || payload.type === 'done'

      if (typeof fullContent === 'string' && messageId) {
        updateMessageById(messageId, (message) => ({
          ...message,
          content: fullContent,
        }))
      } else if (typeof contentDelta === 'string' && messageId) {
        updateMessageById(messageId, (message) => ({
          ...message,
          content: `${message.content}${contentDelta}`,
        }))
      }

      if (payload.preview_html || payload.previewHtml) {
        onPreview?.({ html: payload.preview_html ?? payload.previewHtml })
      }
      if (payload.preview_url || payload.previewUrl) {
        onPreview?.({ previewUrl: payload.preview_url ?? payload.previewUrl })
      }

      if (done) {
        stopStream()
      }
    }

    eventSource.onerror = () => {
      setConnectionState('error')
      setError('Stream connection lost')
      eventSource.close()
      eventSourceRef.current = null
      if (!receivedEventRef.current && pendingMessageRef.current) {
        const pending = pendingMessageRef.current
        pendingMessageRef.current = null
        void fallbackSend(pending)
        return
      }
      stopStream()
    }
  },
    [fallbackSend, onPreview, sessionId, stopStream, updateMessageById]
  )

  const sendMessage = React.useCallback(
    async (content: string) => {
      if (!sessionId || !content.trim()) return
      setError(null)

      const userMessage: Message = {
        id: createId(),
        role: 'user',
        content: content.trim(),
        timestamp: new Date(),
      }
      const assistantMessage: Message = {
        id: createId(),
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isStreaming: true,
      }

      streamMessageIdRef.current = assistantMessage.id
      pendingMessageRef.current = content.trim()
      receivedEventRef.current = false
      setMessages((prev) => [...prev, userMessage, assistantMessage])
      setIsStreaming(true)

      if (typeof EventSource === 'undefined') {
        await fallbackSend(content.trim())
        return
      }

      startStream(content.trim())
    },
    [fallbackSend, sessionId, setMessages, startStream]
  )

  React.useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  return {
    messages,
    isStreaming,
    connectionState,
    error,
    sendMessage,
    stopStream,
  }
}
