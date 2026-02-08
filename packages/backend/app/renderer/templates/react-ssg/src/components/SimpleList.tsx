import type { CSSProperties } from 'react'

export type SimpleListItem =
  | string
  | {
      title: string
      subtitle?: string
      meta?: string
      href?: string
      icon?: string
    }

export interface SimpleListProps {
  title?: string
  items?: SimpleListItem[]
  className?: string
  style?: CSSProperties
}

const SimpleList = ({ title, items = [], className, style }: SimpleListProps) => {
  if (items.length === 0) return null

  return (
    <div className={['ic-card flex flex-col gap-3 p-4', className].filter(Boolean).join(' ')} style={style}>
      {title && <h3 className="text-sm font-semibold">{title}</h3>}
      <div className="flex flex-col gap-3">
        {items.map((item, index) => {
          const data = typeof item === 'string' ? { title: item } : item
          const content = (
            <div className="flex items-center gap-3">
              <span className="text-lg">{data.icon || '*'}</span>
              <div className="flex-1">
                <p className="text-sm font-medium">{data.title}</p>
                {data.subtitle && <p className="text-xs text-slate-500">{data.subtitle}</p>}
              </div>
              {data.meta && <span className="text-xs text-slate-400">{data.meta}</span>}
            </div>
          )

          if (data.href) {
            return (
              <a key={`${data.title}-${index}`} href={data.href} className="rounded-xl bg-slate-50 p-3">
                {content}
              </a>
            )
          }

          return (
            <div key={`${data.title}-${index}`} className="rounded-xl bg-slate-50 p-3">
              {content}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default SimpleList
