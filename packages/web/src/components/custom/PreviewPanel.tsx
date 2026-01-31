import * as React from 'react'
import { RefreshCw, Download, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { PhoneFrame } from './PhoneFrame'

export interface PreviewPanelProps {
  htmlContent?: string
  previewUrl?: string | null
  onRefresh?: () => void
  onExport?: () => void
  isRefreshing?: boolean
  isExporting?: boolean
}

export function PreviewPanel({
  htmlContent,
  previewUrl,
  onRefresh,
  onExport,
  isRefreshing = false,
  isExporting = false,
}: PreviewPanelProps) {
  const containerRef = React.useRef<HTMLDivElement | null>(null)
  const [scale, setScale] = React.useState(1)

  React.useEffect(() => {
    if (!containerRef.current) return

    const updateScale = () => {
      if (!containerRef.current) return
      const width = containerRef.current.clientWidth
      const nextScale = Math.min(1, Math.max(0.6, width / 460))
      setScale(nextScale)
    }

    updateScale()
    const observer = new ResizeObserver(updateScale)
    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-6 py-4">
        <span className="text-sm font-semibold text-foreground">Preview</span>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={onRefresh}
            aria-label="Refresh preview"
            disabled={isRefreshing || !onRefresh}
          >
            {isRefreshing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={onExport}
            aria-label="Export preview"
            disabled={isExporting || !onExport}
          >
            {isExporting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>
      <div ref={containerRef} className="flex flex-1 items-center justify-center bg-muted/30 p-6">
        <PhoneFrame scale={scale}>
          <iframe
            title="Preview"
            className="h-full w-full border-0"
            sandbox="allow-scripts allow-same-origin"
            {...(previewUrl
              ? { src: previewUrl }
              : { srcDoc: htmlContent ?? '' })}
          />
        </PhoneFrame>
      </div>
    </div>
  )
}
