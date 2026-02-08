import type { CSSProperties } from 'react'

export interface CartSummaryProps {
  itemCount?: number
  subtotal?: number
  shipping?: number
  tax?: number
  total?: number
  ctaLabel?: string
  ctaHref?: string
  className?: string
  style?: CSSProperties
}

const CartSummary = ({
  itemCount = 0,
  subtotal = 0,
  shipping = 0,
  tax = 0,
  total = subtotal + shipping + tax,
  ctaLabel,
  ctaHref,
  className,
  style,
}: CartSummaryProps) => {
  return (
    <div className={['ic-card flex flex-col gap-3 p-4', className].filter(Boolean).join(' ')} style={style}>
      <h3 className="text-sm font-semibold">Order summary</h3>
      <div className="flex flex-col gap-2 text-xs text-slate-600">
        <div className="flex items-center justify-between">
          <span>Items</span>
          <span>{itemCount}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>Subtotal</span>
          <span>${subtotal.toFixed(2)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>Shipping</span>
          <span>${shipping.toFixed(2)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>Tax</span>
          <span>${tax.toFixed(2)}</span>
        </div>
      </div>
      <div className="ic-divider" />
      <div className="flex items-center justify-between text-sm font-semibold">
        <span>Total</span>
        <span>${total.toFixed(2)}</span>
      </div>
      {ctaLabel && (
        <a
          href={ctaHref || '#'}
          className="rounded-full bg-brand-500 px-4 py-2 text-center text-xs font-semibold text-white"
        >
          {ctaLabel}
        </a>
      )}
    </div>
  )
}

export default CartSummary
