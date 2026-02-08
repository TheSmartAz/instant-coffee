import type { CSSProperties, FormEvent } from 'react'

export interface FormField {
  name: string
  label: string
  type: 'text' | 'email' | 'number' | 'textarea' | 'select' | 'checkbox'
  placeholder?: string
  required?: boolean
  options?: Array<{ label: string; value: string }>
}

export interface BasicFormProps {
  title?: string
  description?: string
  fields?: FormField[]
  submitLabel?: string
  onSubmit?: (event: FormEvent<HTMLFormElement>) => void
  className?: string
  style?: CSSProperties
}

const BasicForm = ({
  title,
  description,
  fields = [],
  submitLabel = 'Submit',
  onSubmit,
  className,
  style,
}: BasicFormProps) => {
  return (
    <form
      className={['ic-card flex flex-col gap-4 p-4', className].filter(Boolean).join(' ')}
      style={style}
      onSubmit={onSubmit}
    >
      {(title || description) && (
        <div>
          {title && <h3 className="text-sm font-semibold">{title}</h3>}
          {description && <p className="text-xs text-slate-500">{description}</p>}
        </div>
      )}
      <div className="flex flex-col gap-3">
        {fields.map((field) => (
          <label key={field.name} className="flex flex-col gap-2 text-xs text-slate-600">
            {field.label}
            {field.type === 'textarea' ? (
              <textarea
                name={field.name}
                placeholder={field.placeholder}
                required={field.required}
                className="min-h-[90px] rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
              />
            ) : field.type === 'select' ? (
              <select
                name={field.name}
                required={field.required}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
              >
                {field.options?.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ) : field.type === 'checkbox' ? (
              <input type="checkbox" name={field.name} className="h-4 w-4" />
            ) : (
              <input
                type={field.type}
                name={field.name}
                placeholder={field.placeholder}
                required={field.required}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
              />
            )}
          </label>
        ))}
      </div>
      <button
        type="submit"
        className="rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white"
      >
        {submitLabel}
      </button>
    </form>
  )
}

export default BasicForm
