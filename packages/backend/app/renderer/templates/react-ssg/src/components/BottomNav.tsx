import type { CSSProperties } from 'react'

export interface BottomNavItem {
  label: string
  href: string
  active?: boolean
  icon?: string
}

export interface BottomNavProps {
  items?: BottomNavItem[]
  className?: string
  style?: CSSProperties
}

const BottomNav = ({ items = [], className, style }: BottomNavProps) => {
  if (items.length === 0) return null

  return (
    <nav
      className={['ic-card fixed bottom-4 left-1/2 z-50 w-[calc(100%-2rem)] -translate-x-1/2', className]
        .filter(Boolean)
        .join(' ')}
      style={style}
    >
      <div className="flex items-center justify-around px-4 py-3">
        {items.map((item) => (
          <a
            key={item.href}
            href={item.href}
            className={
              item.active
                ? 'flex flex-col items-center gap-1 text-xs font-semibold text-brand-700'
                : 'flex flex-col items-center gap-1 text-xs text-slate-500'
            }
          >
            <span className="text-base">{item.icon || '*'}</span>
            {item.label}
          </a>
        ))}
      </div>
    </nav>
  )
}

export default BottomNav
