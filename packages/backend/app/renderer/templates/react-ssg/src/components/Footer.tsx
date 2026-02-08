import type { CSSProperties } from 'react'

export interface FooterLink {
  label: string
  href: string
}

export interface FooterProps {
  links?: FooterLink[]
  copyright?: string
  className?: string
  style?: CSSProperties
}

const Footer = ({ links = [], copyright, className, style }: FooterProps) => {
  return (
    <footer className={['ic-card flex flex-col gap-3 p-4', className].filter(Boolean).join(' ')} style={style}>
      {links.length > 0 && (
        <div className="flex flex-wrap gap-3 text-xs text-slate-500">
          {links.map((link) => (
            <a key={link.href} href={link.href} className="hover:text-slate-700">
              {link.label}
            </a>
          ))}
        </div>
      )}
      <p className="text-[10px] text-slate-400">{copyright || '(c) 2026 Instant Coffee'}</p>
    </footer>
  )
}

export default Footer
