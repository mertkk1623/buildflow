import type { ReactNode } from 'react'

import { cn } from '../../lib/ui'

export function Card({
  children,
  className,
  as: Tag = 'section',
}: {
  children: ReactNode
  className?: string
  as?: 'section' | 'div' | 'article'
}) {
  return (
    <Tag
      className={cn(
        'rounded-lg border border-steel-200 bg-white shadow-xs',
        className,
      )}
    >
      {children}
    </Tag>
  )
}

export function CardHeader({
  title,
  description,
  action,
  className,
}: {
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-start justify-between gap-3 border-b border-steel-100 px-5 py-3.5',
        className,
      )}
    >
      <div className="min-w-0">
        <h2 className="text-body font-semibold text-steel-900">{title}</h2>
        {description && (
          <p className="mt-0.5 text-sm text-steel-500">{description}</p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

export function CardBody({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return <div className={cn('px-5 py-4', className)}>{children}</div>
}
