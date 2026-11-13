import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { cn } from '../../lib/ui'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  size?: Size
  /** Sol tarafta ikon. */
  icon?: ReactNode
  /** Sağ tarafta ikon. */
  trailingIcon?: ReactNode
}

const variants: Record<Variant, string> = {
  primary:
    'bg-ink text-white border border-ink hover:bg-steel-800 active:bg-steel-900',
  secondary:
    'bg-white text-steel-800 border border-steel-300 hover:bg-steel-50 active:bg-steel-100',
  ghost:
    'bg-transparent text-steel-700 border border-transparent hover:bg-steel-100 active:bg-steel-200',
  danger:
    'bg-white text-danger-fg border border-danger-br hover:bg-danger-bg active:bg-danger-bg',
}

const sizes: Record<Size, string> = {
  sm: 'h-9 px-3 text-sm gap-1.5',
  md: 'h-10 px-4 text-body gap-2',
}

export function Button({
  variant = 'secondary',
  size = 'md',
  icon,
  trailingIcon,
  className,
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex items-center justify-center rounded-md font-medium transition-colors duration-[120ms] ease-snap',
        'disabled:cursor-not-allowed disabled:opacity-45',
        variants[variant],
        sizes[size],
        className,
      )}
      {...rest}
    >
      {icon}
      {children}
      {trailingIcon}
    </button>
  )
}
