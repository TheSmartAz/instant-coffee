import type { CSSProperties } from 'react'
import type { AssetRef } from '../types'

export interface NavLink {
  label: string
  href: string
  active?: boolean
}

export interface NavProps {
  logo?: AssetRef | string
  brand?: string
  links?: NavLink[]
  showSearch?: boolean
  showCart?: boolean
  cartCount?: number
  className?: string
  style?: CSSProperties
}

const Nav = ({
  logo,
  brand = 'Instant Coffee',
  links = [],
  showSearch,
  showCart,
  cartCount,
  className,
  style,
}: NavProps) => {
  const logoUrl = typeof logo === 'string' ? logo : logo?.url

  return (
    <nav className={['ic-card flex flex-col gap-3 p-4', className].filter(Boolean).join(' ')} style={style}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {logoUrl ? (
            <img src={logoUrl} alt={brand} className="h-9 w-9 rounded-full object-cover" />
          ) : (
            <div className="h-9 w-9 rounded-full bg-slate-200" />
          )}
          <div>
            <p className="text-sm font-semibold">{brand}</p>
            <p className="text-xs text-slate-500">Mobile-first storefront</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {showSearch && (
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-500">Search</span>
          )}
          {showCart && (
            <span className="rounded-full bg-slate-900 px-3 py-1 text-xs text-white">
              Cart {cartCount != null ? `(${cartCount})` : ''}
            </span>
          )}
        </div>
      </div>
      {links.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className={
                link.active
                  ? 'rounded-full bg-brand-500 px-3 py-1 text-xs font-semibold text-white'
                  : 'rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600'
              }
            >
              {link.label}
            </a>
          ))}
        </div>
      )}
    </nav>
  )
}

export default Nav
