import type { ReactNode } from 'react'

import { cn } from '../../lib/ui'

/* --------------------------------------------------------------------------
 * Ton tanımı: tek kaynak. Badge, Alert ve durum şeridi aynı paleti kullanır.
 * -------------------------------------------------------------------------- */

export type Tone =
  | 'neutral'
  | 'copper'
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'

const toneBadge: Record<Tone, string> = {
  neutral: 'bg-steel-100 text-steel-700 ring-steel-200',
  copper: 'bg-copper-50 text-copper-700 ring-copper-200',
  success: 'bg-success-bg text-success-fg ring-success-br',
  warning: 'bg-warning-bg text-warning-fg ring-warning-br',
  danger: 'bg-danger-bg text-danger-fg ring-danger-br',
  info: 'bg-info-bg text-info-fg ring-info-br',
}

const toneBar: Record<Tone, string> = {
  neutral: 'bg-steel-300',
  copper: 'bg-copper-500',
  success: 'bg-success-fg',
  warning: 'bg-warning-fg',
  danger: 'bg-danger-fg',
  info: 'bg-info-fg',
}

const toneAlert: Record<Tone, string> = {
  neutral: 'bg-steel-50 border-steel-200 text-steel-700',
  copper: 'bg-copper-50 border-copper-200 text-copper-700',
  success: 'bg-success-bg border-success-br text-success-fg',
  warning: 'bg-warning-bg border-warning-br text-warning-fg',
  danger: 'bg-danger-bg border-danger-br text-danger-fg',
  info: 'bg-info-bg border-info-br text-info-fg',
}

/* --------------------------------------------------------------------------
 * Badge — durum etiketi
 * -------------------------------------------------------------------------- */

export function Badge({
  tone = 'neutral',
  children,
  className,
  mono = false,
}: {
  tone?: Tone
  children: ReactNode
  className?: string
  mono?: boolean
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset whitespace-nowrap',
        mono && 'font-mono tabular',
        toneBadge[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

/* --------------------------------------------------------------------------
 * StatusBar — tablo satırının solundaki 3px durum şeridi
 * -------------------------------------------------------------------------- */

export function StatusBar({ tone = 'neutral' }: { tone?: Tone }) {
  return (
    <span
      aria-hidden
      className={cn(
        'absolute inset-y-0 left-0 w-[3px] rounded-l-sm',
        toneBar[tone],
      )}
    />
  )
}

/* --------------------------------------------------------------------------
 * Alert — bildirim kutusu
 * -------------------------------------------------------------------------- */

export function Alert({
  tone = 'neutral',
  title,
  children,
  icon,
  action,
  className,
}: {
  tone?: Tone
  title?: ReactNode
  children?: ReactNode
  icon?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-lg border px-4 py-3',
        toneAlert[tone],
        className,
      )}
    >
      {icon && <span className="mt-0.5">{icon}</span>}
      <div className="min-w-0 flex-1">
        {title && <p className="text-body font-semibold">{title}</p>}
        {children && (
          <div className={cn('text-sm', Boolean(title) && 'mt-1', 'opacity-90')}>
            {children}
          </div>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

/* --------------------------------------------------------------------------
 * DemoNotice — prototip sınırını her ekranda hatırlatan kalıcı rozet
 * -------------------------------------------------------------------------- */

export function DemoNotice({
  compact = false,
  className,
}: {
  compact?: boolean
  className?: string
}) {
  if (compact) {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1.5 rounded-full bg-steel-100 px-2.5 py-0.5 text-label font-semibold tracking-[0.08em] text-steel-600 uppercase ring-1 ring-inset ring-steel-200',
          className,
        )}
      >
        Demo verisi
      </span>
    )
  }

  return (
    <div
      className={cn(
        'flex items-center gap-2 rounded-md border border-dashed border-steel-300 bg-steel-50 px-3 py-2 text-sm text-steel-600',
        className,
      )}
    >
      <span className="size-1.5 rounded-full bg-copper-500" aria-hidden />
      <span>
        <span className="font-semibold text-steel-700">Sabit demo verisi.</span>{' '}
        Bu ekran gerçek Excel işleme, hesaplama veya AI çağrısı yapmaz.
      </span>
    </div>
  )
}

/* --------------------------------------------------------------------------
 * EmptyState
 * -------------------------------------------------------------------------- */

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string
  description?: string
  action?: ReactNode
  icon?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      {icon && <span className="text-steel-400">{icon}</span>}
      <p className="text-body font-semibold text-steel-800">{title}</p>
      {description && (
        <p className="max-w-sm text-sm text-steel-500">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

/* --------------------------------------------------------------------------
 * Skeleton — yalnızca bileşen galerisinde / gerçek yükleme durumlarında
 * -------------------------------------------------------------------------- */

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('animate-pulse rounded-sm bg-steel-100', className)}
      aria-hidden
    />
  )
}
