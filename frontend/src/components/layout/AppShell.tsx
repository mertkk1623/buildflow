import { useEffect, useState, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { fetchHealth } from '../../lib/api'
import { STEPS, type StepKey } from '../../lib/steps'
import { cn } from '../../lib/ui'
import { Badge } from '../ui/Status'
import { IconCheck } from '../ui/icons'

/* --------------------------------------------------------------------------
 * StepRail — dikey (sidebar) veya yatay (tablet) adım rayı
 * -------------------------------------------------------------------------- */

export function StepRail({
  orientation = 'vertical',
  current,
}: {
  orientation?: 'vertical' | 'horizontal'
  current: StepKey
}) {
  const currentIndex = STEPS.findIndex((step) => step.key === current)

  if (orientation === 'horizontal') {
    return (
      <nav aria-label="İş akışı adımları" className="overflow-x-auto">
        <ol className="flex min-w-max items-center gap-1">
          {STEPS.map((step, index) => {
            const state =
              index < currentIndex
                ? 'done'
                : index === currentIndex
                  ? 'current'
                  : 'todo'
            return (
              <li key={step.key} className="flex items-center gap-1">
                <Link
                  to={step.path}
                  aria-current={state === 'current' ? 'step' : undefined}
                  className={cn(
                    'inline-flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm whitespace-nowrap',
                    state === 'current'
                      ? 'bg-white font-semibold text-steel-900 ring-1 ring-steel-200'
                      : 'text-steel-500 hover:text-steel-800',
                  )}
                >
                  <span
                    className={cn(
                      'tabular font-mono text-xs',
                      state === 'todo' && 'text-steel-500',
                    )}
                  >
                    {step.no}
                  </span>
                  {step.label}
                  {state === 'done' && (
                    <IconCheck className="size-3.5 text-success-fg" />
                  )}
                </Link>
                {index < STEPS.length - 1 && (
                  <span aria-hidden className="h-px w-4 bg-steel-200" />
                )}
              </li>
            )
          })}
        </ol>
      </nav>
    )
  }

  return (
    <nav aria-label="İş akışı adımları">
      <ol className="space-y-0.5">
        {STEPS.map((step, index) => {
          const state =
            index < currentIndex
              ? 'done'
              : index === currentIndex
                ? 'current'
                : 'todo'
          return (
            <li key={step.key}>
              <Link
                to={step.path}
                aria-current={state === 'current' ? 'step' : undefined}
                className={cn(
                  'group flex items-start gap-3 rounded-md px-2.5 py-2 transition-colors duration-[120ms]',
                  state === 'current'
                    ? 'bg-white shadow-xs ring-1 ring-steel-200'
                    : 'hover:bg-steel-100/70',
                )}
              >
                <span
                  className={cn(
                    'tabular mt-px font-mono text-xs leading-5',
                    state === 'current'
                      ? 'text-copper-600'
                      : state === 'done'
                        ? 'text-success-fg'
                        : 'text-steel-500',
                  )}
                >
                  {state === 'done' ? (
                    <IconCheck className="size-3.5" />
                  ) : (
                    step.no
                  )}
                </span>
                <span className="min-w-0">
                  <span
                    className={cn(
                      'block text-sm leading-5',
                      state === 'current'
                        ? 'font-semibold text-steel-900'
                        : 'font-medium text-steel-600 group-hover:text-steel-800',
                    )}
                  >
                    {step.label}
                  </span>
                  <span className="block text-xs text-steel-500">
                    {step.hint}
                  </span>
                </span>
              </Link>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

/* --------------------------------------------------------------------------
 * PageHeader — başlık + açıklama + sağ eylemler
 * -------------------------------------------------------------------------- */

export function PageHeader({
  stepNo,
  title,
  description,
  actions,
  badge,
}: {
  stepNo: string
  title: string
  description?: ReactNode
  actions?: ReactNode
  badge?: ReactNode
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 pb-5">
      <div className="min-w-0 max-w-2xl">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-label tracking-[0.08em] text-copper-600 uppercase">
            Adım {stepNo}
          </p>
          {badge}
        </div>
        <h1 className="mt-1.5 text-h1 text-steel-900">{title}</h1>
        {description && (
          <div className="mt-1.5 text-body text-steel-500">{description}</div>
        )}
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-2">{actions}</div>
      )}
    </header>
  )
}

/* --------------------------------------------------------------------------
 * ActionBar — adım sonu eylem çubuğu
 * -------------------------------------------------------------------------- */

export function ActionBar({
  children,
  hint,
}: {
  children: ReactNode
  hint?: ReactNode
}) {
  return (
    <div className="sticky bottom-0 z-10 -mx-4 mt-6 border-t border-steel-200 bg-steel-25/95 px-4 py-3 backdrop-blur-sm sm:-mx-6 sm:px-6">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 text-sm text-steel-500">{hint}</div>
        <div className="flex flex-wrap items-center gap-2">{children}</div>
      </div>
    </div>
  )
}

/* --------------------------------------------------------------------------
 * AppShell — kenar çubuğu + üst çubuk + içerik
 * -------------------------------------------------------------------------- */

export function AppShell({
  current,
  children,
}: {
  current: StepKey
  children: ReactNode
}) {
  const location = useLocation()

  return (
    <div className="min-h-dvh bg-steel-25">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-ink focus:px-3 focus:py-2 focus:text-sm focus:text-white"
      >
        İçeriğe geç
      </a>

      <div className="mx-auto flex max-w-[1440px]">
        {/* Masaüstü kenar çubuğu */}
        <aside className="sticky top-0 hidden h-dvh w-62 shrink-0 flex-col border-r border-steel-200 bg-steel-50 px-3 py-4 lg:flex">
          <Link to="/" className="mb-6 flex items-center gap-2 px-2.5">
            <BrandMark />
            <span className="text-body font-semibold tracking-tight text-steel-900">
              BuildFlow AI
            </span>
          </Link>

          <StepRail current={current} />

          <div className="mt-auto space-y-3 px-1 pt-6">
            <Badge tone="neutral">Hesaplama sunucuda</Badge>
            <p className="text-xs leading-4 text-steel-500">
              Nihai miktar, fire ve ağırlık değerleri backend'de üretilir.
            </p>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          {/* Üst çubuk */}
          <div className="sticky top-0 z-20 border-b border-steel-200 bg-steel-25/90 backdrop-blur-sm">
            <div className="flex items-center justify-between gap-3 px-4 py-2.5 sm:px-6">
              <div className="flex min-w-0 items-center gap-2">
                <Link to="/" className="flex items-center gap-2 lg:hidden">
                  <BrandMark />
                  <span className="text-sm font-semibold text-steel-900">
                    BuildFlow AI
                  </span>
                </Link>
                <span className="hidden font-mono text-xs text-steel-500 lg:inline">
                  {location.pathname}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <HealthDot />
              </div>
            </div>

            {/* Tablet / mobil adım rayı */}
            <div className="border-t border-steel-200 px-2 py-1.5 lg:hidden">
              <StepRail current={current} orientation="horizontal" />
            </div>
          </div>

          <main
            id="main"
            className="mx-auto w-full max-w-6xl flex-1 px-4 pt-6 pb-4 sm:px-6"
          >
            {children}
          </main>
        </div>
      </div>
    </div>
  )
}

function BrandMark() {
  return (
    <span
      aria-hidden
      className="grid size-7 shrink-0 place-items-center rounded-sm bg-ink text-[11px] font-semibold text-white"
    >
      BF
    </span>
  )
}

type HealthState = 'checking' | 'ok' | 'down'

/**
 * API sağlık göstergesi — `/api/health`.
 *
 * Yalnızca bilgi amaçlıdır: bağlantı yoksa bile ekranlar açılır, gerçek
 * işlemlerde hata kullanıcıya gösterilir.
 */
function HealthDot() {
  const [state, setState] = useState<HealthState>('checking')
  const [environment, setEnvironment] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    fetchHealth(controller.signal)
      .then((health) => {
        setState('ok')
        setEnvironment(health.environment)
      })
      .catch(() => {
        if (!controller.signal.aborted) setState('down')
      })

    return () => controller.abort()
  }, [])

  const meta = {
    checking: {
      dot: 'bg-steel-300',
      label: 'API kontrol ediliyor',
      title: 'Yerel backend sağlık kontrolü — /api/health',
    },
    ok: {
      dot: 'bg-success-fg',
      label: 'API bağlı',
      title: `Backend erişilebilir${environment ? ` · ${environment}` : ''}`,
    },
    down: {
      dot: 'bg-danger-fg',
      label: 'API kapalı',
      title:
        'Backend erişilemiyor. Sunucuyu başlatın: uvicorn app.main:app --reload',
    },
  }[state]

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border border-steel-200 bg-white px-2.5 py-1 text-xs text-steel-500"
      title={meta.title}
    >
      <span className={cn('size-1.5 rounded-full', meta.dot)} aria-hidden />
      {meta.label}
    </span>
  )
}
