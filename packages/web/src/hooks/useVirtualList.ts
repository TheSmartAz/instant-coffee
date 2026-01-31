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
  const totalHeight = count * estimateSize

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
  }
}
