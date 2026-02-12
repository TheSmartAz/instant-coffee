import * as React from 'react'

interface VirtualListOptions {
  count: number
  estimateSize: number
  overscan?: number
  minItems?: number
  scrollElement: HTMLElement | null
}

export function useVirtualList({
  estimateSize,
  overscan = 4,
  minItems = 40,
  scrollElement,
}: VirtualListOptions & { count: number }) {
  const [scrollTop, setScrollTop] = React.useState(0)
  const [viewportHeight, setViewportHeight] = React.useState(0)
  // Track actual item heights using Map by item ID (message.id)
  const itemHeightsRef = React.useRef<Map<string, number>>(new Map())
  const [version, setVersion] = React.useState(0) // Increment to force re-render

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

  // Force re-render when heights change
  const markHeightsChanged = React.useCallback(() => {
    setVersion((v) => v + 1)
  }, [])

  return {
    scrollTop,
    viewportHeight,
    itemHeightsRef,
    markHeightsChanged,
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
  const itemHeightsRef = React.useRef<Map<string, number>>(new Map())
  const [totalVersion, setTotalVersion] = React.useState(0)

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
      height += itemHeightsRef.current.get(String(i)) ?? estimateSize
    }
    return height
  }, [count, estimateSize, totalVersion])

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
    itemHeightsRef,
    updateItemHeight: (index: number, height: number) => {
      const key = String(index)
      const current = itemHeightsRef.current.get(key)
      if (height > 0 && current !== height) {
        itemHeightsRef.current.set(key, height)
        setTotalVersion((v) => v + 1)
      }
    },
  }
}
