import type { CSSProperties } from 'react'

export interface ConfirmModalProps {
  open?: boolean
  title?: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  onConfirm?: () => void
  onCancel?: () => void
  className?: string
  style?: CSSProperties
}

const ConfirmModal = ({
  open,
  title = 'Confirm action',
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
  className,
  style,
}: ConfirmModalProps) => {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className={['ic-card w-[90%] max-w-sm p-5', className].filter(Boolean).join(' ')} style={style}>
        <h3 className="text-sm font-semibold">{title}</h3>
        {description && <p className="mt-2 text-xs text-slate-500">{description}</p>}
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600"
            onClick={onCancel}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className="rounded-full bg-slate-900 px-3 py-1 text-xs text-white"
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ConfirmModal
