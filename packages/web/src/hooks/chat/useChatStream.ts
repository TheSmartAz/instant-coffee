import * as React from 'react'
import { api, type RequestError, userFriendlyMessage } from '@/api/client'
import { createStreamDataHandler } from '@/hooks/chat/useStreamHandler'
import { createStreamConnection, type SendMessageOptions } from '@/hooks/chat/useStreamConnection'
import { clearPendingMessage } from '@/lib/pendingMessageStorage'
import { extractProductDocUpdateFields, PRODUCT_DOC_ACTIONS, type InterviewPayloadLike } from '@/hooks/useChatUtils'
import type { ChatAction, ChatRequestPayload, ChatResponse, ChatStep, Message } from '@/types'

type ConnectionState = 'idle' | 'connecting' | 'open' | 'error' | 'closed'

type RunAction = <T>(
  action: () => Promise<T>,
  options?: {
    onSuccess?: (value: T) => void | Promise<void>
    onError?: (error: RequestError) => void | Promise<void>
    onFinally?: () => void
    errorToast?:
      | { title: string; description?: string }
      | ((error: RequestError) => { title: string; description?: string })
    rethrow?: boolean
  }
) => Promise<T | undefined>

interface UseChatStreamOptions {
  sessionId?: string
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  setError: React.Dispatch<React.SetStateAction<string | null>>
  updateMessageById: (id: string, updater: (message: Message) => Message) => void
  runAction: RunAction
  resetInterviewState: () => void
  onPreview?: (payload: { html?: string; previewUrl?: string | null }) => void
  onTabChange?: (tab: 'preview' | 'code' | 'product-doc' | 'data') => void
  onPageSelect?: (slug: string) => void
  maybeNotifySessionCreated: (value: unknown) => void
  applyInterviewQuestions: (payload: InterviewPayloadLike) => boolean
  interviewModeRef: React.MutableRefObject<boolean>
  resumePendingRef: React.MutableRefObject<boolean>
  eventSourceRef: React.MutableRefObject<EventSource | null>
  fetchAbortRef: React.MutableRefObject<AbortController | null>
  streamMessageIdRef: React.MutableRefObject<string | null>
  pendingMessageRef: React.MutableRefObject<string | null>
  pendingOptionsRef: React.MutableRefObject<SendMessageOptions | null>
  receivedEventRef: React.MutableRefObject<boolean>
  receivedDeltaRef: React.MutableRefObject<boolean>
  sessionIdRef: React.MutableRefObject<string | undefined>
  threadIdRef: React.MutableRefObject<string | undefined | null>
}

export function useChatStream({
  sessionId,
  setMessages,
  setError,
  updateMessageById,
  runAction,
  resetInterviewState,
  onPreview,
  onTabChange,
  onPageSelect,
  maybeNotifySessionCreated,
  applyInterviewQuestions,
  interviewModeRef,
  resumePendingRef,
  eventSourceRef,
  fetchAbortRef,
  streamMessageIdRef,
  pendingMessageRef,
  pendingOptionsRef,
  receivedEventRef,
  receivedDeltaRef,
  sessionIdRef,
  threadIdRef,
}: UseChatStreamOptions) {
  const [isStreaming, setIsStreaming] = React.useState(false)
  const [connectionState, setConnectionState] = React.useState<ConnectionState>('idle')

  const appendStep = React.useCallback(
    (step: ChatStep, options?: { updateKey?: string }) => {
      const messageId = streamMessageIdRef.current
      if (!messageId) return
      updateMessageById(messageId, (message) => {
        const steps = message.steps ? [...message.steps] : []
        if (options?.updateKey) {
          const index = [...steps]
            .map((item) => item.key)
            .lastIndexOf(options.updateKey)
          if (index >= 0) {
            steps[index] = { ...steps[index], ...step, id: steps[index].id }
            return { ...message, steps }
          }
        }
        return { ...message, steps: [...steps, step] }
      })
    },
    [streamMessageIdRef, updateMessageById]
  )

  const finishStream = React.useCallback(() => {
    const messageId = streamMessageIdRef.current
    if (messageId) {
      updateMessageById(messageId, (message) => {
        const steps = message.steps?.some((item) => item.status === 'in_progress')
          ? message.steps.map((item) =>
              item.status === 'in_progress' ? { ...item, status: 'done' as const } : item
            )
          : message.steps
        return {
          ...message,
          isStreaming: false,
          steps,
        }
      })
    }
    streamMessageIdRef.current = null
    pendingMessageRef.current = null
    pendingOptionsRef.current = null
    receivedEventRef.current = false
    receivedDeltaRef.current = false
    setIsStreaming(false)
    setConnectionState('closed')
    if (sessionIdRef.current) {
      clearPendingMessage(sessionIdRef.current, threadIdRef.current ?? undefined)
    }
  }, [
    pendingMessageRef,
    pendingOptionsRef,
    receivedDeltaRef,
    receivedEventRef,
    sessionIdRef,
    streamMessageIdRef,
    threadIdRef,
    updateMessageById,
  ])

  const stopStream = React.useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    if (fetchAbortRef.current) {
      fetchAbortRef.current.abort()
      fetchAbortRef.current = null
    }
    finishStream()
  }, [eventSourceRef, fetchAbortRef, finishStream])

  const clearThread = React.useCallback(async () => {
    stopStream()
    setError(null)

    if (!sessionId) {
      setMessages([])
      resetInterviewState()
      return
    }

    await runAction(
      () => api.sessions.clearMessages(sessionId, threadIdRef.current ?? undefined),
      {
        onSuccess: () => {
          setMessages([])
          resetInterviewState()
        },
        onError: (error) => {
          setError(error.message || 'Failed to clear messages')
        },
        errorToast: (error) => ({
          title: 'Clear failed',
          description: error.message || 'Failed to clear messages',
        }),
        rethrow: true,
      }
    )
  }, [runAction, resetInterviewState, sessionId, setMessages, setError, stopStream, threadIdRef])

  const handleActionTabSwitch = React.useCallback(
    (action: ChatAction, activePageSlug?: string | null) => {
      switch (action) {
        case 'product_doc_generated':
        case 'product_doc_updated':
          onTabChange?.('product-doc')
          break
        case 'pages_generated':
        case 'page_refined':
          onTabChange?.('preview')
          if (activePageSlug) {
            onPageSelect?.(activePageSlug)
          }
          break
        case 'direct_reply':
        case 'product_doc_confirmed':
        default:
          break
      }
    },
    [onTabChange, onPageSelect]
  )

  const dispatchProductDocEvent = React.useCallback(
    (payload: {
      type: string
      doc_id?: string
      change_summary?: string
      section_name?: string
      section_content?: string
    }) => {
      if (typeof window === 'undefined') return
      if (!payload.type || !PRODUCT_DOC_ACTIONS.has(payload.type)) return
      window.dispatchEvent(new CustomEvent('product-doc-event', { detail: payload }))
    },
    []
  )

  const fallbackSend = React.useCallback(
    async (content: string, options?: SendMessageOptions) => {
      if (!content.trim()) return
      const currentSessionId = sessionIdRef.current
      await runAction(
        async () => {
          const payload: ChatRequestPayload = {
            session_id: currentSessionId,
            thread_id: threadIdRef.current ?? undefined,
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
          return (await api.chat.send(payload)) as ChatResponse
        },
        {
          onSuccess: (response) => {
            if (response?.session_id) {
              maybeNotifySessionCreated(response.session_id)
            }
            const messageId = streamMessageIdRef.current
            if (response?.message && messageId) {
              const {
                changeSummary: productDocChangeSummary,
                sectionName: productDocSectionName,
                sectionContent: productDocSectionContent,
              } = extractProductDocUpdateFields(response)
              const productDocUpdated =
                response.product_doc_updated === true ||
                response.action === 'product_doc_updated'

              updateMessageById(messageId, (message) => ({
                ...message,
                content: response.message ?? message.content,
                action: response.action ?? message.action,
                productDocUpdated: productDocUpdated || message.productDocUpdated,
                productDocChangeSummary:
                  productDocChangeSummary ?? message.productDocChangeSummary,
                productDocSectionName:
                  productDocSectionName ?? message.productDocSectionName,
                productDocSectionContent:
                  productDocSectionContent ?? message.productDocSectionContent,
                affectedPages: response.affected_pages ?? message.affectedPages,
                activePageSlug: response.active_page_slug ?? message.activePageSlug,
              }))
            }
            if (response?.preview_html || response?.preview_url) {
              onPreview?.({
                html: response.preview_html ?? undefined,
                previewUrl: response.preview_url ?? undefined,
              })
            }

            const {
              changeSummary: productDocChangeSummary,
              sectionName: productDocSectionName,
              sectionContent: productDocSectionContent,
            } = extractProductDocUpdateFields(response)

            if (response.action && PRODUCT_DOC_ACTIONS.has(response.action)) {
              dispatchProductDocEvent({
                type: response.action,
                change_summary: productDocChangeSummary,
                section_name: productDocSectionName,
                section_content: productDocSectionContent,
              })
            } else if (response.product_doc_updated) {
              dispatchProductDocEvent({
                type: 'product_doc_updated',
                change_summary: productDocChangeSummary,
                section_name: productDocSectionName,
                section_content: productDocSectionContent,
              })
            }

            if (response.action) {
              handleActionTabSwitch(response.action, response.active_page_slug)
            }
          },
          onError: (error) => {
            const message = userFriendlyMessage(error)
            setError(message)
            const messageId = streamMessageIdRef.current
            if (messageId) {
              updateMessageById(messageId, (message) => ({
                ...message,
                content: message.content || 'Sorry, something went wrong.',
                isStreaming: false,
              }))
            }
          },
          errorToast: { title: 'Message failed' },
          onFinally: () => {
            finishStream()
          },
        }
      )
    },
    [
      runAction,
      sessionIdRef,
      threadIdRef,
      maybeNotifySessionCreated,
      streamMessageIdRef,
      updateMessageById,
      onPreview,
      dispatchProductDocEvent,
      handleActionTabSwitch,
      setError,
      finishStream,
    ]
  )

  const handleStreamDataRef = React.useRef<(data: string) => void>(() => undefined)
  React.useEffect(() => {
    handleStreamDataRef.current = createStreamDataHandler({
      streamMessageIdRef,
      receivedEventRef,
      receivedDeltaRef,
      interviewModeRef,
      resumePendingRef,
      stopStream,
      maybeNotifySessionCreated,
      applyInterviewQuestions,
      appendStep,
      updateMessageById,
      dispatchProductDocEvent,
      handleActionTabSwitch,
      onPreview,
    })
  }, [
    streamMessageIdRef,
    receivedEventRef,
    receivedDeltaRef,
    interviewModeRef,
    resumePendingRef,
    stopStream,
    maybeNotifySessionCreated,
    applyInterviewQuestions,
    appendStep,
    updateMessageById,
    dispatchProductDocEvent,
    handleActionTabSwitch,
    onPreview,
  ])

  const streamConnectionRef = React.useRef<ReturnType<typeof createStreamConnection> | null>(null)
  React.useEffect(() => {
    streamConnectionRef.current = createStreamConnection({
      eventSourceRef,
      fetchAbortRef,
      receivedEventRef,
      pendingMessageRef,
      pendingOptionsRef,
      sessionIdRef,
      threadIdRef,
      setConnectionState,
      setError,
      handleStreamData: (data) => handleStreamDataRef.current(data),
      fallbackSend,
      finishStream,
      stopStream,
    })
  }, [
    eventSourceRef,
    fetchAbortRef,
    receivedEventRef,
    pendingMessageRef,
    pendingOptionsRef,
    sessionIdRef,
    threadIdRef,
    setError,
    fallbackSend,
    finishStream,
    stopStream,
  ])

  const startStream = React.useCallback((content: string, options?: SendMessageOptions) => {
    streamConnectionRef.current?.startStream(content, options)
  }, [])

  const startFetchStream = React.useCallback(
    async (content: string, options?: SendMessageOptions) => {
      await streamConnectionRef.current?.startFetchStream(content, options)
    },
    []
  )

  const enqueueConversation = React.useCallback(
    async (
      userMessage: Message,
      assistantMessage: Message,
      rawContent: string,
      options?: SendMessageOptions
    ) => {
      if (isStreaming) {
        stopStream()
      }
      streamMessageIdRef.current = assistantMessage.id
      pendingMessageRef.current = rawContent
      pendingOptionsRef.current = options ?? null
      receivedEventRef.current = false
      receivedDeltaRef.current = false
      setMessages((prev) => [...prev, userMessage, assistantMessage])
      setIsStreaming(true)

      const requiresPostStream = Boolean(
        options?.attachments?.length ||
          options?.targetPages?.length ||
          options?.mentionedFiles?.length ||
          options?.styleReference ||
          options?.resume
      )

      if (requiresPostStream) {
        if (typeof fetch === 'undefined' || typeof ReadableStream === 'undefined') {
          await fallbackSend(rawContent, options)
          return
        }
        await startFetchStream(rawContent, options)
        return
      }

      if (typeof EventSource === 'undefined') {
        await fallbackSend(rawContent, options)
        return
      }

      startStream(rawContent, options)
    },
    [
      isStreaming,
      stopStream,
      streamMessageIdRef,
      pendingMessageRef,
      pendingOptionsRef,
      receivedEventRef,
      receivedDeltaRef,
      setMessages,
      fallbackSend,
      startFetchStream,
      startStream,
    ]
  )

  React.useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
      if (fetchAbortRef.current) {
        fetchAbortRef.current.abort()
      }
    }
  }, [eventSourceRef, fetchAbortRef])

  return {
    isStreaming,
    connectionState,
    enqueueConversation,
    stopStream,
    clearThread,
  }
}
