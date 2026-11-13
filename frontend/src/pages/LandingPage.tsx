import { Link } from 'react-router-dom'

import { Badge } from '../components/ui/Status'
import {
  IconAlert,
  IconArrowRight,
  IconCheck,
  IconInfo,
  IconLayers,
} from '../components/ui/icons'
import { useWorkflow } from '../state/WorkflowContext'

/**
 * Landing — ürün girişi.
 *
 * Akışın gerçek durumunu gösterir: analiz edilmiş dosya varsa devam bağlantısı
 * doğrudan o adıma gider. Sabit demo seti yoktur.
 */
export default function LandingPage() {
  const { analyzeView, counts, total, eligibleCount, calculation } = useWorkflow()

  const nextStep = calculation
    ? { to: '/results', label: 'Sonuçları gör' }
    : analyzeView
      ? { to: '/review', label: 'Eşleşmeleri incele' }
      : { to: '/upload', label: 'Metraj yükle' }

  return (
    <div className="min-h-dvh bg-steel-25">
      <header className="border-b border-steel-200">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2.5">
            <span
              aria-hidden
              className="grid size-7 place-items-center rounded-sm bg-ink text-[11px] font-semibold text-white"
            >
              BF
            </span>
            <span className="text-body font-semibold tracking-tight text-steel-900">
              BuildFlow AI
            </span>
          </Link>

          <nav className="flex items-center gap-1">
            <a
              href="#akis"
              className="hidden rounded-md px-3 py-1.5 text-sm text-steel-600 transition-colors hover:bg-steel-100 hover:text-steel-900 sm:inline-flex"
            >
              Akış
            </a>
            <a
              href="#kapsam"
              className="hidden rounded-md px-3 py-1.5 text-sm text-steel-600 transition-colors hover:bg-steel-100 hover:text-steel-900 sm:inline-flex"
            >
              Kapsam
            </a>
            <Link
              to="/upload"
              className="ml-1 rounded-md border border-steel-300 bg-white px-3 py-1.5 text-sm font-medium text-steel-800 transition-colors hover:bg-steel-50"
            >
              Başla
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 sm:px-6">
        {/* ---------------------------------------------------------------- */}
        {/* Hero                                                             */}
        {/* ---------------------------------------------------------------- */}
        <section className="grid items-center gap-10 py-14 lg:grid-cols-[1.02fr_0.98fr] lg:gap-14 lg:py-20">
          <div>
            <p className="text-label tracking-[0.14em] text-copper-600 uppercase">
              Metraj → satın alma listesi
            </p>

            <h1 className="mt-3 text-display text-balance text-steel-900">
              Metrajı incelenmiş bir satın alma listesine çevirin.
            </h1>

            <p className="mt-4 max-w-xl text-body-lg text-steel-600">
              Excel metrajını yükleyin; malzeme açıklamaları eşleştirilir, belirsiz
              satırları onaylarsınız ve fire, birim dönüşümü ve ticari boy
              yuvarlaması uygulanmış nihai listeyi Excel veya PDF olarak
              indirirsiniz. Hesaplamalar deterministik, eşleştirme şeffaftır.
            </p>

            <div className="mt-7 flex flex-wrap items-center gap-2.5">
              <Link
                to={nextStep.to}
                className="inline-flex h-11 items-center gap-2 rounded-md border border-ink bg-ink px-5 text-body font-medium text-white transition-colors duration-[120ms] hover:bg-steel-800"
              >
                {nextStep.label}
                <IconArrowRight />
              </Link>
              {analyzeView && (
                <Link
                  to="/analysis"
                  className="inline-flex h-11 items-center gap-2 rounded-md border border-steel-300 bg-white px-5 text-body font-medium text-steel-800 transition-colors duration-[120ms] hover:bg-steel-50"
                >
                  Analizi gör
                </Link>
              )}
            </div>

            <div className="mt-6 flex items-start gap-2.5 rounded-md border border-dashed border-steel-300 bg-white px-3.5 py-2.5">
              <IconInfo className="mt-0.5 text-steel-500" />
              <p className="text-sm text-steel-600">
                <span className="font-semibold text-steel-700">
                  Hesaplama sunucuda yapılır.
                </span>{' '}
                Arayüz hiçbir miktarı kendi hesaplamaz; yalnızca kullanıcı
                kararlarını toplar ve sonucu gösterir.
              </p>
            </div>
          </div>

          {/* Akış önizlemesi — gerçek durumdan */}
          <div className="relative min-w-0 overflow-hidden">
            <div
              aria-hidden
              className="blueprint-grid pointer-events-none absolute -inset-x-6 -inset-y-6 rounded-xl opacity-40 [mask-image:radial-gradient(ellipse_at_center,black,transparent_72%)]"
            />
            <figure className="relative rounded-xl border border-steel-200 bg-white shadow-sm">
              <figcaption className="flex items-center justify-between gap-3 border-b border-steel-100 px-4 py-3">
                <span className="text-sm font-semibold text-steel-800">
                  Akış durumu
                </span>
                <span className="font-mono text-xs text-steel-500">
                  {analyzeView ? 'canlı veri' : 'başlanmadı'}
                </span>
              </figcaption>

              <div className="divide-y divide-steel-100">
                {[
                  {
                    no: '01',
                    label: 'Metraj yükleme',
                    detail: analyzeView ? analyzeView.fileName : 'Dosya seçilmedi',
                    done: Boolean(analyzeView),
                  },
                  {
                    no: '02',
                    label: 'Analiz',
                    detail: analyzeView
                      ? `${analyzeView.summary.total} satır · ${analyzeView.summary.rule} kural, ${analyzeView.summary.pending} onay bekliyor`
                      : 'Henüz çalıştırılmadı',
                    done: Boolean(analyzeView),
                  },
                  {
                    no: '03',
                    label: 'Eşleştirme',
                    detail: analyzeView
                      ? `${eligibleCount} / ${total} hesaba uygun · ${counts.pending} onay bekliyor`
                      : 'Karar beklenmiyor',
                    done: Boolean(analyzeView) && counts.pending === 0,
                  },
                  {
                    no: '04',
                    label: 'Hesaplama',
                    detail: calculation
                      ? `${calculation.summary.groups} grup · ${calculation.summary.partial_groups} KISMİ`
                      : 'Henüz hesaplanmadı',
                    done: Boolean(calculation),
                  },
                ].map((step) => (
                  <div
                    key={step.no}
                    className="flex items-center gap-3 px-4 py-3"
                  >
                    <span
                      className={
                        step.done
                          ? 'grid size-6 shrink-0 place-items-center rounded-full bg-success-bg text-success-fg ring-1 ring-success-br'
                          : 'grid size-6 shrink-0 place-items-center rounded-full bg-steel-100 font-mono text-[10px] text-steel-500 ring-1 ring-steel-200'
                      }
                    >
                      {step.done ? (
                        <IconCheck className="size-3.5" />
                      ) : (
                        step.no
                      )}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium text-steel-800">
                        {step.label}
                      </span>
                      <span className="block truncate text-xs text-steel-500">
                        {step.detail}
                      </span>
                    </span>
                  </div>
                ))}
              </div>

              <div className="flex items-center gap-2 border-t border-steel-100 bg-warning-bg px-4 py-2.5">
                <IconAlert className="text-warning-fg" />
                <p className="text-sm text-warning-fg">
                  <span className="font-semibold">Onaysız satır hesaba girmez.</span>{' '}
                  Bu satırlar raporda ayrıca listelenir.
                </p>
              </div>

              <div className="flex items-center justify-between gap-3 border-t border-steel-100 px-4 py-2.5">
                <span className="text-xs text-steel-500">
                  {calculation
                    ? `${calculation.summary.groups} malzeme grubu`
                    : 'Sonuç bekleniyor'}
                </span>
                <Badge tone="neutral">Sunucu hesaplar</Badge>
              </div>
            </figure>
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Beş adımlı akış                                                  */}
        {/* ---------------------------------------------------------------- */}
        <section id="akis" className="scroll-mt-20 border-t border-steel-200 py-12">
          <h2 className="text-h2 text-steel-900">Beş adımda satın alma listesi</h2>
          <p className="mt-1.5 max-w-2xl text-body text-steel-500">
            Her adım tek bir işi yapar. Hesap gerektiren hiçbir değer arayüzde
            üretilmez.
          </p>

          <ol className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {[
              {
                no: '01',
                title: 'Metrajı yükle',
                text: 'Excel şablonunu yükleyin; satırlar ve birimler sunucuda doğrulanır.',
              },
              {
                no: '02',
                title: 'Analizi gör',
                text: 'Kural eşleşmeleri, onay bekleyen satırlar ve AI önerileri ayrı gösterilir.',
              },
              {
                no: '03',
                title: 'Onayla',
                text: 'AI önerisini kabul edin, reddedin veya katalogdan başka bir kod seçin.',
              },
              {
                no: '04',
                title: 'Hesapla',
                text: 'Fire, birim dönüşümü, birleştirme ve ticari boy sunucuda uygulanır.',
              },
              {
                no: '05',
                title: 'Dışa aktar',
                text: 'Aynı sonuçtan üretilen Excel veya PDF raporunu indirin.',
              },
            ].map((step, index) => (
              <li
                key={step.no}
                className="relative rounded-lg border border-steel-200 bg-white p-5"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="tabular font-mono text-xs text-copper-600">
                    {step.no}
                  </span>
                </div>
                <h3 className="mt-3 text-h3 text-steel-900">{step.title}</h3>
                <p className="mt-1.5 text-sm text-steel-600">{step.text}</p>
                {index < 4 && (
                  <span
                    aria-hidden
                    className="absolute top-1/2 -right-2 hidden size-1.5 -translate-y-1/2 rounded-full bg-steel-300 lg:block"
                  />
                )}
              </li>
            ))}
          </ol>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Kapsam                                                           */}
        {/* ---------------------------------------------------------------- */}
        <section
          id="kapsam"
          className="scroll-mt-20 border-t border-steel-200 py-12"
        >
          <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
            <div>
              <h2 className="text-h2 text-steel-900">Ne yapar, ne yapmaz</h2>
              <p className="mt-1.5 text-body text-steel-500">
                Kapsamı dar tutmak, tek iş akışını doğru yapmanın ön koşulu.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-lg border border-steel-200 bg-white p-5">
                <div className="flex items-center gap-2">
                  <IconCheck className="text-success-fg" />
                  <h3 className="text-body font-semibold text-steel-900">
                    Kapsamda
                  </h3>
                </div>
                <ul className="mt-3 space-y-2 text-sm text-steel-600">
                  <li>BOQ → malzeme eşleştirme ve onay akışı</li>
                  <li>Desteklenen aileler: BOX, IPE, HEA, UPN, lama</li>
                  <li>m · kg · t birimleri, fire ve birleştirme</li>
                  <li>Kaynak satıra kadar izlenebilirlik</li>
                  <li>Excel ve PDF satın alma raporu</li>
                </ul>
              </div>

              <div className="rounded-lg border border-steel-200 bg-white p-5">
                <div className="flex items-center gap-2">
                  <IconLayers className="text-steel-500" />
                  <h3 className="text-body font-semibold text-steel-900">
                    Kapsam dışı
                  </h3>
                </div>
                <ul className="mt-3 space-y-2 text-sm text-steel-600">
                  <li>ERP, muhasebe veya tedarikçi entegrasyonu</li>
                  <li>Metraj çıkarma, CAD/BIM veya statik tasarım</li>
                  <li>Kesim optimizasyonu ve fiyatlandırma</li>
                  <li>Kullanıcı hesabı, abonelik, çoklu proje</li>
                </ul>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-steel-200">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-6 sm:px-6">
          <p className="text-sm text-steel-500">BuildFlow AI</p>
          <Badge tone="neutral">Hesaplama sunucuda</Badge>
        </div>
      </footer>
    </div>
  )
}
