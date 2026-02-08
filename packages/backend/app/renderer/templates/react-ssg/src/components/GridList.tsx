import type { CSSProperties } from 'react'

export interface GridListItem {
  title: string
  subtitle?: string
  image?: string
  href?: string
}

export interface GridListProps {
  title?: string
  items?: GridListItem[]
  columns?: number
  className?: string
  style?: CSSProperties
}

const GridList = ({ title, items = [], columns = 2, className, style }: GridListProps) => {
  if (items.length === 0) return null
  const gridClass = columns === 3 ? 'grid-cols-3' : columns === 1 ? 'grid-cols-1' : 'grid-cols-2'

  return (
    <div className={['ic-card flex flex-col gap-3 p-4', className].filter(Boolean).join(' ')} style={style}>
      {title && <h3 className="text-sm font-semibold">{title}</h3>}
      <div className={`grid ${gridClass} gap-3`}>
        {items.map((item) => {
          const card = (
            <div className="flex flex-col gap-2 rounded-xl bg-slate-50 p-3">
              {item.image ? (
                <img src={item.image} alt={item.title} className="h-20 w-full rounded-lg object-cover" />
              ) : (
                <div className="h-20 w-full rounded-lg bg-slate-200" />
              )}
              <div>
                <p className="text-xs font-semibold">{item.title}</p>
                {item.subtitle && <p className="text-[10px] text-slate-500">{item.subtitle}</p>}
              </div>
            </div>
          )

          return item.href ? (
            <a key={item.title} href={item.href}>
              {card}
            </a>
          ) : (
            <div key={item.title}>{card}</div>
          )
        })}
      </div>
    </div>
  )
}

export default GridList
