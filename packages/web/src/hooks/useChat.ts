import * as React from 'react'
import { api, API_BASE } from '@/api/client'
import { uploadAsset as uploadAssetApi } from '@/api/assets'
import { toast } from '@/hooks/use-toast'
import { saveInterviewBatch, clearInterviewBatch } from '@/lib/interviewStorage'
import { loadChatAssets, saveChatAssets } from '@/lib/assetStorage'
import {
  clearPendingMessage,
  savePendingMessage,
  toStoredMessage,
} from '@/lib/pendingMessageStorage'
import { normalizeInterviewQuestions } from '@/lib/interviewUtils'
import type {
  ChatResponse,
  ChatStep,
  ChatAttachment,
  ChatRequestPayload,
  ChatStyleReference,
  InterviewActionPayload,
  InterviewAnswer,
  InterviewBatch,
  InterviewQuestion,
  Message,
  ChatAction,
  ChatAsset,
  AssetType,
} from '@/types'
import type { ExecutionEvent, ToolCallEvent, ToolResultEvent } from '@/types/events'

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

const TOOL_SUMMARY_KEYS = [
  'path',
  'paths',
  'filename',
  'file',
  'url',
  'query',
  'pattern',
  'command',
  'expression',
  'name',
  'id',
  'preview_path',
  'version_path',
  'written_bytes',
  'version',
]

const SENSITIVE_KEYS = new Set([
  'content',
  'html',
  'data',
  'prompt',
  'message',
  'text',
  'code',
])

const truncateText = (value: string, max = 96) => {
  if (value.length <= max) return value
  return `${value.slice(0, max)}...`
}

const summarizeValue = (value: unknown): string | null => {
  if (typeof value === 'string') return truncateText(value, 80)
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) {
    const items = value
      .slice(0, 2)
      .map((item) => summarizeValue(item))
      .filter((item): item is string => Boolean(item))
    return items.length ? `[${items.join(', ')}]` : null
  }
  return null
}

const summarizeRecord = (input?: Record<string, unknown>) => {
  if (!input) return null
  const entries: string[] = []

  for (const key of TOOL_SUMMARY_KEYS) {
    if (!(key in input)) continue
    if (SENSITIVE_KEYS.has(key.toLowerCase())) continue
    const value = summarizeValue(input[key])
    if (!value) continue
    entries.push(`${key}=${value}`)
    if (entries.length >= 2) break
  }

  if (entries.length === 0) {
    for (const [key, value] of Object.entries(input)) {
      if (SENSITIVE_KEYS.has(key.toLowerCase())) continue
      const summary = summarizeValue(value)
      if (!summary) continue
      entries.push(`${key}=${summary}`)
      if (entries.length >= 2) break
    }
  }

  if (entries.length === 0 && typeof input.output === 'object' && input.output) {
    return summarizeRecord(input.output as Record<string, unknown>)
  }

  return entries.length ? entries.join(', ') : null
}

const buildAgentLabel = (event: ExecutionEvent) => {
  if (event.type === 'agent_start') {
    return `${event.agent_type} agent started`
  }
  if (event.type === 'agent_progress') {
    const progress = event.progress !== undefined ? ` (${event.progress}%)` : ''
    const message = event.message ? `: ${truncateText(event.message, 80)}` : ''
    return `${event.agent_id}${progress}${message}`
  }
  if (event.type === 'agent_end') {
    return `${event.agent_id} ${event.status === 'success' ? 'completed' : 'failed'}`
  }
  return event.type
}

const buildToolLabel = (event: ToolCallEvent | ToolResultEvent) => {
  const summarySource =
    event.type === 'tool_call' ? event.tool_input : event.tool_output
  const summary = summarizeRecord(summarySource)
  const base = summary ? `${event.tool_name} (${summary})` : event.tool_name
  if (event.type === 'tool_call') {
    return `Calling ${base}`
  }
  if (!event.success && event.error) {
    return `Result ${base} - ${truncateText(event.error, 80)}`
  }
  return `Result ${base}`
}

const isEventPayload = (payload: unknown): payload is ExecutionEvent =>
  Boolean(payload && typeof payload === 'object' && 'type' in payload)

type InterviewPayloadLike = {
  phase?: string
  questions?: InterviewQuestion[]
  message?: string
  batch_id?: string
  batchId?: string
}

const isInterviewPayload = (payload: unknown): payload is InterviewPayloadLike =>
  Boolean(payload && typeof payload === 'object' && 'questions' in payload)


const formatInterviewSummaryText = (answers: InterviewAnswer[]) => {
  const items = answers.map((item) => {
    const label = item.labels?.join(', ') ?? item.label ?? String(item.value)
    return `${item.question}=${label}`
  })
  return items.length ? `Answer summary: ${items.join('; ')}` : 'Answer summary:'
}

const buildInterviewPayload = (
  action: InterviewActionPayload['action'] | 'update',
  answers: InterviewAnswer[],
  options?: { includeSummary?: boolean }
) => {
  const payload = {
    action:
      action === 'generate'
        ? 'generate_now'
        : action === 'skip'
          ? 'skip_batch'
          : action === 'update'
            ? 'update_answers'
            : 'submit_batch',
    answers,
  }
  const includeSummary = options?.includeSummary ?? action !== 'update'
  const summary = includeSummary ? `\n${formatInterviewSummaryText(answers)}` : ''
  return `<INTERVIEW_ANSWERS>\n${JSON.stringify(payload)}\n</INTERVIEW_ANSWERS>${summary}`
}

const PRODUCT_DOC_ACTIONS = new Set([
  'product_doc_generated',
  'product_doc_updated',
  'product_doc_confirmed',
  'product_doc_outdated',
])

const ASSET_TYPE_LABELS: Record<AssetType, string> = {
  logo: 'Logo',
  style_ref: 'Style reference',
  background: 'Background',
  product_image: 'Product image',
}

export interface UseChatOptions {
  sessionId?: string
  initialMessages?: Message[]
  messages?: Message[]
  setMessages?: React.Dispatch<React.SetStateAction<Message[]>>
  onPreview?: (payload: { html?: string; previewUrl?: string | null }) => void
  onTabChange?: (tab: 'preview' | 'code' | 'product-doc' | 'data') => void
  onPageSelect?: (slug: string) => void
  onSessionCreated?: (sessionId: string) => void
}

export interface SendMessageOptions {
  triggerInterview?: boolean
  generateNow?: boolean
  attachments?: ChatAttachment[]
  targetPages?: string[]
  styleReference?: ChatStyleReference
  resume?: Record<string, unknown>
}

export function useChat({
  sessionId,
  initialMessages = [],
  messages: controlledMessages,
  setMessages: setControlledMessages,
  onPreview,
  onTabChange,
  onPageSelect,
  onSessionCreated,
}: UseChatOptions) {
  const [localMessages, setLocalMessages] = React.useState<Message[]>(initialMessages)
  const [isStreaming, setIsStreaming] = React.useState(false)
  const [connectionState, setConnectionState] = React.useState<ConnectionState>('idle')
  const [error, setError] = React.useState<string | null>(null)
  const [assets, setAssets] = React.useState<ChatAsset[]>(() =>
    loadChatAssets(sessionId)
  )
  const eventSourceRef = React.useRef<EventSource | null>(null)
  const fetchAbortRef = React.useRef<AbortController | null>(null)
  const streamMessageIdRef = React.useRef<string | null>(null)
  const pendingMessageRef = React.useRef<string | null>(null)
  const pendingOptionsRef = React.useRef<SendMessageOptions | null>(null)
  const receivedEventRef = React.useRef(false)
  const receivedDeltaRef = React.useRef(false)
  const interviewTotalRef = React.useRef(0)
  const interviewAnswersRef = React.useRef<Record<string, InterviewAnswer>>({})
  const interviewModeRef = React.useRef(false)
  const resumePendingRef = React.useRef(false)
  const sessionIdRef = React.useRef(sessionId)
  const createdSessionIdRef = React.useRef<string | null>(null)
  const assetsRef = React.useRef<ChatAsset[]>(assets)

  const messages = controlledMessages ?? localMessages
  const setMessages = setControlledMessages ?? setLocalMessages

  const persistPendingMessage = React.useCallback(
    (message: Message) => {
      const currentSessionId = sessionIdRef.current
      if (!currentSessionId) return
      savePendingMessage(currentSessionId, {
        assistant: toStoredMessage(message),
        savedAt: new Date().toISOString(),
      })
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
    if (!sessionId) {
      setAssets([])
      return
    }
    setAssets(loadChatAssets(sessionId))
  }, [sessionId])

  React.useEffect(() => {
    assetsRef.current = assets
    const activeSessionId = sessionIdRef.current
    if (!activeSessionId) return
    saveChatAssets(activeSessionId, assets)
  }, [assets])

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

  const requireSessionId = React.useCallback(() => {
    const currentSessionId = sessionIdRef.current
    if (!currentSessionId) {
      throw new Error(
        'Start a chat to create a session before uploading assets.'
      )
    }
    return currentSessionId
  }, [])

  const addAsset = React.useCallback((asset: ChatAsset) => {
    setAssets((prev) => {
      const index = prev.findIndex((item) => item.id === asset.id)
      if (index >= 0) {
        const next = [...prev]
        next[index] = { ...next[index], ...asset }
        return next
      }
      return [...prev, asset]
    })
  }, [])

  const removeAsset = React.useCallback((assetId: string) => {
    setAssets((prev) => prev.filter((asset) => asset.id !== assetId))
  }, [])

  const getAssetById = React.useCallback((assetId: string) => {
    return assetsRef.current.find((asset) => asset.id === assetId) ?? null
  }, [])

  const appendAssetMessage = React.useCallback(
    (asset: ChatAsset) => {
      setMessages((prev) => {
        const alreadyAdded = prev.some(
          (message) =>
            message.assets?.some((item) => item.id === asset.id) ||
            message.content.includes(asset.id)
        )
        if (alreadyAdded) return prev
        const label = ASSET_TYPE_LABELS[asset.assetType] ?? asset.assetType
        return [
          ...prev,
          {
            id: createId(),
            role: 'user',
            content: `Uploaded ${label}`,
            timestamp: new Date(),
            assets: [asset],
          },
        ]
      })
    },
    [setMessages]
  )

  React.useEffect(() => {
    interviewTotalRef.current = 0
    interviewAnswersRef.current = {}
    interviewModeRef.current = false
  }, [sessionId])

  const updateMessageById = React.useCallback(
    (id: string, updater: (message: Message) => Message) => {
      setMessages((prev) =>
        prev.map((message) => (message.id === id ? updater(message) : message))
      )
    },
    [setMessages]
  )

  const updateInterviewByBatchId = React.useCallback(
    (batchId: string, updater: (batch: InterviewBatch) => InterviewBatch) => {
      setMessages((prev) =>
        prev.map((message) => {
          if (!message.interview || message.interview.id !== batchId) return message
          return { ...message, interview: updater(message.interview) }
        })
      )
    },
    [setMessages]
  )

  const setInterviewSummaryByBatchId = React.useCallback(
    (batchId: string, summary: InterviewAnswer[]) => {
      setMessages((prev) =>
        prev.map((message) => {
          if (!message.interview || message.interview.id !== batchId) return message
          return { ...message, interviewSummary: { items: summary } }
        })
      )
    },
    [setMessages]
  )

  const mergeInterviewAnswers = React.useCallback((answers: InterviewAnswer[]) => {
    answers.forEach((answer) => {
      interviewAnswersRef.current[answer.id] = answer
    })
  }, [])

  React.useEffect(() => {
    if (!sessionId) return
    if (messages.length === 0) return
    let totalCount = 0
    let hasActive = false
    const collected: InterviewAnswer[] = []

    for (const message of messages) {
      if (message.interview) {
        totalCount = Math.max(totalCount, message.interview.totalCount)
        if (message.interview.status === 'active') {
          hasActive = true
        }
        if (message.interview.answers && message.interview.answers.length > 0) {
          collected.push(...message.interview.answers)
        }
      }
      if (message.interviewSummary?.items?.length) {
        collected.push(...message.interviewSummary.items)
      }
    }

    if (collected.length > 0) {
      mergeInterviewAnswers(collected)
    }
    if (totalCount > 0) {
      interviewTotalRef.current = totalCount
    }
    interviewModeRef.current = hasActive
  }, [mergeInterviewAnswers, messages, sessionId])

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
  }, [isStreaming, messages, persistPendingMessage, sessionId])

  const resetInterviewState = React.useCallback(() => {
    interviewTotalRef.current = 0
    interviewAnswersRef.current = {}
    interviewModeRef.current = false
    clearInterviewBatch(sessionId)
    clearPendingMessage(sessionId)
  }, [sessionId])

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
    [updateMessageById]
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
    pendingOptionsRef.current = null
    receivedEventRef.current = false
    receivedDeltaRef.current = false
    setIsStreaming(false)
    setConnectionState('closed')
    if (sessionIdRef.current) {
      clearPendingMessage(sessionIdRef.current)
    }
  }, [updateMessageById])

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
  }, [finishStream])

  const clearThread = React.useCallback(async () => {
    stopStream()
    setError(null)

    if (!sessionId) {
      setMessages([])
      resetInterviewState()
      return
    }

    try {
      await api.sessions.clearMessages(sessionId)
      setMessages([])
      resetInterviewState()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to clear messages'
      setError(message)
      toast({ title: 'Clear failed', description: message })
      throw err
    }
  }, [resetInterviewState, sessionId, setMessages, stopStream])

  const uploadAsset = React.useCallback(
    async (
      file: File,
      assetType: AssetType,
      options?: { onProgress?: (progress: number) => void }
    ) => {
      const activeSessionId = requireSessionId()
      const assetRef = await uploadAssetApi(activeSessionId, file, assetType, {
        onProgress: options?.onProgress,
      })
      const chatAsset: ChatAsset = {
        ...assetRef,
        assetType,
        name: file.name,
        size: file.size,
        createdAt: new Date().toISOString(),
      }
      addAsset(chatAsset)
      appendAssetMessage(chatAsset)
    },
    [addAsset, appendAssetMessage, requireSessionId]
  )

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
          // No tab switch needed
          break
      }
    },
    [onTabChange, onPageSelect]
  )

  const dispatchProductDocEvent = React.useCallback((payload: {
    type: string
    doc_id?: string
    change_summary?: string
  }) => {
    if (typeof window === 'undefined') return
    if (!payload.type || !PRODUCT_DOC_ACTIONS.has(payload.type)) return
    window.dispatchEvent(new CustomEvent('product-doc-event', { detail: payload }))
  }, [])

  const fallbackSend = React.useCallback(
    async (content: string, options?: SendMessageOptions) => {
      if (!content.trim()) return
      const currentSessionId = sessionIdRef.current
      try {
        const payload: ChatRequestPayload = {
          session_id: currentSessionId,
          message: content.trim(),
          interview: options?.triggerInterview,
          generate_now: options?.generateNow,
        }
        if (options?.attachments?.length) {
          payload.images = options.attachments
            .map((attachment) => attachment.data)
            .filter(Boolean)
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
        const response = (await api.chat.send(payload)) as ChatResponse
        if (response?.session_id) {
          maybeNotifySessionCreated(response.session_id)
        }
        const messageId = streamMessageIdRef.current
        if (response?.message && messageId) {
          updateMessageById(messageId, (message) => ({
            ...message,
            content: response.message ?? message.content,
            action: response.action ?? undefined,
            affectedPages: response.affected_pages ?? undefined,
            activePageSlug: response.active_page_slug ?? undefined,
          }))
        }
        if (response?.preview_html || response?.preview_url) {
          onPreview?.({
            html: response.preview_html ?? undefined,
            previewUrl: response.preview_url ?? undefined,
          })
        }

        if (response.action && PRODUCT_DOC_ACTIONS.has(response.action)) {
          dispatchProductDocEvent({ type: response.action })
        } else if (response.product_doc_updated) {
          dispatchProductDocEvent({ type: 'product_doc_updated' })
        }

        // Handle action-based tab switching
        if (response.action) {
          handleActionTabSwitch(response.action, response.active_page_slug)
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
    [
      dispatchProductDocEvent,
      finishStream,
      handleActionTabSwitch,
      maybeNotifySessionCreated,
      onPreview,
      updateMessageById,
    ]
  )

  const applyInterviewQuestions = React.useCallback(
    (payload: InterviewPayloadLike) => {
      if (!Array.isArray(payload.questions)) return false
      const normalizedQuestions = normalizeInterviewQuestions(payload.questions)
      if (normalizedQuestions.length === 0) return false
      receivedEventRef.current = true
      const messageId = streamMessageIdRef.current
      if (!messageId) return false

      const payloadBatchId = payload.batch_id ?? payload.batchId
      const prompt = typeof payload.message === 'string' ? payload.message : undefined
      let interviewBatch: InterviewBatch | null = null

      updateMessageById(messageId, (message) => {
        if (message.interview) {
          if (
            payloadBatchId &&
            message.interview.id !== String(payloadBatchId)
          ) {
            const updated: InterviewBatch = {
              ...message.interview,
              id: String(payloadBatchId),
              prompt: prompt ?? message.interview.prompt,
              questions: normalizedQuestions.length
                ? normalizedQuestions
                : message.interview.questions,
            }
            interviewBatch = updated
            return { ...message, interview: updated }
          }
          return message
        }

        const startIndex = interviewTotalRef.current + 1
        const totalCount = interviewTotalRef.current + normalizedQuestions.length
        interviewTotalRef.current = totalCount
        const batchId = String(payloadBatchId ?? createId())
        interviewBatch = {
          id: batchId,
          prompt,
          questions: normalizedQuestions,
          startIndex,
          totalCount,
          status: 'active',
        }
        return {
          ...message,
          content: '',
          interview: interviewBatch,
        }
      })

      if (!interviewBatch) return false
      interviewModeRef.current = true
      if (sessionId) {
        saveInterviewBatch(sessionId, interviewBatch)
      }
      return true
    },
    [sessionId, updateMessageById]
  )

  const handleStreamData = React.useCallback(
    (data: string) => {
      if (data === '[DONE]') {
        stopStream()
        return
      }

      const payload = safeJsonParse(data)
      if (!payload || typeof payload !== 'object') return
      if ('session_id' in payload) {
        maybeNotifySessionCreated((payload as { session_id?: unknown }).session_id)
      }
      if (isEventPayload(payload)) {
        receivedEventRef.current = true
        if (payload.type === 'interview_question') {
          applyInterviewQuestions(payload as InterviewPayloadLike)
          return
        }
        if (payload.type === 'refine_waiting' || payload.type === 'interrupt') {
          resumePendingRef.current = true
          interviewModeRef.current = false
        }
        if (payload.type.startsWith('agent_')) {
          const label = buildAgentLabel(payload)
          const step: ChatStep = {
            id: createId(),
            label,
            status:
              payload.type === 'agent_end'
                ? payload.status === 'success'
                  ? 'done'
                  : 'failed'
                : 'in_progress',
            kind: 'agent',
            key: payload.type === 'agent_progress' ? `agent:${payload.agent_id}` : undefined,
          }
          if (payload.type === 'agent_progress') {
            appendStep(step, { updateKey: `agent:${payload.agent_id}` })
          } else if (payload.type === 'agent_start') {
            appendStep(
              { ...step, key: `agent:${payload.agent_id}` },
              { updateKey: `agent:${payload.agent_id}` }
            )
          } else {
            appendStep(step)
          }
        }
        if (payload.type.startsWith('tool_')) {
          const toolEvent = payload as ToolCallEvent | ToolResultEvent
          const step: ChatStep = {
            id: createId(),
            label: buildToolLabel(toolEvent),
            status:
              toolEvent.type === 'tool_call'
                ? 'in_progress'
                : toolEvent.success
                  ? 'done'
                  : 'failed',
            kind: 'tool',
          }
          appendStep(step)
        }
        // Handle ProductDoc events - dispatch as custom events
        if (
          payload.type === 'product_doc_generated' ||
          payload.type === 'product_doc_updated' ||
          payload.type === 'product_doc_confirmed' ||
          payload.type === 'product_doc_outdated'
        ) {
          window.dispatchEvent(
            new CustomEvent('product-doc-event', { detail: payload })
          )
        }
        // Handle Page events - dispatch as custom events
        if (
          payload.type === 'page_created' ||
          payload.type === 'page_version_created' ||
          payload.type === 'page_preview_ready'
        ) {
          window.dispatchEvent(
            new CustomEvent('page-event', { detail: payload })
          )
        }
        if (payload.type === 'aesthetic_score') {
          window.dispatchEvent(
            new CustomEvent('aesthetic-score-event', { detail: payload })
          )
        }
        if (
          payload.type === 'build_start' ||
          payload.type === 'build_progress' ||
          payload.type === 'build_complete' ||
          payload.type === 'build_failed'
        ) {
          window.dispatchEvent(new CustomEvent('build-event', { detail: payload }))
        }
        // Handle MultiPage decision events
        if (payload.type === 'multipage_decision_made') {
          window.dispatchEvent(
            new CustomEvent('multipage-decision-event', { detail: payload })
          )
        }
        // Handle Sitemap events
        if (payload.type === 'sitemap_proposed') {
          window.dispatchEvent(
            new CustomEvent('sitemap-event', { detail: payload })
          )
        }
        return
      }
      if (isInterviewPayload(payload) && applyInterviewQuestions(payload)) {
        return
      }
      receivedEventRef.current = true

      if (typeof (payload as { phase?: string }).phase === 'string') {
        interviewModeRef.current = (payload as { phase?: string }).phase === 'interview'
      }

      const messageId = streamMessageIdRef.current
      const contentDelta =
        payload.delta ?? payload.token ?? payload.content ?? payload.message ?? payload.text
      const fullContent =
        payload.full_content ?? payload.fullContent ?? payload.output ?? payload.result
      const done =
        payload.done ||
        payload.type === 'done' ||
        payload.is_complete === true ||
        payload.isComplete === true

      // Parse new response fields
      const action = payload.action as ChatAction | undefined
      const activePageSlug = payload.active_page_slug ?? payload.activePageSlug as string | undefined
      const affectedPages = payload.affected_pages ?? payload.affectedPages as string[] | undefined
      const productDocUpdated =
        typeof (payload as { product_doc_updated?: unknown }).product_doc_updated === 'boolean'
          ? (payload as { product_doc_updated?: boolean }).product_doc_updated
          : false

      if (action && PRODUCT_DOC_ACTIONS.has(action)) {
        dispatchProductDocEvent({ type: action })
      } else if (productDocUpdated) {
        dispatchProductDocEvent({ type: 'product_doc_updated' })
      }

      const hasDelta =
        typeof (payload as { delta?: unknown }).delta === 'string' ||
        typeof (payload as { token?: unknown }).token === 'string'

      if (typeof fullContent === 'string' && messageId) {
        receivedDeltaRef.current = false
        updateMessageById(messageId, (message) => ({
          ...message,
          content: fullContent,
          action,
          affectedPages,
          activePageSlug,
        }))
      } else if (typeof contentDelta === 'string' && messageId) {
        const fullMessage = (payload as { message?: unknown }).message
        if (typeof fullMessage === 'string' && receivedDeltaRef.current) {
          receivedDeltaRef.current = false
          updateMessageById(messageId, (message) => ({
            ...message,
            content: fullMessage,
            action,
            affectedPages,
            activePageSlug,
          }))
        } else {
          updateMessageById(messageId, (message) => ({
            ...message,
            content: `${message.content}${contentDelta}`,
            action,
            affectedPages,
            activePageSlug,
          }))
          if (hasDelta) {
            receivedDeltaRef.current = true
          }
        }
      }

      if (payload.preview_html || payload.previewHtml) {
        onPreview?.({ html: payload.preview_html ?? payload.previewHtml })
      }
      if (payload.preview_url || payload.previewUrl) {
        onPreview?.({ previewUrl: payload.preview_url ?? payload.previewUrl })
      }

      if (done) {
        // Handle action-based tab switching on stream complete
        if (action) {
          handleActionTabSwitch(action, activePageSlug)
        }
        stopStream()
      }
    },
    [
      appendStep,
      applyInterviewQuestions,
      dispatchProductDocEvent,
      handleActionTabSwitch,
      maybeNotifySessionCreated,
      onPreview,
      stopStream,
      updateMessageById,
    ]
  )

  const startStream = React.useCallback(
    (content: string, options?: SendMessageOptions) => {
      if (!content.trim()) return
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }

      const eventSource = new EventSource(
        api.chat.streamUrl(sessionIdRef.current, content, {
          interview: options?.triggerInterview,
          generateNow: options?.generateNow,
        })
      )
      eventSourceRef.current = eventSource
      setConnectionState('connecting')

      eventSource.onopen = () => {
        setConnectionState('open')
      }

      eventSource.onmessage = (event) => {
        handleStreamData(event.data)
      }

      eventSource.onerror = () => {
        setConnectionState('error')
        setError('Stream connection lost')
        eventSource.close()
        eventSourceRef.current = null
        if (!receivedEventRef.current && pendingMessageRef.current) {
          const pending = pendingMessageRef.current
          const pendingOptions = pendingOptionsRef.current ?? undefined
          pendingMessageRef.current = null
          pendingOptionsRef.current = null
          void fallbackSend(pending, pendingOptions)
          return
        }
        stopStream()
      }
    },
    [fallbackSend, handleStreamData, stopStream]
  )

  const startFetchStream = React.useCallback(
    async (content: string, options?: SendMessageOptions) => {
      if (!content.trim()) return
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      if (fetchAbortRef.current) {
        fetchAbortRef.current.abort()
      }
      const controller = new AbortController()
      fetchAbortRef.current = controller
      setConnectionState('connecting')

      const payload: ChatRequestPayload = {
        session_id: sessionIdRef.current,
        message: content.trim(),
        interview: options?.triggerInterview,
        generate_now: options?.generateNow,
      }
      if (options?.attachments?.length) {
        payload.images = options.attachments
          .map((attachment) => attachment.data)
          .filter(Boolean)
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

        setConnectionState('open')
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
              const data = line.replace(/^data:\\s?/, '')
              if (!data) continue
              handleStreamData(data)
            }
          }
        }

        if (buffer.trim()) {
          const lines = buffer.split('\n')
          for (const line of lines) {
            if (!line.startsWith('data:')) continue
            const data = line.replace(/^data:\\s?/, '')
            if (!data) continue
            handleStreamData(data)
          }
        }
        if (!controller.signal.aborted) {
          stopStream()
        }
      } catch {
        if (controller.signal.aborted) return
        setConnectionState('error')
        setError('Stream connection lost')
        if (!receivedEventRef.current && pendingMessageRef.current) {
          const pending = pendingMessageRef.current
          const pendingOptions = pendingOptionsRef.current ?? undefined
          pendingMessageRef.current = null
          pendingOptionsRef.current = null
          void fallbackSend(pending, pendingOptions)
          return
        }
        stopStream()
      } finally {
        if (fetchAbortRef.current === controller) {
          fetchAbortRef.current = null
        }
      }
    },
    [fallbackSend, handleStreamData, stopStream]
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
    [fallbackSend, isStreaming, setMessages, startFetchStream, startStream, stopStream]
  )

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
        targetPages: options?.targetPages,
        styleReference: options?.styleReference,
        resume: resumePayload,
      })
    },
    [enqueueConversation]
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
        content: payload.answers.length > 0 ? fallbackContent : fallbackContent,
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
      mergeInterviewAnswers,
      sessionId,
      setInterviewSummaryByBatchId,
      updateInterviewByBatchId,
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
  }, [])

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
