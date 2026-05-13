import * as React from 'react'

interface VirtualListOptions {
  count: number
  estimateSize: number
  overscan?: number
  minItems?: number
  scrollElement: HTMLElement | null
}

export function useVirtualList({
  count,
  estimateSize,
  overscan = 4,
  minItems = 40,
  scrollElement,
}: VirtualListOptions) {
  const [scrollTop, setScrollTop] = React.useState(0)
  const [viewportHeight, setViewportHeight] = React.useState(0)

  React.useLayoutEffect(() => {
    if (!scrollElement) return

    const handleScroll = () => {
      setScrollTop(scrollElement.scrollTop)
    }

    const updateSize = () => {
      setViewportHeight(scrollElement.clientHeight)
    }

    updateSize()
    handleScroll()

    scrollElement.addEventListener('scroll', handleScroll)
    const observer = new ResizeObserver(updateSize)
    observer.observe(scrollElement)

    return () => {
      scrollElement.removeEventListener('scroll', handleScroll)
      observer.disconnect()
    }
  }, [scrollElement])

  const shouldVirtualize = count > minItems && viewportHeight > 0
  const start = shouldVirtualize
    ? Math.max(0, Math.floor(scrollTop / estimateSize) - overscan)
    : 0
  const end = shouldVirtualize
    ? Math.min(count, Math.ceil((scrollTop + viewportHeight) / estimateSize) + overscan)
    : count
  const totalHeight = count * estimateSize
  const paddingTop = start * estimateSize
  const paddingBottom = Math.max(0, totalHeight - end * estimateSize)

  return {
    start,
    end,
    paddingTop,
    paddingBottom,
    totalHeight,
    scrollTop,
    viewportHeight,
    shouldVirtualize,
  }
}

// Helper hook that handles the dynamic height logic for chat messages
export function useChatVirtualList(
  count: number,
  scrollElement: HTMLElement | null,
  estimateSize: number = 200,
  overscan: number = 8,
  minItems: number = 80
) {
  const [scrollTop, setScrollTop] = React.useState(0)
  const [viewportHeight, setViewportHeight] = React.useState(0)
  const [itemHeights, setItemHeights] = React.useState<Map<string, number>>(
    () => new Map()
  )

  React.useLayoutEffect(() => {
    if (!scrollElement) return

    const handleScroll = () => {
      setScrollTop(scrollElement.scrollTop)
    }

    const updateSize = () => {
      setViewportHeight(scrollElement.clientHeight)
    }

    updateSize()
    handleScroll()

    scrollElement.addEventListener('scroll', handleScroll)
    const observer = new ResizeObserver(updateSize)
    observer.observe(scrollElement)

    return () => {
      scrollElement.removeEventListener('scroll', handleScroll)
      observer.disconnect()
    }
  }, [scrollElement])

  // Calculate total height with dynamic item heights
  const totalHeight = React.useMemo(() => {
    let height = 0
    for (let i = 0; i < count; i++) {
      height += itemHeights.get(String(i)) ?? estimateSize
    }
    return height
  }, [count, estimateSize, itemHeights])

  const shouldVirtualize = count > minItems && viewportHeight > 0

  // Calculate render range
  const start = shouldVirtualize
    ? Math.max(0, Math.floor(scrollTop / estimateSize) - overscan)
    : 0
  const end = shouldVirtualize
    ? Math.min(count, Math.ceil((scrollTop + viewportHeight) / estimateSize) + overscan)
    : count

  const paddingTop = start * estimateSize
  const paddingBottom = totalHeight - end * estimateSize

  return {
    start,
    end,
    paddingTop,
    paddingBottom,
    totalHeight,
    scrollTop,
    viewportHeight,
    shouldVirtualize,
    updateItemHeight: React.useCallback((index: number, height: number) => {
      if (height <= 0) return
      const key = String(index)
      setItemHeights((prev) => {
        const current = prev.get(key)
        if (current === height) return prev
        const next = new Map(prev)
        next.set(key, height)
        return next
      })
    }, []),
  }
}
