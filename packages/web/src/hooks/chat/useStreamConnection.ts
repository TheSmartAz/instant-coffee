import { api, API_BASE, classifyError, userFriendlyMessage } from '@/api/client'
import type { ChatRequestPayload, ChatAttachment, ChatStyleReference, ImageIntent } from '@/types'

type ConnectionState = 'idle' | 'connecting' | 'open' | 'error' | 'closed'

export interface SendMessageOptions {
  triggerInterview?: boolean
  generateNow?: boolean
  attachments?: ChatAttachment[]
  imageIntent?: ImageIntent
  targetPages?: string[]
  mentionedFiles?: string[]
  styleReference?: ChatStyleReference
  resume?: Record<string, unknown>
}

export interface StreamConnectionDeps {
  eventSourceRef: { current: EventSource | null }
  fetchAbortRef: { current: AbortController | null }
  receivedEventRef: { current: boolean }
  pendingMessageRef: { current: string | null }
  pendingOptionsRef: { current: SendMessageOptions | null }
  sessionIdRef: { current: string | undefined }
  threadIdRef: { current: string | null | undefined }
  setConnectionState: (state: ConnectionState) => void
  setError: (error: string | null) => void
  handleStreamData: (data: string) => void
  fallbackSend: (content: string, options?: SendMessageOptions) => Promise<void>
  finishStream: () => void
  stopStream: () => void
}

/** Close any existing EventSource / fetch controller before opening a new stream. */
function prepareStream(deps: StreamConnectionDeps) {
  if (deps.eventSourceRef.current) {
    deps.eventSourceRef.current.close()
    deps.eventSourceRef.current = null
  }
  if (deps.fetchAbortRef.current) {
    deps.fetchAbortRef.current.abort()
    deps.fetchAbortRef.current = null
  }
  deps.setConnectionState('connecting')
}

/** Shared error path for both EventSource and fetch streams. */
function handleStreamError(
  deps: StreamConnectionDeps,
  errorMessage: string,
) {
  deps.setConnectionState('error')
  if (!deps.receivedEventRef.current && deps.pendingMessageRef.current) {
    const pending = deps.pendingMessageRef.current
    const pendingOptions = deps.pendingOptionsRef.current ?? undefined
    deps.pendingMessageRef.current = null
    deps.pendingOptionsRef.current = null
    void deps.fallbackSend(pending, pendingOptions)
    return
  }
  deps.setError(errorMessage)
  deps.stopStream()
}

function buildPayload(
  deps: StreamConnectionDeps,
  content: string,
  options?: SendMessageOptions,
): ChatRequestPayload {
  const payload: ChatRequestPayload = {
    session_id: deps.sessionIdRef.current,
    thread_id: deps.threadIdRef.current ?? undefined,
    message: content.trim(),
    interview: options?.triggerInterview,
    generate_now: options?.generateNow,
  }
  if (options?.attachments?.length) {
    payload.images = options.attachments
      .map((attachment) => attachment.data)
      .filter(Boolean)
    if (options.imageIntent) {
      payload.image_intent = options.imageIntent
    }
  }
  if (options?.targetPages?.length) {
    payload.target_pages = options.targetPages
  }
  if (options?.styleReference) {
    payload.style_reference = options.styleReference
  }
  if (options?.resume) {
    payload.resume = options.resume
  }
  if (options?.mentionedFiles?.length) {
    payload.mentioned_files = options.mentionedFiles
  }
  return payload
}

export function createStreamConnection(deps: StreamConnectionDeps) {
  const startStream = (content: string, options?: SendMessageOptions) => {
    if (!content.trim()) return
    prepareStream(deps)

    const eventSource = new EventSource(
      api.chat.streamUrl(deps.sessionIdRef.current, content, {
        interview: options?.triggerInterview,
        generateNow: options?.generateNow,
      })
    )
    deps.eventSourceRef.current = eventSource

    eventSource.onopen = () => {
      deps.setConnectionState('open')
    }

    eventSource.onmessage = (event) => {
      deps.handleStreamData(event.data)
    }

    eventSource.onerror = () => {
      eventSource.close()
      deps.eventSourceRef.current = null
      handleStreamError(
        deps,
        'Stream connection lost — try sending your message again.',
      )
    }
  }

  const startFetchStream = async (content: string, options?: SendMessageOptions) => {
    if (!content.trim()) return
    prepareStream(deps)

    const controller = new AbortController()
    deps.fetchAbortRef.current = controller

    const payload = buildPayload(deps, content, options)

    try {
      const base = API_BASE.endsWith('/') ? API_BASE.slice(0, -1) : API_BASE
      const response = await fetch(`${base}/api/chat/stream`, {
        method: 'POST',
        headers: {
          Accept: 'text/event-stream',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      })

      if (!response.ok || !response.body) {
        throw new Error('Stream connection failed')
      }

      deps.setConnectionState('open')
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''
        for (const part of parts) {
          const lines = part.split('\n')
          for (const line of lines) {
            if (!line.startsWith('data:')) continue
            const data = line.replace(/^data:\s?/, '')
            if (!data) continue
            deps.handleStreamData(data)
          }
        }
      }

      if (buffer.trim()) {
        const lines = buffer.split('\n')
        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          const data = line.replace(/^data:\s?/, '')
          if (!data) continue
          deps.handleStreamData(data)
        }
      }
      if (!controller.signal.aborted) {
        deps.stopStream()
      }
    } catch (err) {
      if (controller.signal.aborted) return
      const classified = classifyError(err)
      handleStreamError(deps, userFriendlyMessage(classified))
    } finally {
      if (deps.fetchAbortRef.current === controller) {
        deps.fetchAbortRef.current = null
      }
    }
  }

  return { startStream, startFetchStream }
}
