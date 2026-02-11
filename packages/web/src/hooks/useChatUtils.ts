/**
 * Shared utilities and types for the chat system.
 * Extracted from useChat.ts to reduce file size.
 */

import type {
  InterviewActionPayload,
  InterviewAnswer,
  InterviewQuestion,
} from '@/types'
import { getCaseString } from '@/lib/caseAccess'
import type { ExecutionEvent } from '@/types/events'

export const createId = () => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export const safeJsonParse = (value: string) => {
  try {
    return JSON.parse(value)
  } catch {
    return null
  }
}

export type ProductDocUpdatePayloadLike = {
  change_summary?: unknown
  changeSummary?: unknown
  section_name?: unknown
  sectionName?: unknown
  section_content?: unknown
  sectionContent?: unknown
}

export const extractProductDocUpdateFields = (payload: ProductDocUpdatePayloadLike) => {
  const changeSummary = getCaseString(payload, 'change_summary')
  const sectionName = getCaseString(payload, 'section_name')
  const sectionContent = getCaseString(payload, 'section_content', { trim: false })

  return { changeSummary, sectionName, sectionContent }
}

export const isEventPayload = (payload: unknown): payload is ExecutionEvent =>
  Boolean(payload && typeof payload === 'object' && 'type' in payload)

export type InterviewPayloadLike = {
  phase?: string
  questions?: InterviewQuestion[]
  message?: string
  batch_id?: string
  batchId?: string
}

export const isInterviewPayload = (payload: unknown): payload is InterviewPayloadLike =>
  Boolean(payload && typeof payload === 'object' && 'questions' in payload)

export const formatInterviewSummaryText = (answers: InterviewAnswer[]) => {
  const items = answers.map((item) => {
    const label = item.labels?.join(', ') ?? item.label ?? String(item.value)
    return `${item.question}=${label}`
  })
  return items.length ? `Answer summary: ${items.join('; ')}` : 'Answer summary:'
}

export const buildInterviewPayload = (
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

export const PRODUCT_DOC_ACTIONS = new Set([
  'product_doc_generated',
  'product_doc_updated',
  'product_doc_confirmed',
  'product_doc_outdated',
])
