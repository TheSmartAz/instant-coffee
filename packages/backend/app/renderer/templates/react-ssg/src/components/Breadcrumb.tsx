import type { CSSProperties } from 'react'

export interface BreadcrumbItem {
  label: string
  href?: string
}

export interface BreadcrumbProps {
  items?: BreadcrumbItem[]
  className?: string
  style?: CSSProperties
}

const Breadcrumb = ({ items = [], className, style }: BreadcrumbProps) => {
  if (items.length === 0) return null

  return (
    <nav className={['text-xs text-slate-500', className].filter(Boolean).join(' ')} style={style}>
      <ol className="flex flex-wrap items-center gap-2">
        {items.map((item, index) => (
          <li key={`${item.label}-${index}`} className="flex items-center gap-2">
            {item.href ? (
              <a href={item.href} className="hover:text-slate-700">
                {item.label}
              </a>
            ) : (
              <span className="text-slate-700">{item.label}</span>
            )}
            {index < items.length - 1 && <span className="text-slate-300">/</span>}
          </li>
        ))}
      </ol>
    </nav>
  )
}

export default Breadcrumb
