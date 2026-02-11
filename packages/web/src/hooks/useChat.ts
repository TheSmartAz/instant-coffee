import * as React from 'react'
import { useAsyncAction } from '@/hooks/useAsyncAction'
import { useChatAssets } from '@/hooks/chat/useChatAssets'
import { useChatInterview } from '@/hooks/chat/useChatInterview'
import { useChatStream } from '@/hooks/chat/useChatStream'
import type { SendMessageOptions } from '@/hooks/chat/useStreamConnection'
import { clearInterviewBatch } from '@/lib/interviewStorage'
import { savePendingMessage, toStoredMessage } from '@/lib/pendingMessageStorage'
import { createId, buildInterviewPayload } from '@/hooks/useChatUtils'
import type { InterviewActionPayload, Message } from '@/types'

export interface UseChatOptions {
  sessionId?: string
  threadId?: string
  initialMessages?: Message[]
  messages?: Message[]
  setMessages?: React.Dispatch<React.SetStateAction<Message[]>>
  onPreview?: (payload: { html?: string; previewUrl?: string | null }) => void
  onTabChange?: (tab: 'preview' | 'code' | 'product-doc' | 'data') => void
  onPageSelect?: (slug: string) => void
  onSessionCreated?: (sessionId: string) => void
}

export type { SendMessageOptions }

export function useChat({
  sessionId,
  threadId,
  initialMessages = [],
  messages: controlledMessages,
  setMessages: setControlledMessages,
  onPreview,
  onTabChange,
  onPageSelect,
  onSessionCreated,
}: UseChatOptions) {
  const { runAction } = useAsyncAction()
  const [localMessages, setLocalMessages] = React.useState<Message[]>(initialMessages)
  const [error, setError] = React.useState<string | null>(null)
  const eventSourceRef = React.useRef<EventSource | null>(null)
  const fetchAbortRef = React.useRef<AbortController | null>(null)
  const streamMessageIdRef = React.useRef<string | null>(null)
  const pendingMessageRef = React.useRef<string | null>(null)
  const pendingOptionsRef = React.useRef<SendMessageOptions | null>(null)
  const receivedEventRef = React.useRef(false)
  const receivedDeltaRef = React.useRef(false)
  const sessionIdRef = React.useRef(sessionId)
  const threadIdRef = React.useRef(threadId)
  const createdSessionIdRef = React.useRef<string | null>(null)

  const messages = controlledMessages ?? localMessages
  const setMessages = setControlledMessages ?? setLocalMessages

  const {
    assets,
    addAsset,
    removeAsset,
    getAssetById,
    uploadAsset,
  } = useChatAssets({
    sessionId,
    sessionIdRef,
    setMessages,
  })

  const persistPendingMessage = React.useCallback(
    (message: Message) => {
      const currentSessionId = sessionIdRef.current
      if (!currentSessionId) return
      savePendingMessage(
        currentSessionId,
        {
          assistant: toStoredMessage(message),
          savedAt: new Date().toISOString(),
        },
        threadIdRef.current ?? undefined
      )
    },
    []
  )

  React.useEffect(() => {
    if (controlledMessages) return
    setLocalMessages(initialMessages)
  }, [controlledMessages, initialMessages])

  React.useEffect(() => {
    sessionIdRef.current = sessionId
    if (sessionId) {
      createdSessionIdRef.current = null
    }
  }, [sessionId])

  React.useEffect(() => {
    threadIdRef.current = threadId
  }, [threadId])

  const maybeNotifySessionCreated = React.useCallback(
    (value: unknown) => {
      if (typeof value !== 'string' || !value) return
      if (sessionIdRef.current) return
      if (createdSessionIdRef.current === value) return
      createdSessionIdRef.current = value
      sessionIdRef.current = value
      onSessionCreated?.(value)
    },
    [onSessionCreated]
  )

  const updateMessageById = React.useCallback(
    (id: string, updater: (message: Message) => Message) => {
      setMessages((prev) =>
        prev.map((message) => (message.id === id ? updater(message) : message))
      )
    },
    [setMessages]
  )

  const {
    interviewAnswersRef,
    interviewModeRef,
    resumePendingRef,
    updateInterviewByBatchId,
    setInterviewSummaryByBatchId,
    mergeInterviewAnswers,
    resetInterviewState,
    applyInterviewQuestions,
  } = useChatInterview({
    sessionId,
    messages,
    setMessages,
    updateMessageById,
    streamMessageIdRef,
    receivedEventRef,
    threadIdRef,
  })

  const {
    isStreaming,
    connectionState,
    enqueueConversation,
    stopStream,
    clearThread,
  } = useChatStream({
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
  })

  React.useEffect(() => {
    if (!isStreaming) return
    const currentSessionId = sessionIdRef.current
    if (!currentSessionId) return
    const streamMessageId = streamMessageIdRef.current
    const pendingMessage =
      (streamMessageId
        ? messages.find((message) => message.id === streamMessageId)
        : messages
            .slice()
            .reverse()
            .find((message) => message.role === 'assistant' && message.isStreaming)) ?? null
    if (!pendingMessage) return
    persistPendingMessage(pendingMessage)
  }, [isStreaming, messages, persistPendingMessage])

  const sendMessage = React.useCallback(
    async (content: string, options?: SendMessageOptions) => {
      if (!content.trim()) return
      setError(null)

      const trimmed = content.trim()
      const resumePayload = resumePendingRef.current
        ? { user_feedback: trimmed }
        : options?.resume
      if (resumePendingRef.current) {
        resumePendingRef.current = false
      }
      const shouldTriggerInterview = resumePayload
        ? false
        : options?.triggerInterview ?? interviewModeRef.current
      const generateNow = options?.generateNow

      const allAnswers = Object.values(interviewAnswersRef.current)
      const rawContent = resumePayload
        ? trimmed
        : allAnswers.length > 0
          ? `${trimmed}\n\n${buildInterviewPayload('update', allAnswers, { includeSummary: false })}`
          : trimmed

      const userMessage: Message = {
        id: createId(),
        role: 'user',
        content: trimmed,
        timestamp: new Date(),
      }
      const assistantMessage: Message = {
        id: createId(),
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isStreaming: true,
      }

      await enqueueConversation(userMessage, assistantMessage, rawContent, {
        triggerInterview: shouldTriggerInterview,
        generateNow,
        attachments: options?.attachments,
        imageIntent: options?.imageIntent,
        targetPages: options?.targetPages,
        mentionedFiles: options?.mentionedFiles,
        styleReference: options?.styleReference,
        resume: resumePayload,
      })
    },
    [
      enqueueConversation,
      interviewAnswersRef,
      interviewModeRef,
      resumePendingRef,
      setError,
    ]
  )

  const handleInterviewAction = React.useCallback(
    async (payload: InterviewActionPayload) => {
      if (!sessionId) return
      setError(null)

      const status =
        payload.action === 'generate'
          ? 'generated'
          : payload.action === 'skip'
            ? 'skipped'
            : 'submitted'

      updateInterviewByBatchId(payload.batchId, (batch) => ({
        ...batch,
        status,
        answers: payload.answers,
      }))

      if (payload.answers.length > 0) {
        mergeInterviewAnswers(payload.answers)
        setInterviewSummaryByBatchId(payload.batchId, payload.answers)
      }
      clearInterviewBatch(sessionId)

      const allAnswers = Object.values(interviewAnswersRef.current)
      const rawContent = buildInterviewPayload(payload.action, allAnswers)

      const fallbackContent =
        payload.action === 'generate'
          ? 'Generate now'
          : payload.action === 'skip'
            ? 'Skip this batch'
            : 'Answers submitted'

      const userMessage: Message = {
        id: createId(),
        role: 'user',
        content: fallbackContent,
        hidden: true,
        timestamp: new Date(),
      }

      const assistantMessage: Message = {
        id: createId(),
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isStreaming: true,
      }

      await enqueueConversation(userMessage, assistantMessage, rawContent, {
        triggerInterview: true,
      })
    },
    [
      enqueueConversation,
      interviewAnswersRef,
      mergeInterviewAnswers,
      sessionId,
      setInterviewSummaryByBatchId,
      setError,
      updateInterviewByBatchId,
    ]
  )

  return {
    messages,
    isStreaming,
    connectionState,
    error,
    assets,
    addAsset,
    removeAsset,
    getAssetById,
    uploadAsset,
    sendMessage,
    handleInterviewAction,
    stopStream,
    clearThread,
  }
}
