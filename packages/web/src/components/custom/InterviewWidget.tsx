import * as React from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import type {
  InterviewAnswer,
  InterviewBatch,
  InterviewOption,
  InterviewQuestion,
} from '@/types'

const OTHER_OPTION_ID = '__other__'

type LocalAnswer = {
  value?: string | string[]
  other?: string
}

interface InterviewWidgetProps {
  batch: InterviewBatch
  onAction: (payload: {
    action: 'submit' | 'skip' | 'generate'
    batchId: string
    answers: InterviewAnswer[]
  }) => void
}

const buildOptionsMap = (options?: InterviewOption[]) => {
  const map: Record<string, string> = {}
  if (!options) return map
  for (const option of options) {
    map[option.id] = option.label
  }
  return map
}

const deriveAnswerState = (answers?: InterviewAnswer[]) => {
  if (!answers) return {}
  const state: Record<string, LocalAnswer> = {}
  for (const answer of answers) {
    const value = answer.value
    state[answer.id] = {
      value,
      other: answer.other,
    }
  }
  return state
}

const getQuestionValue = (answer?: LocalAnswer) => answer?.value

const toArray = (value?: string | string[]) => {
  if (!value) return []
  return Array.isArray(value) ? value : [value]
}

const buildInterviewAnswers = (
  batch: InterviewBatch,
  answers: Record<string, LocalAnswer>
): InterviewAnswer[] => {
  const result: InterviewAnswer[] = []
  batch.questions.forEach((question, index) => {
    const answer = answers[question.id]
    const value = answer?.value
    const other = answer?.other
    if (!value && !other) return

    const optionsMap = buildOptionsMap(question.options)
    const globalIndex = batch.startIndex + index

    if (question.type === 'multi') {
      const values = toArray(value)
      const labels = values
        .map((item) => (item === OTHER_OPTION_ID ? other : optionsMap[item]))
        .filter((item): item is string => Boolean(item))
      if (labels.length === 0 && !other) return
      result.push({
        id: question.id,
        question: question.title,
        type: question.type,
        value: values,
        labels,
        other,
        index: globalIndex,
      })
      return
    }

    if (question.type === 'single') {
      const selected = Array.isArray(value) ? value[0] : value
      const label = selected
        ? selected === OTHER_OPTION_ID
          ? other
          : optionsMap[selected]
        : other
      if (!label && !other) return
      result.push({
        id: question.id,
        question: question.title,
        type: question.type,
        value: selected ?? '',
        label: label ?? other,
        other,
        index: globalIndex,
      })
      return
    }

    const textValue = Array.isArray(value) ? value[0] : value
    if (!textValue) return
    result.push({
      id: question.id,
      question: question.title,
      type: question.type,
      value: textValue,
      label: textValue,
      index: globalIndex,
    })
  })
  return result
}

const renderOption = (
  question: InterviewQuestion,
  option: InterviewOption,
  selected: string | string[] | undefined,
  onChange: (next: string | string[]) => void,
  readOnly: boolean
) => {
  const isMulti = question.type === 'multi'
  const selectedIds = toArray(selected)
  const checked = isMulti ? selectedIds.includes(option.id) : selected === option.id

  return (
    <label
      key={option.id}
      className={cn(
        'flex items-center gap-2 rounded-md border border-border/70 px-3 py-2 text-sm transition',
        checked ? 'border-primary/60 bg-primary/5 text-foreground' : 'text-muted-foreground',
        readOnly ? 'opacity-80' : 'hover:border-primary/50 hover:text-foreground'
      )}
    >
      <input
        type={isMulti ? 'checkbox' : 'radio'}
        name={question.id}
        disabled={readOnly}
        checked={checked}
        onChange={() => {
          if (readOnly) return
          if (isMulti) {
            const set = new Set(selectedIds)
            if (checked) {
              set.delete(option.id)
            } else {
              set.add(option.id)
            }
            onChange(Array.from(set))
            return
          }
          onChange(option.id)
        }}
        className="h-3.5 w-3.5 accent-primary"
      />
      <span>{option.label}</span>
    </label>
  )
}

export function InterviewWidget({ batch, onAction }: InterviewWidgetProps) {
  const [currentIndex, setCurrentIndex] = React.useState(0)
  const [answers, setAnswers] = React.useState<Record<string, LocalAnswer>>(() =>
    deriveAnswerState(batch.answers)
  )
  const [expanded, setExpanded] = React.useState(batch.status === 'active')

  React.useEffect(() => {
    setCurrentIndex(0)
  }, [batch.id])

  React.useEffect(() => {
    setAnswers(deriveAnswerState(batch.answers))
  }, [batch.answers])

  React.useEffect(() => {
    if (batch.status !== 'active') return
    if (!batch.answers || batch.answers.length === 0) return
    const answered = new Set(batch.answers.map((answer) => answer.id))
    const nextIndex = batch.questions.findIndex((question) => !answered.has(question.id))
    if (nextIndex >= 0) {
      setCurrentIndex(nextIndex)
    }
  }, [batch.answers, batch.questions, batch.status])

  React.useEffect(() => {
    if (batch.status === 'active') {
      setExpanded(true)
    }
  }, [batch.status])

  const readOnly = batch.status !== 'active'
  const question = batch.questions[currentIndex]
  const displayIndex = currentIndex + 1
  const displayTotal = batch.questions.length || batch.totalCount

  if (!question) return null

  const currentAnswer = answers[question.id]
  const selectedValue = getQuestionValue(currentAnswer)

  const setAnswerValue = (value: string | string[]) => {
    setAnswers((prev) => ({
      ...prev,
      [question.id]: {
        ...prev[question.id],
        value,
      },
    }))
  }

  const setOtherValue = (value: string) => {
    setAnswers((prev) => ({
      ...prev,
      [question.id]: {
        ...prev[question.id],
        other: value,
      },
    }))
  }

  const showOther = question.allow_other
  const otherSelected = question.type === 'multi'
    ? toArray(selectedValue).includes(OTHER_OPTION_ID)
    : selectedValue === OTHER_OPTION_ID

  const handleSubmit = (action: 'submit' | 'skip' | 'generate') => {
    const submittedAnswers = buildInterviewAnswers(batch, answers)
    onAction({
      action,
      batchId: batch.id,
      answers: submittedAnswers,
    })
  }

  return (
    <div className="rounded-lg border border-border bg-background/80 p-4">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Interview
        </div>
        <div className="text-xs text-muted-foreground">
          {displayIndex}/{displayTotal}
        </div>
      </div>
      {batch.prompt ? (
        <div className="mt-2 text-sm text-muted-foreground">{batch.prompt}</div>
      ) : null}

      {batch.status !== 'active' ? (
        <div className="mt-3 flex items-center justify-between rounded-md border border-dashed border-border/70 px-3 py-2 text-xs text-muted-foreground">
          <span>
            {batch.status === 'generated'
              ? 'Generated immediately'
              : batch.status === 'skipped'
                ? 'Skipped this batch'
                : 'Answers submitted'}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpanded((prev) => !prev)}
          >
            {expanded ? 'Collapse' : 'Expand'}
          </Button>
        </div>
      ) : null}

      {!expanded && batch.status !== 'active' ? null : (
        <div className="mt-4 space-y-4">
          <div className="text-sm font-medium text-foreground">
            {question.title}
          </div>
          {question.type === 'text' ? (
            <Input
              value={typeof selectedValue === 'string' ? selectedValue : ''}
              onChange={(event) => setAnswerValue(event.target.value)}
              placeholder={question.placeholder ?? 'Enter your answer'}
              disabled={readOnly}
            />
          ) : (
            <div className="space-y-2">
              {(question.options ?? []).map((option) =>
                renderOption(
                  question,
                  option,
                  selectedValue,
                  setAnswerValue,
                  readOnly
                )
              )}
              {showOther ? (
                <div className="space-y-2">
                  {renderOption(
                    question,
                    { id: OTHER_OPTION_ID, label: 'Other' },
                    selectedValue,
                    setAnswerValue,
                    readOnly
                  )}
                  <Input
                    value={currentAnswer?.other ?? ''}
                    onChange={(event) => setOtherValue(event.target.value)}
                    placeholder={question.other_placeholder ?? 'Enter your other answer'}
                    disabled={readOnly || !otherSelected}
                  />
                </div>
              ) : null}
            </div>
          )}

          <div className="flex items-center justify-between">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
              disabled={currentIndex === 0}
            >
              Previous
            </Button>
            {currentIndex < batch.questions.length - 1 ? (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCurrentIndex((prev) => Math.min(batch.questions.length - 1, prev + 1))}
              >
                Next
              </Button>
            ) : (
              <Button
                size="sm"
                className="bg-emerald-600 text-white hover:bg-emerald-500"
                onClick={() => handleSubmit('submit')}
                disabled={readOnly}
              >
                Submit answers
              </Button>
            )}
          </div>

          {batch.status === 'active' ? (
            <div className="flex items-center justify-between border-t border-border/60 pt-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleSubmit('skip')}
              >
                Skip questions
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleSubmit('generate')}
              >
                Generate now
              </Button>
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}
