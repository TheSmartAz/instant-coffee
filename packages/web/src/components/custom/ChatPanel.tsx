import * as React from 'react'
import { ChatInput } from './ChatInput'
import { ChatMessage } from './ChatMessage'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { useVirtualList } from '@/hooks/useVirtualList'
import type { InterviewActionPayload, Message } from '@/types'

export interface ChatPanelProps {
  messages: Message[]
  onSendMessage: (content: string, options?: { triggerInterview?: boolean; generateNow?: boolean }) => void
  onInterviewAction?: (payload: InterviewActionPayload) => void
  onTabChange?: (tab: 'preview' | 'code' | 'product-doc') => void
  onDisambiguationSelect?: (option: { id: string; slug: string; title: string }) => void
  isLoading?: boolean
  title?: string
  status?: string
  errorMessage?: string | null
  showHeader?: boolean
  showBorder?: boolean
  className?: string
}

export function ChatPanel({
  messages,
  onSendMessage,
  onInterviewAction,
  onTabChange,
  onDisambiguationSelect,
  isLoading = false,
  title = 'Conversation',
  status,
  errorMessage,
  showHeader = true,
  showBorder = true,
  className,
}: ChatPanelProps) {
  const bottomRef = React.useRef<HTMLDivElement | null>(null)
  const visibleMessages = React.useMemo(
    () => messages.filter((message) => !message.hidden),
    [messages]
  )
  const showEmptyState = !isLoading && visibleMessages.length === 0
  const rootRef = React.useRef<HTMLDivElement | null>(null)
  const [scrollElement, setScrollElement] = React.useState<HTMLDivElement | null>(null)
  const [autoScroll, setAutoScroll] = React.useState(true)

  React.useEffect(() => {
    const root = rootRef.current
    if (!root) return
    const viewport = root.querySelector(
      '[data-radix-scroll-area-viewport]'
    ) as HTMLDivElement | null
    if (!viewport) return
    setScrollElement(viewport)
  }, [])

  const {
    start,
    end,
    paddingTop,
    paddingBottom,
    totalHeight,
    scrollTop,
    viewportHeight,
    shouldVirtualize,
  } = useVirtualList({
    count: visibleMessages.length,
    estimateSize: 120,
    overscan: 8,
    minItems: 80,
    scrollElement,
  })

  const effectiveTotalHeight =
    scrollElement && !shouldVirtualize ? scrollElement.scrollHeight : totalHeight

  React.useEffect(() => {
    if (!scrollElement) return
    const isAtBottom = effectiveTotalHeight - scrollTop - viewportHeight < 80
    setAutoScroll(isAtBottom)
  }, [scrollElement, scrollTop, viewportHeight, effectiveTotalHeight])

  React.useLayoutEffect(() => {
    if (!autoScroll || !scrollElement) return
    scrollElement.scrollTo({ top: effectiveTotalHeight, behavior: 'smooth' })
  }, [autoScroll, scrollElement, effectiveTotalHeight, visibleMessages.length])

  const displayMessages = visibleMessages.slice(start, end)
  const isFirstMessage = visibleMessages.length === 0

  return (
    <div
      className={cn(
        'flex h-full flex-col',
        showBorder ? 'border-r border-border' : '',
        className
      )}
    >
      {showHeader ? (
        <div className="flex items-center justify-between px-6 py-4 text-sm font-semibold text-foreground">
          <span>{title}</span>
          {status ? (
            <span className="text-xs font-normal text-muted-foreground">{status}</span>
          ) : null}
        </div>
      ) : null}
      <ScrollArea ref={rootRef} className="flex-1">
        <div
          className="flex flex-col"
          role="log"
          aria-live="polite"
          aria-busy={isLoading}
        >
          {isLoading && messages.length === 0 ? (
            <div className="space-y-4 px-6 py-6">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="flex gap-4">
                  <Skeleton className="h-8 w-8 rounded-full" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-1/3" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-5/6" />
                  </div>
                </div>
              ))}
            </div>
          ) : null}
          {showEmptyState ? (
            <div className="px-6 py-10 text-sm text-muted-foreground">
              Start the conversation by describing what you want to build.
            </div>
          ) : null}
          <div className="px-6 py-6">
            <div style={{ paddingTop, paddingBottom }} className="space-y-6">
              {displayMessages.map((message, index) => (
                <ChatMessage
                  key={`${message.id}-${start + index}`}
                  {...message}
                  onInterviewAction={onInterviewAction}
                  onTabChange={onTabChange}
                  onDisambiguationSelect={onDisambiguationSelect}
                />
              ))}
            </div>
          </div>
          <div ref={bottomRef} />
        </div>
      </ScrollArea>
      {errorMessage ? (
        <div className="border-t border-border bg-destructive/10 px-4 py-2 text-xs text-destructive">
          {errorMessage}
        </div>
      ) : null}
      <div className="border-t border-border p-4">
        <ChatInput
          onSend={onSendMessage}
          disabled={isLoading}
          initialInterviewOn={isFirstMessage}
          showInterviewToggle
        />
      </div>
    </div>
  )
}
