import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface PhoneFrameProps {
  children: ReactNode
  className?: string
  scale?: number
}

export function PhoneFrame({ children, className, scale = 1 }: PhoneFrameProps) {
  const clampedScale = Math.min(1, Math.max(0.5, scale))

  return (
    <div
      className={cn('relative w-full max-w-[430px] aspect-[9/19.5]', className)}
      style={{ transform: `scale(${clampedScale})`, transformOrigin: 'top center' }}
    >
      <div className="absolute inset-0 rounded-[34px] border-[3px] border-border bg-background shadow-[0_18px_48px_-32px_rgba(15,23,42,0.55)]" />
      <div className="relative h-full w-full overflow-hidden rounded-[32px] bg-background ring-1 ring-black/10">
        <div className="h-full w-full pt-0">{children}</div>
      </div>
    </div>
  )
}
