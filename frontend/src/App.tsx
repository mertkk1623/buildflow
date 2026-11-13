import { useEffect, useState } from 'react'

import { fetchHealth } from './lib/api'

type ConnectionState =
  | { status: 'checking' }
  | { status: 'online'; environment: string }
  | { status: 'offline'; message: string }

const stateLabel: Record<ConnectionState['status'], string> = {
  checking: 'Kontrol ediliyor',
  online: 'Bağlı',
  offline: 'Bağlantı yok',
}

const stateStyle: Record<ConnectionState['status'], string> = {
  checking: 'bg-slate-100 text-slate-600 ring-slate-200',
  online: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  offline: 'bg-amber-50 text-amber-800 ring-amber-200',
}

export default function App() {
  const [connection, setConnection] = useState<ConnectionState>({
    status: 'checking',
  })

  useEffect(() => {
    const controller = new AbortController()

    fetchHealth(controller.signal)
      .then((health) =>
        setConnection({ status: 'online', environment: health.environment }),
      )
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setConnection({
          status: 'offline',
          message:
            error instanceof Error ? error.message : 'Bilinmeyen bir hata oluştu',
        })
      })

    return () => controller.abort()
  }, [])

  return (
    <main className="min-h-dvh bg-slate-50 px-6 py-16 text-slate-900">
      <div className="mx-auto max-w-2xl">
        <p className="text-xs font-medium tracking-[0.18em] text-slate-500 uppercase">
          Faz 0 · Proje iskeleti
        </p>

        <h1 className="mt-3 text-3xl font-semibold tracking-tight">
          BuildFlow AI
        </h1>

        <p className="mt-4 text-base leading-relaxed text-slate-600">
          İnşaat metraj (BOQ) dosyalarını incelenmiş ve satın almaya hazır
          malzeme listesine dönüştüren uygulama. Bu ekran yalnızca geliştirme
          ortamının çalıştığını doğrular.
        </p>

        <section className="mt-10 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                Backend durumu
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                FastAPI · <code className="text-slate-700">GET /api/health</code>
              </p>
            </div>

            <span
              className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset ${stateStyle[connection.status]}`}
            >
              {stateLabel[connection.status]}
            </span>
          </div>

          {connection.status === 'online' && (
            <p className="mt-4 border-t border-slate-100 pt-4 text-sm text-slate-600">
              Ortam: <span className="font-medium">{connection.environment}</span>
            </p>
          )}

          {connection.status === 'offline' && (
            <p className="mt-4 border-t border-slate-100 pt-4 text-sm text-amber-800">
              {connection.message}. Backend'i{' '}
              <code className="text-slate-800">
                uvicorn app.main:app --reload
              </code>{' '}
              ile başlatın.
            </p>
          )}
        </section>

        <p className="mt-8 text-sm text-slate-500">
          Ürün ekranları, hesaplama motoru ve AI entegrasyonu sonraki fazlarda
          eklenecektir.
        </p>
      </div>
    </main>
  )
}
