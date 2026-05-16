import * as React from 'react'
import { api, type RequestError, userFriendlyMessage } from '@/api/client'
import { createStreamDataHandler } from '@/hooks/chat/useStreamHandler'
import { createStreamConnection, type SendMessageOptions } from '@/hooks/chat/useStreamConnection'
import { clearPendingMessage } from '@/lib/pendingMessageStorage'
import { extractProductDocUpdateFields, PRODUCT_DOC_ACTIONS, type InterviewPayloadLike } from '@/hooks/useChatUtils'
import type { ChatAction, ChatRequestPayload, ChatResponse, ChatRunStatus, ChatStep, Message } from '@/types'

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
  onRunStatusChange?: (status: ChatRunStatus | null) => void
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
  onRunStatusChange,
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
  const handleStreamDataRef = React.useRef<((data: string) => void) & { destroy?: () => void }>(() => undefined)
  const runEventSourceRef = React.useRef<EventSource | null>(null)
  const runEventRunIdRef = React.useRef<string | null>(null)

  const closeRunEventStream = React.useCallback(() => {
    if (runEventSourceRef.current) {
      runEventSourceRef.current.close()
      runEventSourceRef.current = null
    }
    runEventRunIdRef.current = null
  }, [])

  const isTerminalRunStatus = React.useCallback((status: ChatRunStatus) => {
    const normalized = (status.status ?? '').toLowerCase()
    return (
      normalized === 'completed' ||
      normalized === 'failed' ||
      normalized === 'cancelled' ||
      status.eventType === 'run_completed' ||
      status.eventType === 'run_failed' ||
      status.eventType === 'run_cancelled'
    )
  }, [])

  const runDetailToStatus = React.useCallback(
    (run: import('@/types').SessionRunDetail): ChatRunStatus => ({
      eventType:
        run.status === 'completed'
          ? 'run_completed'
          : run.status === 'failed'
            ? 'run_failed'
            : run.status === 'cancelled'
              ? 'run_cancelled'
              : run.status === 'waiting_input'
                ? 'run_waiting_input'
                : 'run_phase',
      stage: 'run',
      runId: run.run_id,
      executionMode: run.execution_mode ?? run.executionMode ?? run.approval_mode ?? undefined,
      phase: run.current_phase ?? undefined,
      status: run.status,
      message: run.waiting_reason ?? undefined,
      error:
        typeof run.latest_error?.message === 'string'
          ? run.latest_error.message
          : undefined,
      summary: run.phase_metadata,
      updatedAt: run.updated_at ?? undefined,
    }),
    [],
  )

  const reconcileRunStatus = React.useCallback(
    async (runId: string) => {
      try {
        const run = await api.runs.get(runId)
        handleStreamDataRef.current(
          JSON.stringify({
            type:
              run.status === 'completed'
                ? 'run_completed'
                : run.status === 'failed'
                  ? 'run_failed'
                  : run.status === 'cancelled'
                    ? 'run_cancelled'
                    : run.status === 'waiting_input'
                      ? 'run_waiting_input'
                      : 'run_phase',
            run_id: run.run_id,
            execution_mode: run.execution_mode ?? run.executionMode ?? run.approval_mode,
            phase: run.current_phase,
            status: run.status,
            waiting_reason: run.waiting_reason,
            timestamp: run.updated_at,
          }),
        )
      } catch {
        // Keep the last streamed state when reconciliation is unavailable.
      }
    },
    [],
  )

  const subscribeRunEventStream = React.useCallback(
    (runId: string) => {
      if (runEventRunIdRef.current === runId && runEventSourceRef.current) return
      closeRunEventStream()

      const eventSource = new EventSource(api.runs.streamUrl(runId))
      runEventSourceRef.current = eventSource
      runEventRunIdRef.current = runId

      eventSource.onmessage = (event) => {
        if (event.data === '[DONE]') {
          closeRunEventStream()
          void reconcileRunStatus(runId)
          return
        }
        handleStreamDataRef.current(event.data)
      }

      eventSource.onerror = () => {
        closeRunEventStream()
        void reconcileRunStatus(runId)
      }
    },
    [closeRunEventStream, reconcileRunStatus],
  )

  const handleRunStatusChange = React.useCallback(
    (status: ChatRunStatus | null) => {
      onRunStatusChange?.(status)
      if (!status?.runId) return
      if (isTerminalRunStatus(status)) {
        closeRunEventStream()
        return
      }
      subscribeRunEventStream(status.runId)
    },
    [closeRunEventStream, isTerminalRunStatus, onRunStatusChange, subscribeRunEventStream],
  )

  React.useEffect(() => {
    if (!sessionId || isStreaming) return
    let active = true

    const restoreActiveRun = async () => {
      try {
        const response = await api.runs.list(sessionId, { limit: 1 })
        if (!active) return
        const latestRun = response.runs?.[0]
        if (!latestRun) return
        if (!['queued', 'running', 'waiting_input'].includes(latestRun.status)) return
        handleRunStatusChange(runDetailToStatus(latestRun))
      } catch {
        // Run status recovery is best-effort; the persisted chat still renders.
      }
    }

    void restoreActiveRun()
    return () => {
      active = false
    }
  }, [handleRunStatusChange, isStreaming, runDetailToStatus, sessionId])

  const appendStep = React.useCallback(
    (step: ChatStep, options?: { updateKey?: string }) => {
      const messageId = streamMessageIdRef.current
      if (!messageId) return
      updateMessageById(messageId, (message) => {
        // Update flat steps array (backward compat)
        const steps = message.steps ? [...message.steps] : []
        if (options?.updateKey) {
          const index = [...steps]
            .map((item) => item.key)
            .lastIndexOf(options.updateKey)
          if (index >= 0) {
            steps[index] = { ...steps[index], ...step, id: steps[index].id }
          } else {
            steps.push(step)
          }
        } else {
          steps.push(step)
        }

        // Update segments — ensure last segment is a tool_group
        const segments = message.segments ? [...message.segments] : []
        const lastSeg = segments[segments.length - 1]
        if (lastSeg && lastSeg.type === 'tool_group') {
          const groupSteps = [...lastSeg.steps]
          if (options?.updateKey) {
            const idx = groupSteps.map((s) => s.key).lastIndexOf(options.updateKey)
            if (idx >= 0) {
              groupSteps[idx] = { ...groupSteps[idx], ...step, id: groupSteps[idx].id }
            } else {
              groupSteps.push(step)
            }
          } else {
            groupSteps.push(step)
          }
          segments[segments.length - 1] = { type: 'tool_group', steps: groupSteps }
        } else {
          segments.push({ type: 'tool_group', steps: [step] })
        }

        return { ...message, steps, segments }
      })
    },
    [streamMessageIdRef, updateMessageById]
  )

  const appendTextSegment = React.useCallback(
    (text: string) => {
      const messageId = streamMessageIdRef.current
      if (!messageId) return
      updateMessageById(messageId, (message) => {
        const segments = message.segments ? [...message.segments] : []
        const lastSeg = segments[segments.length - 1]
        if (lastSeg && lastSeg.type === 'text') {
          segments[segments.length - 1] = { type: 'text', content: lastSeg.content + text }
        } else {
          segments.push({ type: 'text', content: text })
        }
        return { ...message, segments }
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

        // Also finalize segments
        const segments = message.segments?.map((seg) => {
          if (seg.type !== 'tool_group') return seg
          const hasInProgress = seg.steps.some((s) => s.status === 'in_progress')
          if (!hasInProgress) return seg
          return {
            ...seg,
            steps: seg.steps.map((s) =>
              s.status === 'in_progress' ? { ...s, status: 'done' as const } : s
            ),
          }
        })

        // Filter out empty text segments
        const cleanSegments = segments?.filter(
          (seg) => seg.type !== 'text' || seg.content.trim().length > 0
        )

        return {
          ...message,
          isStreaming: false,
          steps,
          segments: cleanSegments,
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
            execution_mode: options?.executionMode ?? options?.approvalMode,
            executionMode: options?.executionMode ?? options?.approvalMode,
            approval_mode: options?.approvalMode ?? options?.executionMode,
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

  React.useEffect(() => {
    // Destroy previous handler's delta buffer
    handleStreamDataRef.current.destroy?.()
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
      appendTextSegment,
      updateMessageById,
      dispatchProductDocEvent,
      handleActionTabSwitch,
      onRunStatusChange: handleRunStatusChange,
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
    appendTextSegment,
    updateMessageById,
    dispatchProductDocEvent,
    handleActionTabSwitch,
    handleRunStatusChange,
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
      closeRunEventStream()
    }
  }, [closeRunEventStream, eventSourceRef, fetchAbortRef])

  return {
    isStreaming,
    connectionState,
    enqueueConversation,
    stopStream,
    clearThread,
  }
}
