import * as React from 'react'
import { getCaretCoords } from '@/lib/caretPosition'
import { filterPages } from '@/utils/chat'
import type { Page } from '@/types'

const MENTION_POPOVER_WIDTH = 288
const MENTION_POPOVER_HEIGHT = 224

const isValidMentionBoundary = (value?: string) =>
  !value || !/[A-Za-z0-9_]/.test(value)

export type MentionType = 'page' | 'file'

const findMentionAtCursor = (value: string, cursor: number): {
  start: number
  end: number
  query: string
  mentionType: MentionType
} | null => {
  const uptoCursor = value.slice(0, cursor)
  const atIndex = uptoCursor.lastIndexOf('@')
  if (atIndex === -1) return null
  const prevChar = atIndex > 0 ? value[atIndex - 1] : undefined
  if (!isValidMentionBoundary(prevChar)) return null

  const fragment = uptoCursor.slice(atIndex + 1)

  // Check for @file: prefix
  if (fragment.startsWith('file:')) {
    const fileQuery = fragment.slice(5) // after "file:"
    if (!/^[A-Za-z0-9_./\-]*$/.test(fileQuery)) return null
    return { start: atIndex, end: cursor, query: fileQuery, mentionType: 'file' }
  }

  // Standard page mention
  if (!/^[A-Za-z0-9_-]*$/.test(fragment)) return null
  return { start: atIndex, end: cursor, query: fragment, mentionType: 'page' }
}

export interface MentionPosition {
  x: number
  y: number
  placement: 'top' | 'bottom'
  arrowOffset: number
}

export interface MentionRange {
  start: number
  end: number
}

export interface UseMentionStateReturn {
  mentionOpen: boolean
  mentionQuery: string
  mentionType: MentionType
  mentionIndex: number
  mentionRange: MentionRange | null
  mentionPosition: MentionPosition | null
  filteredPages: Page[]
  setMentionOpen: React.Dispatch<React.SetStateAction<boolean>>
  setMentionIndex: React.Dispatch<React.SetStateAction<number>>
  updateMentionState: (value: string, cursor: number) => void
  closeMention: () => void
}

export function useMentionState(
  pages: Page[],
  textareaRef: React.RefObject<HTMLTextAreaElement | null>,
): UseMentionStateReturn {
  const [mentionOpen, setMentionOpen] = React.useState(false)
  const [mentionQuery, setMentionQuery] = React.useState('')
  const [mentionType, setMentionType] = React.useState<MentionType>('page')
  const [mentionIndex, setMentionIndex] = React.useState(0)
  const [mentionRange, setMentionRange] = React.useState<MentionRange | null>(null)
  const [mentionPosition, setMentionPosition] = React.useState<MentionPosition | null>(null)

  const filteredPages = React.useMemo(
    () => filterPages(pages, mentionQuery),
    [pages, mentionQuery],
  )

  React.useEffect(() => {
    if (!mentionOpen) return
    setMentionIndex((current) =>
      Math.min(current, Math.max(filteredPages.length - 1, 0)),
    )
  }, [filteredPages.length, mentionOpen])

  const updateMentionState = React.useCallback(
    (value: string, cursor: number) => {
      const mention = findMentionAtCursor(value, cursor)
      if (!mention) {
        setMentionOpen(false)
        setMentionQuery('')
        setMentionRange(null)
        return
      }

      const textarea = textareaRef.current
      if (textarea) {
        const coords = getCaretCoords(textarea, mention.end)
        const rect = textarea.getBoundingClientRect()
        const baseX = rect.left + coords.left - textarea.scrollLeft
        const baseY = rect.top + coords.top - textarea.scrollTop + coords.lineHeight + 8

        let nextX = baseX
        let nextY = baseY
        let placement: 'top' | 'bottom' = 'bottom'
        const margin = 8
        const maxX = window.innerWidth - MENTION_POPOVER_WIDTH - margin
        const maxY = window.innerHeight - MENTION_POPOVER_HEIGHT - margin

        if (nextX > maxX) nextX = Math.max(margin, maxX)
        if (nextY > maxY) {
          const above = rect.top + coords.top - MENTION_POPOVER_HEIGHT - margin
          if (above > margin) {
            nextY = above
            placement = 'top'
          } else {
            nextY = Math.max(margin, maxY)
          }
        }

        const unclampedArrow = baseX - nextX
        const arrowOffset = Math.min(
          Math.max(unclampedArrow, 12),
          MENTION_POPOVER_WIDTH - 12,
        )

        setMentionPosition({ x: nextX, y: nextY, placement, arrowOffset })
      }

      const isSameMention =
        mentionRange?.start === mention.start && mentionQuery === mention.query
      setMentionRange({ start: mention.start, end: mention.end })
      setMentionQuery(mention.query)
      setMentionType(mention.mentionType)
      setMentionIndex((current) => (isSameMention ? current : 0))
      setMentionOpen(true)
    },
    [mentionQuery, mentionRange, textareaRef],
  )

  const closeMention = React.useCallback(() => {
    setMentionOpen(false)
    setMentionQuery('')
    setMentionRange(null)
  }, [])

  return {
    mentionOpen,
    mentionQuery,
    mentionType,
    mentionIndex,
    mentionRange,
    mentionPosition,
    filteredPages,
    setMentionOpen,
    setMentionIndex,
    updateMentionState,
    closeMention,
  }
}
