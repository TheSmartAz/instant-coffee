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
      <div className="absolute inset-0 rounded-[48px] bg-black shadow-[0_24px_60px_-30px_rgba(0,0,0,0.6)]" />
      <div className="absolute inset-[6px] rounded-[44px] bg-zinc-900" />
      <div className="relative z-10 m-[10px] h-[calc(100%-20px)] rounded-[36px] overflow-hidden bg-black">
        <div className="absolute left-1/2 top-[10px] h-[28px] w-[120px] -translate-x-1/2 rounded-full bg-zinc-950 shadow-[0_0_0_1px_rgba(255,255,255,0.08)]" />
        <div className="absolute inset-0 bg-gradient-to-b from-white/10 via-transparent to-transparent" />
        <div className="relative h-full w-full bg-background">{children}</div>
      </div>
    </div>
  )
}
