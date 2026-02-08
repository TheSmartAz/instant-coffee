import type { CSSProperties } from 'react'

export interface HeroProps {
  title: string
  subtitle?: string
  backgroundImage?: string
  backgroundColor?: string
  cta?: {
    label: string
    href: string
  }
  alignment?: 'left' | 'center' | 'right'
  className?: string
  style?: CSSProperties
}

const Hero = ({
  title,
  subtitle,
  backgroundImage,
  backgroundColor,
  cta,
  alignment = 'left',
  className,
  style,
}: HeroProps) => {
  const alignClass =
    alignment === 'center'
      ? 'items-center text-center'
      : alignment === 'right'
      ? 'items-end text-right'
      : 'items-start text-left'

  return (
    <section
      className={['ic-card overflow-hidden', className].filter(Boolean).join(' ')}
      style={style}
    >
      <div
        className="flex min-h-[220px] flex-col justify-between gap-6 p-6"
        style={{
          backgroundImage: backgroundImage ? `url(${backgroundImage})` : undefined,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundColor: backgroundColor || undefined,
        }}
      >
        <div className={['flex flex-1 flex-col gap-3', alignClass].join(' ')}>
          <p className="text-xs uppercase tracking-[0.25em] text-white/70">Featured</p>
          <h1 className="text-2xl font-semibold text-white drop-shadow">{title}</h1>
          {subtitle && <p className="text-sm text-white/80">{subtitle}</p>}
        </div>
        {cta && (
          <div className={alignClass}>
            <a
              href={cta.href}
              className="inline-flex rounded-full bg-white px-4 py-2 text-xs font-semibold text-slate-900"
            >
              {cta.label}
            </a>
          </div>
        )}
      </div>
    </section>
  )
}

export default Hero
