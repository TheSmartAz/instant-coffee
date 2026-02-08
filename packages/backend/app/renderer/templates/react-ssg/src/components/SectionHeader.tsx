import type { CSSProperties } from 'react'

export interface SectionHeaderProps {
  title: string
  subtitle?: string
  align?: 'left' | 'center' | 'right'
  className?: string
  style?: CSSProperties
}

const SectionHeader = ({ title, subtitle, align = 'left', className, style }: SectionHeaderProps) => {
  const alignClass =
    align === 'center' ? 'text-center items-center' : align === 'right' ? 'text-right items-end' : 'items-start'

  return (
    <div className={['flex flex-col gap-1', alignClass, className].filter(Boolean).join(' ')} style={style}>
      <h2 className="text-lg font-semibold">{title}</h2>
      {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
    </div>
  )
}

export default SectionHeader
