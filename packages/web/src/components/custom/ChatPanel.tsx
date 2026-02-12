import * as React from 'react'
import { ChatInput, type ChatInputProps } from './ChatInput'
import { ChatMessage } from './ChatMessage'
import { TokenDisplay } from '@/components/TokenDisplay'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { useChatVirtualList } from '@/hooks/useVirtualList'
import type {
  InterviewActionPayload,
  Message,
  Page,
  SessionTokenSummary,
} from '@/types'

export interface ChatPanelProps {
  messages: Message[]
  onSendMessage: (
    content: string,
    options?: {
      triggerInterview?: boolean
      generateNow?: boolean
      targetPages?: string[]
      mentionedFiles?: string[]
    }
  ) => void
  onAssetUpload?: ChatInputProps['onAssetUpload']
  onInterviewAction?: (payload: InterviewActionPayload) => void
  onTabChange?: (tab: 'preview' | 'code' | 'product-doc' | 'data') => void
  isLoading?: boolean
  errorMessage?: string | null
  className?: string
  pages?: Page[]
  tokenUsage?: SessionTokenSummary
}

export function ChatPanel({
  messages,
  onSendMessage,
  onAssetUpload,
  onInterviewAction,
  onTabChange,
  isLoading = false,
  errorMessage,
  className,
  pages,
  tokenUsage,
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
  // Track refs for each message to measure their height
  const messageRefs = React.useRef<Map<number, HTMLDivElement>>(new Map())

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
    updateItemHeight,
  } = useChatVirtualList(
    visibleMessages.length,
    scrollElement,
    200, // estimateSize
    8, // overscan
    80 // minItems
  )

  // Observe message heights using ResizeObserver
  React.useEffect(() => {
    if (!scrollElement || visibleMessages.length === 0) return

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const target = entry.target as HTMLElement
        // Find the message index from the ref map
        for (const [index, el] of messageRefs.current.entries()) {
          if (el === target) {
            const height = entry.borderBoxSize?.[0]?.blockSize ?? entry.contentRect.height
            if (height > 0) {
              updateItemHeight(index, height)
            }
            break
          }
        }
      }
    })

    // Observe all message elements
    messageRefs.current.forEach((el) => {
      if (el) observer.observe(el)
    })

    return () => observer.disconnect()
  }, [visibleMessages.length, updateItemHeight, scrollElement])

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

  const windowedMessages = visibleMessages.slice(start, end)

  return (
    <div className={cn('flex h-full flex-col', className)}>
      <ScrollArea ref={rootRef} className="flex-1">
        <div
          className="flex flex-col"
          role="log"
          aria-live="polite"
          aria-busy={isLoading}
        >
          {isLoading && messages.length === 0 ? (
            <div className="space-y-4 px-6 py-6">
              {Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="flex gap-4">
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
            <div className="flex flex-col items-center gap-6 px-6 py-16">
              <div className="text-center">
                <h3 className="text-base font-medium text-foreground mb-1">
                  What would you like to build?
                </h3>
                <p className="text-sm text-muted-foreground">
                  Describe your idea and I&apos;ll create a mobile-optimized page for you.
                </p>
              </div>
              <div className="grid w-full max-w-md gap-2">
                {[
                  'A product landing page for a coffee subscription service',
                  'A personal portfolio with project showcase',
                  'A restaurant menu with online ordering',
                  'An event invitation page with RSVP form',
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    className="rounded-lg border border-border bg-card px-4 py-3 text-left text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:bg-accent hover:text-foreground"
                    onClick={() => onSendMessage(suggestion)}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          <div className="px-4 py-4">
            <div style={{ paddingTop, paddingBottom }} className="space-y-3">
              {windowedMessages.map((message, index) => {
                const messageIndex = start + index
                return (
                  <div
                    key={message.id}
                    ref={(el) => {
                      if (el) messageRefs.current.set(messageIndex, el)
                      else messageRefs.current.delete(messageIndex)
                    }}
                  >
                    <ChatMessage
                      {...message}
                      onInterviewAction={onInterviewAction}
                      onTabChange={onTabChange}
                    />
                  </div>
                )
              })}
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
      {tokenUsage && tokenUsage.total.total_tokens > 0 ? (
        <div className="border-t border-border px-3 py-2">
          <TokenDisplay usage={tokenUsage} showDetails={false} />
        </div>
      ) : null}
      <div className="p-4">
        <ChatInput
          onSend={onSendMessage}
          onAssetUpload={onAssetUpload}
          disabled={isLoading}
          pages={pages}
        />
      </div>
    </div>
  )
}
