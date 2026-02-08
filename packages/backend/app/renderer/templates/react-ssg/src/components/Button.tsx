import type { CSSProperties, MouseEvent } from 'react'

export interface ButtonProps {
  label: string
  href?: string
  variant?: 'primary' | 'secondary'
  fullWidth?: boolean
  size?: 'sm' | 'md' | 'lg'
  onClick?: (event: MouseEvent<HTMLButtonElement | HTMLAnchorElement>) => void
  className?: string
  style?: CSSProperties
}

const Button = ({
  label,
  href,
  variant = 'primary',
  fullWidth,
  size = 'md',
  onClick,
  className,
  style,
}: ButtonProps) => {
  const base =
    variant === 'secondary'
      ? 'bg-slate-100 text-slate-700'
      : 'bg-slate-900 text-white'
  const sizeClass =
    size === 'sm' ? 'px-3 py-2 text-xs' : size === 'lg' ? 'px-5 py-3 text-sm' : 'px-4 py-2 text-xs'
  const widthClass = fullWidth ? 'w-full' : 'inline-flex'

  const classes = ['rounded-full font-semibold', base, sizeClass, widthClass, className]
    .filter(Boolean)
    .join(' ')

  if (href) {
    return (
      <a href={href} className={classes} style={style} onClick={onClick}>
        {label}
      </a>
    )
  }

  return (
    <button type="button" className={classes} style={style} onClick={onClick}>
      {label}
    </button>
  )
}

export default Button
