import { useState } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { MessageImage } from '@/types'

const INTENT_LABELS: Record<string, string> = {
  asset: 'Asset',
  style_reference: 'Style Ref',
  layout_reference: 'Layout Ref',
  screenshot: 'Screenshot',
}

interface ChatImageGridProps {
  images: MessageImage[]
  className?: string
}

export function ChatImageGrid({ images, className }: ChatImageGridProps) {
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null)

  if (!images.length) return null

  return (
    <>
      <div className={cn('flex flex-wrap gap-1.5', className)}>
        {images.map((img, i) => (
          <button
            key={`${img.name ?? ''}-${i}`}
            type="button"
            onClick={() => setLightboxIndex(i)}
            className="group relative h-16 w-16 shrink-0 overflow-hidden rounded-lg border border-white/20 bg-black/10 transition hover:ring-2 hover:ring-white/40"
          >
            <img
              src={img.data}
              alt={img.name ?? 'Uploaded image'}
              className="h-full w-full object-cover"
            />
            {img.intent && INTENT_LABELS[img.intent] ? (
              <span className="absolute bottom-0.5 left-0.5 rounded bg-black/60 px-1 py-px text-[8px] font-medium text-white">
                {INTENT_LABELS[img.intent]}
              </span>
            ) : null}
          </button>
        ))}
      </div>

      {/* Lightbox */}
      {lightboxIndex !== null ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
          onClick={() => setLightboxIndex(null)}
          role="dialog"
          aria-modal="true"
          aria-label="Image preview"
        >
          <button
            type="button"
            onClick={() => setLightboxIndex(null)}
            className="absolute right-4 top-4 rounded-full bg-white/10 p-2 text-white hover:bg-white/20 transition"
            aria-label="Close preview"
          >
            <X className="h-5 w-5" />
          </button>
          <img
            src={images[lightboxIndex].data}
            alt={images[lightboxIndex].name ?? 'Full size image'}
            className="max-h-[85vh] max-w-[90vw] rounded-lg object-contain"
            onClick={(e) => e.stopPropagation()}
          />
          {images[lightboxIndex].intent && INTENT_LABELS[images[lightboxIndex].intent!] ? (
            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 rounded-full bg-black/60 px-3 py-1 text-xs text-white">
              {INTENT_LABELS[images[lightboxIndex].intent!]}
            </div>
          ) : null}
        </div>
      ) : null}
    </>
  )
}
