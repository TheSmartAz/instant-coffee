import type { CSSProperties } from 'react'

export interface ToastProps {
  message: string
  type?: 'info' | 'success' | 'warning' | 'error'
  open?: boolean
  className?: string
  style?: CSSProperties
}

const TOAST_STYLES: Record<string, string> = {
  info: 'bg-slate-900 text-white',
  success: 'bg-emerald-500 text-white',
  warning: 'bg-amber-500 text-white',
  error: 'bg-rose-500 text-white',
}

const Toast = ({ message, type = 'info', open = true, className, style }: ToastProps) => {
  if (!open) return null

  return (
    <div
      className={[
        'ic-card fixed bottom-20 left-1/2 z-50 flex w-[calc(100%-2rem)] -translate-x-1/2 items-center justify-between px-4 py-3 text-xs',
        TOAST_STYLES[type],
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      style={style}
    >
      <span>{message}</span>
      <span className="text-white/80">Tap to dismiss</span>
    </div>
  )
}

export default Toast
