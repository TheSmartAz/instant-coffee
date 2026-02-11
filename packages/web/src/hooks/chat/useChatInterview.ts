import * as React from 'react'
import { saveInterviewBatch, clearInterviewBatch } from '@/lib/interviewStorage'
import { clearPendingMessage } from '@/lib/pendingMessageStorage'
import { normalizeInterviewQuestions } from '@/lib/interviewUtils'
import { createId, type InterviewPayloadLike } from '@/hooks/useChatUtils'
import type { InterviewAnswer, InterviewBatch, Message } from '@/types'

interface UseChatInterviewOptions {
  sessionId?: string
  messages: Message[]
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  updateMessageById: (id: string, updater: (message: Message) => Message) => void
  streamMessageIdRef: React.MutableRefObject<string | null>
  receivedEventRef: React.MutableRefObject<boolean>
  threadIdRef: React.MutableRefObject<string | null | undefined>
}

export function useChatInterview({
  sessionId,
  messages,
  setMessages,
  updateMessageById,
  streamMessageIdRef,
  receivedEventRef,
  threadIdRef,
}: UseChatInterviewOptions) {
  const interviewTotalRef = React.useRef(0)
  const interviewAnswersRef = React.useRef<Record<string, InterviewAnswer>>({})
  const interviewModeRef = React.useRef(false)
  const resumePendingRef = React.useRef(false)

  React.useEffect(() => {
    interviewTotalRef.current = 0
    interviewAnswersRef.current = {}
    interviewModeRef.current = false
  }, [sessionId])

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

  const resetInterviewState = React.useCallback(() => {
    interviewTotalRef.current = 0
    interviewAnswersRef.current = {}
    interviewModeRef.current = false
    clearInterviewBatch(sessionId)
    clearPendingMessage(sessionId, threadIdRef.current ?? undefined)
  }, [sessionId, threadIdRef])

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
            return { ...message, content: '', interview: updated }
          }
          return { ...message, content: '' }
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
    [sessionId, updateMessageById, receivedEventRef, streamMessageIdRef]
  )

  return {
    interviewTotalRef,
    interviewAnswersRef,
    interviewModeRef,
    resumePendingRef,
    updateInterviewByBatchId,
    setInterviewSummaryByBatchId,
    mergeInterviewAnswers,
    resetInterviewState,
    applyInterviewQuestions,
  }
}
