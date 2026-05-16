import * as React from 'react'

import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/components/ui/resizable'
import { cn } from '@/lib/utils'

const DESKTOP_QUERY = '(min-width: 1024px)'

interface ResizableSplitPaneProps {
  left: React.ReactNode
  right: React.ReactNode
  className?: string
  leftClassName?: string
  rightClassName?: string
  defaultLeftSize?: number
  minLeftSize?: number
  maxLeftSize?: number
}

function useIsDesktop() {
  const [isDesktop, setIsDesktop] = React.useState(() =>
    typeof window === 'undefined' ? true : window.matchMedia(DESKTOP_QUERY).matches
  )

  React.useEffect(() => {
    const mediaQuery = window.matchMedia(DESKTOP_QUERY)
    const update = () => setIsDesktop(mediaQuery.matches)

    update()
    mediaQuery.addEventListener('change', update)
    return () => mediaQuery.removeEventListener('change', update)
  }, [])

  return isDesktop
}

export function ResizableSplitPane({
  left,
  right,
  className,
  leftClassName,
  rightClassName,
  defaultLeftSize = 30,
  minLeftSize = 30,
  maxLeftSize = 66,
}: ResizableSplitPaneProps) {
  const isDesktop = useIsDesktop()

  if (!isDesktop) {
    return (
      <div className={cn('flex h-full min-h-0 flex-col overflow-hidden', className)}>
        <section
          className={cn(
            'min-h-[360px] flex-[0_0_min(52%,520px)] overflow-hidden border-b border-border sm:min-h-[400px]',
            leftClassName
          )}
        >
          {left}
        </section>
        <section className={cn('min-h-0 flex-1 overflow-hidden', rightClassName)}>
          {right}
        </section>
      </div>
    )
  }

  return (
    <ResizablePanelGroup
      direction="horizontal"
      className={cn('min-h-0 overflow-hidden', className)}
    >
      <ResizablePanel
        defaultSize={`${defaultLeftSize}%`}
        minSize={`${minLeftSize}%`}
        maxSize={`${maxLeftSize}%`}
        className={cn('min-w-0 overflow-hidden lg:min-w-[360px]', leftClassName)}
      >
        {left}
      </ResizablePanel>
      <ResizableHandle
        withHandle
        className="w-2 bg-transparent transition-colors after:w-2 hover:bg-accent/60 data-[resize-handle-state=drag]:bg-accent"
      />
      <ResizablePanel
        minSize="28%"
        className={cn('min-w-0 overflow-hidden lg:min-w-[320px] xl:min-w-[360px]', rightClassName)}
      >
        {right}
      </ResizablePanel>
    </ResizablePanelGroup>
  )
}
