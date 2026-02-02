import type { InterviewAnswer, InterviewQuestion } from '@/types'

const QUESTION_TYPES = new Set(['single', 'multi', 'text'])

const normalizeQuestionType = (value: unknown): InterviewQuestion['type'] => {
  if (typeof value !== 'string') return 'text'
  const lowered = value.toLowerCase()
  return QUESTION_TYPES.has(lowered) ? (lowered as InterviewQuestion['type']) : 'text'
}

export const normalizeInterviewQuestions = (questions: unknown): InterviewQuestion[] => {
  if (!Array.isArray(questions)) return []
  return questions
    .map((item, index) => {
      if (!item || typeof item !== 'object') return null
      const raw = item as Record<string, unknown>
      const id = String(raw.id ?? raw.key ?? raw.name ?? `q${index + 1}`)
      const title = String(raw.title ?? raw.question ?? '')
      if (!title) return null
      const type = normalizeQuestionType(raw.type)
      const options = Array.isArray(raw.options)
        ? raw.options
            .map((opt, optIndex) => {
              if (!opt || typeof opt !== 'object') return null
              const option = opt as Record<string, unknown>
              const optionId = String(option.id ?? option.value ?? `opt${optIndex + 1}`)
              const label = String(option.label ?? option.text ?? optionId)
              return { id: optionId, label }
            })
            .filter(Boolean)
        : undefined
      const allowOther = Boolean(raw.allow_other ?? raw.allowOther)
      const otherPlaceholder =
        raw.other_placeholder ?? raw.otherPlaceholder ?? 'Enter your other answer'
      const placeholder = raw.placeholder ?? 'Enter your answer'
      return {
        id,
        type,
        title,
        options,
        allow_other: allowOther,
        other_placeholder: String(otherPlaceholder),
        placeholder: String(placeholder),
      }
    })
    .filter(Boolean) as InterviewQuestion[]
}

export const normalizeInterviewAnswers = (answers: unknown): InterviewAnswer[] => {
  if (!Array.isArray(answers)) return []
  return answers
    .map((item, index) => {
      if (!item || typeof item !== 'object') return null
      const raw = item as Record<string, unknown>
      const id = String(
        raw.id ?? raw.question_id ?? raw.questionId ?? raw.key ?? `a${index + 1}`
      )
      const question = String(raw.question ?? raw.title ?? raw.prompt ?? id)
      const type = normalizeQuestionType(raw.type)
      const value = raw.value ?? raw.answer ?? raw.response ?? raw.label ?? raw.labels
      const labels = Array.isArray(raw.labels)
        ? raw.labels.filter((label): label is string => typeof label === 'string')
        : undefined
      const label = typeof raw.label === 'string' ? raw.label : undefined
      const other = typeof raw.other === 'string' ? raw.other : undefined
      const indexValue =
        typeof raw.index === 'number'
          ? raw.index
          : typeof raw.order === 'number'
            ? raw.order
            : undefined
      const resolvedValue =
        typeof value === 'string' || Array.isArray(value)
          ? (value as string | string[])
          : label
            ? label
            : labels && labels.length > 0
              ? labels
              : other ?? ''
      return {
        id,
        question,
        type,
        value: Array.isArray(resolvedValue) ? resolvedValue : String(resolvedValue),
        label,
        labels,
        other,
        index: indexValue ?? index + 1,
      }
    })
    .filter(Boolean) as InterviewAnswer[]
}

export const mergeInterviewAnswerList = (
  base: InterviewAnswer[] | undefined,
  incoming: InterviewAnswer[]
): InterviewAnswer[] => {
  if (!base || base.length === 0) return incoming
  const byId = new Map(base.map((answer) => [answer.id, answer]))
  for (const answer of incoming) {
    const existing = byId.get(answer.id)
    byId.set(answer.id, existing ? { ...existing, ...answer } : answer)
  }
  return Array.from(byId.values())
}
