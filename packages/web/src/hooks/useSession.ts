import * as React from 'react'
import { api } from '@/api/client'
import type {
  InterviewAnswer,
  InterviewBatch,
  InterviewSummary,
  Message,
  SessionDetail,
  Version,
} from '@/types'
import { loadInterviewBatch } from '@/lib/interviewStorage'
import {
  mergeInterviewAnswerList,
  normalizeInterviewAnswers,
  normalizeInterviewQuestions,
} from '@/lib/interviewUtils'
import {
  clearPendingMessage,
  fromStoredMessage,
  loadPendingMessage,
} from '@/lib/pendingMessageStorage'
import type { SessionEvent } from '@/types/events'

const PENDING_MESSAGE_TTL_MS = 10 * 60 * 1000
const INTERVIEW_EVENT_LIMIT = 400

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

const INTERVIEW_TAG_RE = /<INTERVIEW_ANSWERS>([\s\S]*?)<\/INTERVIEW_ANSWERS>/
const SUMMARY_PREFIX_RE = /^answer summary\s*:/i

const summarizeInterviewAction = (action?: string) => {
  switch (action) {
    case 'generate_now':
      return 'Generate now'
    case 'skip_batch':
      return 'Skip this batch'
    case 'update_answers':
      return 'Answers updated'
    case 'submit_batch':
      return 'Answers submitted'
    default:
      return 'Answers submitted'
  }
}

const safeParsePayload = (payloadText?: string | null) => {
  if (!payloadText) return null
  try {
    return JSON.parse(payloadText)
  } catch {
    const start = payloadText.indexOf('{')
    const end = payloadText.lastIndexOf('}')
    if (start >= 0 && end > start) {
      try {
        return JSON.parse(payloadText.slice(start, end + 1))
      } catch {
        return null
      }
    }
    return null
  }
}

const parseInterviewPayloadFromContent = (content?: string) => {
  if (!content) return null
  const match = INTERVIEW_TAG_RE.exec(content)
  if (!match) return null
  const payload = safeParsePayload(match[1]?.trim())
  if (!payload || typeof payload !== 'object') return null
  const action = typeof (payload as { action?: unknown }).action === 'string'
    ? String((payload as { action?: unknown }).action)
    : undefined
  const answers = normalizeInterviewAnswers((payload as { answers?: unknown }).answers)
  return { action, answers }
}

const extractInterviewAction = (content?: string) => {
  if (!content) return null
  const match = INTERVIEW_TAG_RE.exec(content)
  if (!match) return null
  const payload = safeParsePayload(match[1]?.trim())
  return typeof payload?.action === 'string' ? payload.action : null
}

const parseInterviewFromContent = (content: string): {
  cleanContent: string
  interviewSummary?: InterviewSummary
  interviewAction?: string
  isInterviewOnly?: boolean
} => {
  if (!content) return { cleanContent: content }
  const match = INTERVIEW_TAG_RE.exec(content)
  if (!match) return { cleanContent: content }

  const before = content.slice(0, match.index).trim()
  const afterRaw = content.slice(match.index + match[0].length).trim()
  const after = SUMMARY_PREFIX_RE.test(afterRaw) ? '' : afterRaw

  const payload = safeParsePayload(match[1]?.trim())
  const action = typeof payload?.action === 'string' ? payload.action : undefined
  const answers = Array.isArray(payload?.answers) ? payload.answers : []
  const showSummary = action !== 'update_answers'
  const interviewSummary =
    showSummary && answers.length ? ({ items: answers } as InterviewSummary) : undefined

  const combined = [before, after].filter(Boolean).join('\n\n').trim()
  const cleanContent = combined || summarizeInterviewAction(action)
  const isInterviewOnly = !before && !after
  return { cleanContent, interviewSummary, interviewAction: action, isInterviewOnly }
}

const buildInterviewPayloadMap = (
  rawMessages: ApiMessage[],
  mappedMessages: Message[]
) => {
  const map = new Map<string, { action?: string; answers: InterviewAnswer[] }>()
  rawMessages.forEach((raw, index) => {
    const payload = parseInterviewPayloadFromContent(raw.content ?? raw.message)
    if (!payload) return
    const mapped = mappedMessages[index]
    if (!mapped) return
    map.set(mapped.id, payload)
  })
  return map
}

const reconcileInterviewSummaries = (
  messages: Message[],
  payloadsById: Map<string, { action?: string; answers: InterviewAnswer[] }>
) => {
  if (payloadsById.size === 0) return messages
  let next = messages

  for (let index = 0; index < messages.length; index += 1) {
    const message = messages[index]
    if (message.role !== 'user') continue
    const payload = payloadsById.get(message.id)
    if (!payload) continue
    if (!payload.action || payload.action === 'update_answers') continue
    if (payload.answers.length === 0) continue

    const answerIds = new Set(payload.answers.map((answer) => answer.id))
    let targetIndex = -1
    let fallbackIndex = -1

    for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
      const candidate = next[cursor]
      if (candidate.role !== 'assistant') continue
      if (fallbackIndex < 0) fallbackIndex = cursor
      const questions = candidate.interview?.questions
      if (!questions || questions.length === 0) continue
      const overlap = questions.reduce(
        (count, question) => count + (answerIds.has(question.id) ? 1 : 0),
        0
      )
      if (overlap > 0) {
        targetIndex = cursor
        break
      }
    }

    if (targetIndex < 0) targetIndex = fallbackIndex
    if (targetIndex < 0) continue

    if (next === messages) next = [...messages]
    const target = next[targetIndex]
    const status = mapInterviewActionToStatus(payload.action)
    const mergedAnswers = target.interview
      ? mergeInterviewAnswerList(target.interview.answers, payload.answers)
      : undefined

    next[targetIndex] = {
      ...target,
      interview: target.interview
        ? {
            ...target.interview,
            answers: mergedAnswers ?? target.interview.answers,
            status: status ?? target.interview.status,
          }
        : target.interview,
      interviewSummary: { items: payload.answers },
    }
  }

  return next
}

const applyStoredInterview = (
  sessionId: string | undefined,
  rawMessages: ApiMessage[],
  mappedMessages: Message[]
) => {
  if (!sessionId) return mappedMessages
  const stored = loadInterviewBatch(sessionId)
  if (!stored) return mappedMessages
  if (mappedMessages.some((message) => message.interview?.id === stored.id)) {
    return mappedMessages
  }

  const promptText = stored.prompt?.trim()
  if (!promptText) return mappedMessages

  let promptIndex = -1
  for (let index = mappedMessages.length - 1; index >= 0; index -= 1) {
    const message = mappedMessages[index]
    if (message.role !== 'assistant') continue
    if (message.content.trim() !== promptText) continue
    promptIndex = index
    break
  }
  if (promptIndex < 0) return mappedMessages

  const hasSubmitAfter = rawMessages.slice(promptIndex + 1).some((raw) => {
    const action = extractInterviewAction(raw.content ?? raw.message)
    return Boolean(action && action !== 'update_answers')
  })
  if (hasSubmitAfter) return mappedMessages

  const next = [...mappedMessages]
  next[promptIndex] = {
    ...next[promptIndex],
    interview: stored,
  }
  return next
}

const applyPendingMessage = (
  sessionId: string | undefined,
  messages: Message[]
) => {
  if (!sessionId) return messages
  const pending = loadPendingMessage(sessionId)
  if (!pending?.assistant) return messages
  const restored = fromStoredMessage(pending.assistant)
  if (messages.some((message) => message.id === restored.id)) {
    return messages
  }
  if (
    restored.interview?.id &&
    messages.some((message) => message.interview?.id === restored.interview?.id)
  ) {
    clearPendingMessage(sessionId)
    return messages
  }
  const savedAt = pending.savedAt ? new Date(pending.savedAt) : null
  if (savedAt && Date.now() - savedAt.getTime() > PENDING_MESSAGE_TTL_MS) {
    clearPendingMessage(sessionId)
    return messages
  }
  if (
    savedAt &&
    messages.some(
      (message) =>
        message.role === 'assistant' &&
        message.timestamp &&
        message.timestamp >= savedAt
    )
  ) {
    clearPendingMessage(sessionId)
    return messages
  }
  return [
    ...messages,
    {
      ...restored,
      isStreaming: restored.isStreaming ?? true,
    },
  ]
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value && typeof value === 'object')

const getString = (value: unknown) =>
  typeof value === 'string' ? value : undefined

const mapInterviewActionToStatus = (
  action?: string
): InterviewBatch['status'] | undefined => {
  switch (action) {
    case 'generate_now':
      return 'generated'
    case 'skip_batch':
      return 'skipped'
    case 'submit_batch':
      return 'submitted'
    case 'update_answers':
      return 'active'
    default:
      return undefined
  }
}

const buildInterviewBatchesFromEvents = (events: SessionEvent[]): InterviewBatch[] => {
  const sorted = [...events].sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0))
  const batches: InterviewBatch[] = []
  const byId = new Map<string, InterviewBatch>()
  let totalCount = 0
  let latestBatchId: string | null = null

  for (const event of sorted) {
    if (event.type !== 'interview_question' && event.type !== 'interview_answer') {
      continue
    }
    const payload = isRecord(event.payload) ? event.payload : {}

    if (event.type === 'interview_question') {
      const questions = normalizeInterviewQuestions(payload.questions)
      if (questions.length === 0) continue
      const batchId = String(
        payload.batch_id ?? payload.batchId ?? payload.id ?? `batch-${event.seq ?? batches.length + 1}`
      )
      const prompt = getString(payload.message ?? payload.prompt)
      const startIndex = totalCount + 1
      totalCount += questions.length
      const batch: InterviewBatch = {
        id: batchId,
        prompt,
        questions,
        startIndex,
        totalCount,
        status: 'active',
      }
      batches.push(batch)
      byId.set(batchId, batch)
      latestBatchId = batchId
      continue
    }

    if (event.type === 'interview_answer') {
      const answers = normalizeInterviewAnswers(
        payload.answers ?? payload.answer ?? payload.responses ?? payload.response
      )
      const batchIdRaw = payload.batch_id ?? payload.batchId ?? payload.id ?? latestBatchId
      if (!batchIdRaw) continue
      const batchId = String(batchIdRaw)
      const batch = byId.get(batchId)
      if (!batch) continue

      if (answers.length > 0) {
        const questionIndex = new Map(
          batch.questions.map((question, index) => [
            question.id,
            batch.startIndex + index,
          ])
        )
        const enriched = answers.map((answer, index) => ({
          ...answer,
          question:
            batch.questions.find((q) => q.id === answer.id)?.title ?? answer.question,
          index:
            typeof answer.index === 'number'
              ? answer.index
              : questionIndex.get(answer.id) ?? batch.startIndex + index,
        }))
        batch.answers = mergeInterviewAnswerList(batch.answers, enriched)
      }

      const action = getString(payload.action)
      const status = mapInterviewActionToStatus(action)
      if (status && status !== 'active') {
        batch.status = status
        latestBatchId = null
      } else if (status) {
        batch.status = status
      }
    }
  }

  const lastActiveIndex = [...batches].reverse().findIndex((batch) => batch.status === 'active')
  if (lastActiveIndex > 0) {
    const cutoff = batches.length - 1 - lastActiveIndex
    for (let index = 0; index < cutoff; index += 1) {
      if (batches[index].status === 'active') {
        batches[index].status = 'submitted'
      }
    }
  }

  return batches
}

const extractMessagesList = (messagesResponse: unknown): ApiMessage[] =>
  Array.isArray(messagesResponse)
    ? (messagesResponse as ApiMessage[])
    : (messagesResponse as { messages?: ApiMessage[] })?.messages ?? []

const buildBaseMessages = (
  sessionId: string | undefined,
  rawMessages: ApiMessage[]
) => {
  const mappedMessages = rawMessages.map(mapMessage)
  const payloadMap = buildInterviewPayloadMap(rawMessages, mappedMessages)
  let nextMessages = applyStoredInterview(sessionId, rawMessages, mappedMessages)
  nextMessages = reconcileInterviewSummaries(nextMessages, payloadMap)
  nextMessages = applyPendingMessage(sessionId, nextMessages)
  return { messages: nextMessages, payloadMap }
}

const applyInterviewEvents = (
  sessionId: string | undefined,
  messages: Message[],
  payloadMap: Map<string, { action?: string; answers: InterviewAnswer[] }>,
  events: SessionEvent[]
) => {
  const interviewBatches = buildInterviewBatchesFromEvents(events)
  if (interviewBatches.length === 0) return messages
  let nextMessages = attachInterviewBatches(messages, interviewBatches)
  nextMessages = reconcileInterviewSummaries(nextMessages, payloadMap)
  nextMessages = applyPendingMessage(sessionId, nextMessages)
  return nextMessages
}

const attachInterviewBatches = (
  messages: Message[],
  batches: InterviewBatch[]
) => {
  if (batches.length === 0) return messages
  const next = [...messages]
  const usedIndexes = new Set<number>()

  for (const batch of batches) {
    const prompt = batch.prompt?.trim()
    let targetIndex = -1

    if (prompt) {
      for (let index = next.length - 1; index >= 0; index -= 1) {
        const message = next[index]
        if (usedIndexes.has(index)) continue
        if (message.role !== 'assistant') continue
        if (message.content.trim() !== prompt) continue
        targetIndex = index
        break
      }
    }

    if (targetIndex < 0) {
      for (let index = next.length - 1; index >= 0; index -= 1) {
        const message = next[index]
        if (usedIndexes.has(index)) continue
        if (message.role !== 'assistant') continue
        if (message.interview) continue
        targetIndex = index
        break
      }
    }

    if (targetIndex < 0) {
      next.push({
        id: `interview-${batch.id}`,
        role: 'assistant',
        content: batch.prompt ?? '',
        timestamp: new Date(),
        interview: batch,
        interviewSummary: batch.answers?.length
          ? { items: batch.answers }
          : undefined,
      })
      continue
    }

    const current = next[targetIndex]
    if (current.interview) continue
    next[targetIndex] = {
      ...current,
      interview: batch,
      interviewSummary:
        current.interviewSummary ??
        (batch.answers?.length ? { items: batch.answers } : undefined),
    }
    usedIndexes.add(targetIndex)
  }

  return next
}

const mapMessage = (message: ApiMessage, index: number): Message => {
  const rawContent = message.content ?? message.message ?? ''
  const parsedInterview = parseInterviewFromContent(rawContent)
  return {
    id: message.id ?? `m-${index}-${Date.now()}`,
    role: message.role === 'user' ? 'user' : 'assistant',
    content: parsedInterview.cleanContent,
    timestamp: toDate(message.created_at ?? message.timestamp),
    interviewSummary: parsedInterview.interviewSummary,
    hidden:
      message.role === 'user' &&
      parsedInterview.isInterviewOnly &&
      parsedInterview.interviewAction !== 'update_answers',
  }
}

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
  const [messages, setMessagesState] = React.useState<Message[]>([])
  const [versions, setVersions] = React.useState<Version[]>([])
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const lastMessageUpdateRef = React.useRef(0)

  const setMessages = React.useCallback(
    (value: React.SetStateAction<Message[]>) => {
      lastMessageUpdateRef.current = Date.now()
      setMessagesState(value)
    },
    []
  )

  const refresh = React.useCallback(async () => {
    if (!sessionId) return
    const loadStartedAt = Date.now()
    setIsLoading(true)
    setError(null)
    try {
      const [sessionResponse, messagesResponse, versionsResponse] =
        await Promise.all([
          api.sessions.get(sessionId),
          api.sessions.messages(sessionId),
          api.sessions.versions(sessionId, { includePreviewHtml: false }),
        ])

      if (sessionResponse) {
        setSession(mapSession(sessionResponse as ApiSession))
      }

      const messagesList = extractMessagesList(messagesResponse)
      const { messages: baseMessages, payloadMap } = buildBaseMessages(
        sessionId,
        messagesList
      )
      if (lastMessageUpdateRef.current <= loadStartedAt) {
        setMessagesState(baseMessages)
        lastMessageUpdateRef.current = Date.now()
      }

      const versionsPayload = versionsResponse as {
        versions?: ApiVersion[]
        current_version?: number
      }
      const currentVersion = versionsPayload?.current_version
      const versionList = Array.isArray(versionsResponse)
        ? versionsResponse
        : versionsPayload?.versions ?? []
      setVersions(versionList.map((item) => mapVersion(item, currentVersion)))

      if (messagesList.length > 0) {
        void (async () => {
          try {
            const eventsResponse = await api.events.getSessionEvents(
              sessionId,
              undefined,
              INTERVIEW_EVENT_LIMIT
            )
            const events = (eventsResponse as { events?: SessionEvent[] })?.events ?? []
            if (events.length === 0) return
            setMessages((prev) =>
              applyInterviewEvents(sessionId, prev, payloadMap, events)
            )
          } catch {
            // Ignore event recovery failures, keep base messages.
          }
        })()
      }
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load session'
      setError(message)
      return false
    } finally {
      setIsLoading(false)
    }
  }, [sessionId, setMessages])

  React.useEffect(() => {
    let active = true
    if (!sessionId) return
    const load = async () => {
      const loadStartedAt = Date.now()
      setIsLoading(true)
      try {
        const [sessionResponse, messagesResponse, versionsResponse] =
          await Promise.all([
            api.sessions.get(sessionId),
            api.sessions.messages(sessionId),
            api.sessions.versions(sessionId, { includePreviewHtml: false }),
          ])
        if (!active) return

        if (sessionResponse) {
          setSession(mapSession(sessionResponse as ApiSession))
        }

        const messagesList = extractMessagesList(messagesResponse)
        const { messages: baseMessages, payloadMap } = buildBaseMessages(
          sessionId,
          messagesList
        )
        if (lastMessageUpdateRef.current <= loadStartedAt) {
          setMessagesState(baseMessages)
          lastMessageUpdateRef.current = Date.now()
        }

        const versionsPayload = versionsResponse as {
          versions?: ApiVersion[]
          current_version?: number
        }
        const currentVersion = versionsPayload?.current_version
        const versionList = Array.isArray(versionsResponse)
          ? versionsResponse
          : versionsPayload?.versions ?? []
        setVersions(versionList.map((item) => mapVersion(item, currentVersion)))

        if (messagesList.length > 0) {
          void (async () => {
            try {
              const eventsResponse = await api.events.getSessionEvents(
                sessionId,
                undefined,
                INTERVIEW_EVENT_LIMIT
              )
              if (!active) return
              const events = (eventsResponse as { events?: SessionEvent[] })?.events ?? []
              if (events.length === 0) return
              setMessages((prev) =>
                applyInterviewEvents(sessionId, prev, payloadMap, events)
              )
            } catch {
              // Ignore event recovery failures, keep base messages.
            }
          })()
        }
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
  }, [sessionId, setMessages])

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
