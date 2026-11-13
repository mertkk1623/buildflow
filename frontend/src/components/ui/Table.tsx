import type { ReactNode, ThHTMLAttributes, TdHTMLAttributes } from 'react'

import { cn } from '../../lib/ui'

/**
 * Bilgi yoğun tablo kabuğu.
 * Başlık 40px, gövde satırı 48px; ilk sütun sabit, tablo yatay kaydırılır.
 */
export function TableShell({
  children,
  className,
  minWidth = 720,
}: {
  children: ReactNode
  className?: string
  minWidth?: number
}) {
  return (
    <div className={cn('-mx-px overflow-x-auto', className)}>
      <table
        className="w-full border-collapse text-body"
        style={{ minWidth }}
      >
        {children}
      </table>
    </div>
  )
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead className="border-b border-steel-200 bg-steel-50 text-left">
      {children}
    </thead>
  )
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody className="divide-y divide-steel-100">{children}</tbody>
}

export function TR({
  children,
  className,
  interactive = false,
  onClick,
}: {
  children: ReactNode
  className?: string
  interactive?: boolean
  onClick?: () => void
}) {
  const isInteractive = interactive && Boolean(onClick)

  return (
    <tr
      className={cn(
        'relative align-middle',
        isInteractive &&
          'cursor-pointer transition-colors duration-[120ms] hover:bg-steel-25 focus-within:bg-steel-25',
        className,
      )}
      onClick={onClick}
      onKeyDown={
        isInteractive
          ? (event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                onClick?.()
              }
            }
          : undefined
      }
      tabIndex={isInteractive ? 0 : undefined}
    >
      {children}
    </tr>
  )
}

export function TH({
  children,
  className,
  align = 'left',
  ...rest
}: ThHTMLAttributes<HTMLTableCellElement> & { align?: 'left' | 'right' }) {
  return (
    <th
      scope="col"
      className={cn(
        'h-10 px-3 text-label font-semibold tracking-[0.08em] text-steel-500 uppercase whitespace-nowrap first:pl-5 last:pr-5',
        align === 'right' && 'text-right',
        className,
      )}
      {...rest}
    >
      {children}
    </th>
  )
}

export function TD({
  children,
  className,
  align = 'left',
  ...rest
}: TdHTMLAttributes<HTMLTableCellElement> & { align?: 'left' | 'right' }) {
  return (
    <td
      className={cn(
        'h-12 px-3 text-steel-800 first:pl-5 last:pr-5',
        align === 'right' && 'text-right',
        className,
      )}
      {...rest}
    >
      {children}
    </td>
  )
}

/** Kısa, nötr açıklama satırı: hesaplanmayan sütunlar için "—". */
export function Pending({ label = '—' }: { label?: string }) {
  return (
    <span
      className="font-mono text-xs text-steel-500"
      title="Hesap motoru devreye girdiğinde doldurulacak"
    >
      {label}
    </span>
  )
}
