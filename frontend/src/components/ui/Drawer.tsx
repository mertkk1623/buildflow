import { useEffect, useId, useRef, type ReactNode } from 'react'

import { cn } from '../../lib/ui'
import { IconClose } from './icons'

/**
 * Sağdan açılan panel. Review ekranındaki eşleşme detayı için kullanılır.
 *
 * Erişilebilirlik: `role="dialog"`, `aria-modal`, Escape ile kapanır, açıkken
 * gövde kaydırması kilitlenir, ilk odağa alınır.
 */
export function Drawer({
  open,
  title,
  subtitle,
  onClose,
  children,
  footer,
}: {
  open: boolean
  title: ReactNode
  subtitle?: ReactNode
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
}) {
  const panelRef = useRef<HTMLDivElement>(null)
  const titleId = useId()

  useEffect(() => {
    if (!open) return

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    panelRef.current?.focus()

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div
        className="absolute inset-0 bg-ink/25"
        onClick={onClose}
        aria-hidden
      />

      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={cn(
          'relative flex h-full w-full flex-col bg-white shadow-lg outline-none',
          'transition-transform duration-[220ms] ease-snap',
          'sm:max-w-[480px]',
        )}
      >
        <header className="flex items-start justify-between gap-4 border-b border-steel-200 px-5 py-4">
          <div className="min-w-0">
            <h2 id={titleId} className="text-h3 text-steel-900">
              {title}
            </h2>
            {subtitle && (
              <div className="mt-1 text-sm text-steel-500">{subtitle}</div>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid size-9 place-items-center rounded-md text-steel-500 transition-colors hover:bg-steel-100 hover:text-steel-800"
            aria-label="Paneli kapat"
          >
            <IconClose />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>

        {footer && (
          <footer className="border-t border-steel-200 bg-steel-25 px-5 py-3">
            {footer}
          </footer>
        )}
      </div>
    </div>
  )
}
