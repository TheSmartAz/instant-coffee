import type { CSSProperties } from 'react'

export interface ProductCardProps {
  image?: string
  title: string
  price: number
  originalPrice?: number
  badge?: string
  rating?: number
  href?: string
  className?: string
  style?: CSSProperties
}

const ProductCard = ({
  image,
  title,
  price,
  originalPrice,
  badge,
  rating,
  href,
  className,
  style,
}: ProductCardProps) => {
  const content = (
    <div className="ic-card flex flex-col gap-3 p-4">
      <div className="relative">
        {image ? (
          <img src={image} alt={title} className="h-40 w-full rounded-xl object-cover" />
        ) : (
          <div className="h-40 w-full rounded-xl bg-slate-200" />
        )}
        {badge && (
          <span className="absolute left-3 top-3 rounded-full bg-slate-900 px-3 py-1 text-xs text-white">
            {badge}
          </span>
        )}
      </div>
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-semibold">{title}</h3>
        <div className="flex items-center gap-2 text-sm">
          <span className="font-semibold text-slate-900">${price.toFixed(2)}</span>
          {originalPrice && (
            <span className="text-xs text-slate-400 line-through">${originalPrice.toFixed(2)}</span>
          )}
          {rating != null && (
            <span className="ml-auto text-xs text-slate-500">* {rating.toFixed(1)}</span>
          )}
        </div>
      </div>
    </div>
  )

  if (href) {
    return (
      <a href={href} className={className} style={style}>
        {content}
      </a>
    )
  }

  return (
    <div className={className} style={style}>
      {content}
    </div>
  )
}

export default ProductCard
