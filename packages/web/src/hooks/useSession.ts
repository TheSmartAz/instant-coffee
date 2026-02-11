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
} from '@/lib/interviewUtils'
import {
  clearPendingMessage,
  fromStoredMessage,
  loadPendingMessage,
} from '@/lib/pendingMessageStorage'
import {
  buildInterviewBatchesFromEvents,
  buildStepsFromEvents,
  mapInterviewActionToStatus,
  STEP_EVENT_TYPES,
} from '@/lib/eventProcessors'
import { getCaseArray, getCaseString, getCaseValue } from '@/lib/caseAccess'
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
  action?: string | null
  product_doc_updated?: boolean
  change_summary?: string | null
  changeSummary?: string | null
  section_name?: string | null
  sectionName?: string | null
  section_content?: string | null
  sectionContent?: string | null
  affected_pages?: string[]
  active_page_slug?: string | null
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
  messages: Message[],
  threadId?: string
) => {
  if (!sessionId) return messages
  const pending = loadPendingMessage(sessionId, threadId)
  if (!pending?.assistant) return messages
  const restored = fromStoredMessage(pending.assistant)
  if (messages.some((message) => message.id === restored.id)) {
    return messages
  }
  if (
    restored.interview?.id &&
    messages.some((message) => message.interview?.id === restored.interview?.id)
  ) {
    clearPendingMessage(sessionId, threadId)
    return messages
  }
  const savedAt = pending.savedAt ? new Date(pending.savedAt) : null
  if (savedAt && Date.now() - savedAt.getTime() > PENDING_MESSAGE_TTL_MS) {
    clearPendingMessage(sessionId, threadId)
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
    clearPendingMessage(sessionId, threadId)
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

const extractMessagesList = (messagesResponse: unknown): ApiMessage[] =>
  Array.isArray(messagesResponse)
    ? (messagesResponse as ApiMessage[])
    : (messagesResponse as { messages?: ApiMessage[] })?.messages ?? []

const attachStepsToMessages = (
  messages: Message[],
  events: SessionEvent[]
): Message[] => {
  const stepsByRun = buildStepsFromEvents(events)
  if (stepsByRun.size === 0) return messages

  let next = messages
  for (const [, steps] of stepsByRun) {
    // Find the assistant message whose timestamp is closest to the events
    const eventTimes = events
      .filter((e) => STEP_EVENT_TYPES.has(e.type))
      .map((e) => new Date(e.created_at).getTime())
    if (eventTimes.length === 0) continue
    const minTime = Math.min(...eventTimes)
    const maxTime = Math.max(...eventTimes)

    let bestIndex = -1
    let bestDistance = Infinity
    for (let i = next.length - 1; i >= 0; i--) {
      const msg = next[i]
      if (msg.role !== 'assistant') continue
      if (msg.steps && msg.steps.length > 0) continue
      const msgTime = msg.timestamp?.getTime() ?? 0
      // Prefer messages whose timestamp falls within or just before the event range
      const distance = Math.abs(msgTime - maxTime)
      if (msgTime >= minTime - 60000 && distance < bestDistance) {
        bestDistance = distance
        bestIndex = i
      }
    }

    if (bestIndex < 0) {
      // Fallback: last assistant message without steps
      for (let i = next.length - 1; i >= 0; i--) {
        if (next[i].role === 'assistant' && (!next[i].steps || next[i].steps!.length === 0)) {
          bestIndex = i
          break
        }
      }
    }

    if (bestIndex < 0) continue
    if (next === messages) next = [...messages]
    next[bestIndex] = { ...next[bestIndex], steps }
  }

  return next
}

const buildBaseMessages = (
  sessionId: string | undefined,
  rawMessages: ApiMessage[],
  threadId?: string
) => {
  const mappedMessages = rawMessages.map(mapMessage)
  const payloadMap = buildInterviewPayloadMap(rawMessages, mappedMessages)
  let nextMessages = applyStoredInterview(sessionId, rawMessages, mappedMessages)
  nextMessages = reconcileInterviewSummaries(nextMessages, payloadMap)
  nextMessages = applyPendingMessage(sessionId, nextMessages, threadId)
  return { messages: nextMessages, payloadMap }
}

const applyInterviewEvents = (
  sessionId: string | undefined,
  messages: Message[],
  payloadMap: Map<string, { action?: string; answers: InterviewAnswer[] }>,
  events: SessionEvent[],
  threadId?: string
) => {
  const interviewBatches = buildInterviewBatchesFromEvents(events)
  if (interviewBatches.length === 0) return messages
  let nextMessages = attachInterviewBatches(messages, interviewBatches)
  nextMessages = reconcileInterviewSummaries(nextMessages, payloadMap)
  nextMessages = applyPendingMessage(sessionId, nextMessages, threadId)
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
      if (batch.status !== 'active') {
        continue
      }
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
  const rawContent =
    getCaseString(message, 'content', { trim: false }) ??
    getCaseString(message, 'message', { trim: false }) ??
    ''
  const parsedInterview = parseInterviewFromContent(rawContent)
  const role = getCaseString(message, 'role')
  const action = getCaseString(message, 'action') as Message['action'] | undefined
  const productDocUpdated =
    getCaseValue<boolean>(message, 'product_doc_updated') === true ||
    action === 'product_doc_updated'

  return {
    id: message.id ?? `m-${index}-${Date.now()}`,
    role: role === 'user' ? 'user' : 'assistant',
    content: parsedInterview.cleanContent,
    timestamp: toDate(getCaseString(message, 'created_at') ?? getCaseString(message, 'timestamp')),
    interviewSummary: parsedInterview.interviewSummary,
    action,
    productDocUpdated,
    productDocChangeSummary: getCaseString(message, 'change_summary'),
    productDocSectionName: getCaseString(message, 'section_name'),
    productDocSectionContent: getCaseString(message, 'section_content', { trim: false }),
    affectedPages: getCaseArray<string>(message, 'affected_pages'),
    activePageSlug: getCaseString(message, 'active_page_slug'),
    hidden:
      role === 'user' &&
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

export function useSession(sessionId?: string, threadId?: string) {
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

  // Track previous threadId to detect switches
  const prevThreadIdRef = React.useRef(threadId)

  const buildMessagesFromApi = React.useCallback(
    (sid: string, messagesResponse: unknown, tid?: string) => {
      const messagesList = extractMessagesList(messagesResponse)
      return {
        messagesList,
        base: buildBaseMessages(sid, messagesList, tid),
      }
    },
    []
  )

  const loadSessionData = React.useCallback(
    async (
      sid: string,
      tid: string | undefined,
      options?: { active?: () => boolean },
    ) => {
      const isActive = options?.active ?? (() => true)
      const loadStartedAt = Date.now()
      const fetches: [
        Promise<unknown>,
        Promise<unknown>,
        Promise<unknown>,
      ] = [
        api.sessions.get(sid),
        api.sessions.messages(sid, tid),
        api.sessions.versions(sid, { includePreviewHtml: false }),
      ]
      const [sessionResponse, messagesResponse, versionsResponse] =
        await Promise.all(fetches)
      if (!isActive()) return

      if (sessionResponse) {
        setSession(mapSession(sessionResponse as ApiSession))
      }

      const {
        messagesList,
        base: { messages: baseMessages, payloadMap },
      } = buildMessagesFromApi(sid, messagesResponse, tid)
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
              sid,
              undefined,
              INTERVIEW_EVENT_LIMIT,
            )
            if (!isActive()) return
            const events = (eventsResponse as { events?: SessionEvent[] })?.events ?? []
            if (events.length === 0) return
            setMessages((prev) => {
              let next = applyInterviewEvents(sid, prev, payloadMap, events, tid)
              next = attachStepsToMessages(next, events)
              return next
            })
          } catch {
            // Ignore event recovery failures, keep base messages.
          }
        })()
      }
    },
    [buildMessagesFromApi, setMessages],
  )

  const refresh = React.useCallback(async () => {
    if (!sessionId) return
    setIsLoading(true)
    setError(null)
    try {
      await loadSessionData(sessionId, threadId)
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load session'
      setError(message)
      return false
    } finally {
      setIsLoading(false)
    }
  }, [sessionId, threadId, loadSessionData])

  React.useEffect(() => {
    let active = true
    if (!sessionId) return

    const prevThreadId = prevThreadIdRef.current
    if (prevThreadId !== threadId) {
      if (prevThreadId !== undefined) {
        setMessagesState([])
        lastMessageUpdateRef.current = Date.now()
      }
      prevThreadIdRef.current = threadId
    }

    const load = async () => {
      setIsLoading(true)
      try {
        await loadSessionData(sessionId, threadId, {
          active: () => active,
        })
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
  }, [sessionId, threadId, loadSessionData])

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
