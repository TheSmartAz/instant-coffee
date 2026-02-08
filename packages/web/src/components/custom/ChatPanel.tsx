import * as React from 'react'
import { ChatInput, type ChatInputProps } from './ChatInput'
import { ChatMessage } from './ChatMessage'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { useVirtualList } from '@/hooks/useVirtualList'
import type {
  ChatAsset,
  ChatAttachment,
  ChatStyleReference,
  InterviewActionPayload,
  Message,
  Page,
} from '@/types'

const ASSET_REFERENCE_RE = /asset:[A-Za-z0-9_-]+/g

const extractAssetIds = (content?: string) => {
  if (!content) return []
  const matches = content.match(ASSET_REFERENCE_RE)
  if (!matches || matches.length === 0) return []
  return Array.from(new Set(matches))
}

export interface ChatPanelProps {
  messages: Message[]
  assets?: ChatAsset[]
  onSendMessage: (
    content: string,
    options?: {
      triggerInterview?: boolean
      generateNow?: boolean
      attachments?: ChatAttachment[]
      targetPages?: string[]
      styleReference?: ChatStyleReference
    }
  ) => void
  onAssetUpload?: ChatInputProps['onAssetUpload']
  onAssetRemove?: (assetId: string) => void
  onInterviewAction?: (payload: InterviewActionPayload) => void
  onTabChange?: (tab: 'preview' | 'code' | 'product-doc' | 'data') => void
  onDisambiguationSelect?: (option: { id: string; slug: string; title: string }) => void
  isLoading?: boolean
  title?: string
  status?: string
  errorMessage?: string | null
  showHeader?: boolean
  showBorder?: boolean
  className?: string
  pages?: Page[]
}

export function ChatPanel({
  messages,
  assets,
  onSendMessage,
  onAssetUpload,
  onAssetRemove,
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
  pages,
}: ChatPanelProps) {
  const bottomRef = React.useRef<HTMLDivElement | null>(null)
  const visibleMessages = React.useMemo(
    () => messages.filter((message) => !message.hidden),
    [messages]
  )
  const assetLookup = React.useMemo(() => {
    const map = new Map<string, ChatAsset>()
    if (assets) {
      assets.forEach((asset) => {
        map.set(asset.id, asset)
      })
    }
    return map
  }, [assets])
  const assetsProvided = assets !== undefined
  const hasAssetMentions = React.useMemo(
    () =>
      visibleMessages.some(
        (message) =>
          (message.assets && message.assets.length > 0) ||
          extractAssetIds(message.content).length > 0
      ),
    [visibleMessages]
  )
  const assetMessage = React.useMemo(() => {
    if (!assets || assets.length === 0) return null
    if (hasAssetMentions) return null
    return {
      id: 'asset-summary',
      role: 'user',
      content: 'Uploaded assets',
      assets,
    } as Message
  }, [assets, hasAssetMentions])
  const displayMessages = React.useMemo(
    () => (assetMessage ? [assetMessage, ...visibleMessages] : visibleMessages),
    [assetMessage, visibleMessages]
  )
  const showEmptyState = !isLoading && displayMessages.length === 0
  const rootRef = React.useRef<HTMLDivElement | null>(null)
  const [scrollElement, setScrollElement] = React.useState<HTMLDivElement | null>(null)
  const [autoScroll, setAutoScroll] = React.useState(true)
  const resolveMessageAssets = React.useCallback(
    (message: Message) => {
      const collected = new Map<string, ChatAsset>()
      if (message.assets) {
        message.assets.forEach((asset) => {
          if (!assetsProvided || assetLookup.has(asset.id)) {
            collected.set(asset.id, assetLookup.get(asset.id) ?? asset)
          }
        })
      }
      const referencedIds = extractAssetIds(message.content)
      referencedIds.forEach((id) => {
        const asset = assetLookup.get(id)
        if (asset) collected.set(asset.id, asset)
      })
      return Array.from(collected.values())
    },
    [assetLookup, assetsProvided]
  )

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
    count: displayMessages.length,
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
  }, [autoScroll, scrollElement, effectiveTotalHeight, displayMessages.length])

  const windowedMessages = displayMessages.slice(start, end)
  const isFirstMessage = displayMessages.length === 0

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
              {windowedMessages.map((message, index) => {
                const messageAssets = resolveMessageAssets(message)
                return (
                  <ChatMessage
                    key={`${message.id}-${start + index}`}
                    {...message}
                    assets={messageAssets.length > 0 ? messageAssets : undefined}
                    onAssetRemove={onAssetRemove}
                    onInterviewAction={onInterviewAction}
                    onTabChange={onTabChange}
                    onDisambiguationSelect={onDisambiguationSelect}
                  />
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
      <div className="border-t border-border p-4">
        <ChatInput
          onSend={onSendMessage}
          onAssetUpload={onAssetUpload}
          disabled={isLoading}
          initialInterviewOn={isFirstMessage}
          showInterviewToggle
          pages={pages}
        />
      </div>
    </div>
  )
}
