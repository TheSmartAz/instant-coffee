import type { CSSProperties } from 'react'

export interface CheckoutFormProps {
  title?: string
  sections?: Array<{
    title: string
    fields: Array<{ name: string; label: string; placeholder?: string }>
  }>
  submitLabel?: string
  className?: string
  style?: CSSProperties
}

const CheckoutForm = ({
  title = 'Checkout',
  sections = [],
  submitLabel = 'Place order',
  className,
  style,
}: CheckoutFormProps) => {
  return (
    <div className={['ic-card flex flex-col gap-4 p-4', className].filter(Boolean).join(' ')} style={style}>
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        <p className="text-xs text-slate-500">Secure checkout for your order</p>
      </div>
      <div className="flex flex-col gap-4">
        {sections.map((section) => (
          <div key={section.title} className="flex flex-col gap-3">
            <p className="text-xs font-semibold uppercase text-slate-500">{section.title}</p>
            <div className="grid grid-cols-1 gap-3">
              {section.fields.map((field) => (
                <label key={field.name} className="flex flex-col gap-2 text-xs text-slate-600">
                  {field.label}
                  <input
                    name={field.name}
                    placeholder={field.placeholder}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                  />
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>
      <button className="rounded-full bg-brand-500 px-4 py-2 text-xs font-semibold text-white">
        {submitLabel}
      </button>
    </div>
  )
}

export default CheckoutForm
