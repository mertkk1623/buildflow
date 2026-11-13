import type { InputHTMLAttributes } from 'react'

import { cn } from '../../lib/ui'
import { IconSearch } from './icons'

export function SearchInput({
  className,
  ...rest
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className={cn('relative', className)}>
      <IconSearch className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-steel-400" />
      <input
        type="search"
        className={cn(
          'h-9 w-full rounded-md border border-steel-300 bg-white pr-3 pl-9 text-sm text-steel-900',
          'placeholder:text-steel-500',
          'transition-colors hover:border-steel-400',
          'focus:border-steel-400 focus:outline-none',
        )}
        {...rest}
      />
    </div>
  )
}

export type SegmentOption<T extends string> = {
  value: T
  label: string
  /** Sayaç: filtre çubuğunda görünen adet. */
  count?: number
  tone?: 'neutral' | 'copper' | 'success' | 'warning' | 'danger'
}

const segmentTone: Record<string, string> = {
  neutral: 'text-steel-700',
  copper: 'text-copper-700',
  success: 'text-success-fg',
  warning: 'text-warning-fg',
  danger: 'text-danger-fg',
}

/** Filtre çubuğu: tek seçimli segment kontrolü. */
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  label,
  className,
}: {
  options: SegmentOption<T>[]
  value: T
  onChange: (value: T) => void
  label: string
  className?: string
}) {
  return (
    <div
      role="tablist"
      aria-label={label}
      className={cn(
        'flex flex-wrap items-center gap-1 rounded-lg border border-steel-200 bg-steel-50 p-1',
        className,
      )}
    >
      {options.map((option) => {
        const active = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(option.value)}
            className={cn(
              'inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-sm font-medium whitespace-nowrap transition-colors duration-[120ms]',
              active
                ? 'bg-white text-steel-900 shadow-xs ring-1 ring-steel-200'
                : 'text-steel-600 hover:text-steel-900',
            )}
          >
            <span className={active ? undefined : segmentTone[option.tone ?? 'neutral']}>
              {option.label}
            </span>
            {option.count !== undefined && (
              <span
                className={cn(
                  'tabular rounded-full px-1.5 py-px text-xs',
                  active ? 'bg-steel-100 text-steel-600' : 'text-steel-500',
                )}
              >
                {option.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

/** Radyo benzeri seçim listesi — drawer içindeki aday seçimi için. */
export function RadioCard({
  checked,
  onChange,
  name,
  children,
  disabled = false,
}: {
  checked: boolean
  onChange: () => void
  name: string
  children: React.ReactNode
  disabled?: boolean
}) {
  return (
    <label
      className={cn(
        'flex cursor-pointer items-start gap-3 rounded-md border p-3 transition-colors duration-[120ms]',
        checked
          ? 'border-copper-500 bg-copper-50/60'
          : 'border-steel-200 bg-white hover:border-steel-300',
        disabled && 'cursor-not-allowed opacity-60',
      )}
    >
      <input
        type="radio"
        name={name}
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        className="mt-0.5 size-4 shrink-0 accent-copper-600"
      />
      <div className="min-w-0 flex-1">{children}</div>
    </label>
  )
}
