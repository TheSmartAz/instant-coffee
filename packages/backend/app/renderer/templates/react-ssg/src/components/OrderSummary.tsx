import type { CSSProperties } from 'react'

export interface OrderItem {
  title: string
  quantity?: number
  price?: number
}

export interface OrderSummaryProps {
  orderId?: string
  status?: string
  date?: string
  items?: OrderItem[]
  total?: number
  className?: string
  style?: CSSProperties
}

const OrderSummary = ({
  orderId,
  status,
  date,
  items = [],
  total = 0,
  className,
  style,
}: OrderSummaryProps) => {
  return (
    <div className={['ic-card flex flex-col gap-3 p-4', className].filter(Boolean).join(' ')} style={style}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-slate-500">Order</p>
          <h3 className="text-sm font-semibold">{orderId || 'Order summary'}</h3>
          {date && <p className="text-xs text-slate-400">{date}</p>}
        </div>
        {status && <span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] uppercase">{status}</span>}
      </div>
      <div className="flex flex-col gap-2 text-xs text-slate-600">
        {items.map((item) => (
          <div key={item.title} className="flex items-center justify-between">
            <span>
              {item.title} {item.quantity ? `x${item.quantity}` : ''}
            </span>
            {item.price != null && <span>${item.price.toFixed(2)}</span>}
          </div>
        ))}
      </div>
      <div className="ic-divider" />
      <div className="flex items-center justify-between text-sm font-semibold">
        <span>Total</span>
        <span>${total.toFixed(2)}</span>
      </div>
    </div>
  )
}

export default OrderSummary
