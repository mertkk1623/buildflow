import { Link, useNavigate } from 'react-router-dom'

import { Badge } from '../components/ui/Status'
import {
  IconAlert,
  IconArrowRight,
  IconCheck,
  IconDownload,
  IconFile,
  IconInfo,
} from '../components/ui/icons'
import { EXAMPLE_FILES, SAMPLE_PROJECT_FILE } from '../lib/examples'
import { useWorkflow } from '../state/WorkflowContext'

/**
 * Landing — ürün tanıtımı ve demo girişi.
 *
 * Akışın gerçek durumunu gösterir: analiz edilmiş dosya varsa devam bağlantısı
 * doğrudan o adıma gider. Sabit demo seti yoktur.
 *
 * Ürün iddiası ile gerçek durum ayrı tutulur: V1 özellikleri "çalışıyor",
 * yol haritası ise açıkça "planlandı" olarak işaretlenir.
 */

const FLOW_STEPS = [
  {
    no: '01',
    title: 'Metrajı yükle',
    text: 'Excel şablonunu yükleyin; satırlar ve birimler sunucuda doğrulanır.',
  },
  {
    no: '02',
    title: 'Analiz ve eşleştirme',
    text: 'Açıklamalar yorumlanır, katalog kalemleriyle deterministik olarak eşleştirilir.',
  },
  {
    no: '03',
    title: 'Belirsizleri onayla',
    text: 'Tek kaleme oturmayan satırlarda katalog adaylarını siz seçersiniz.',
  },
  {
    no: '04',
    title: 'Hesapla',
    text: 'Fire, birim dönüşümü, birleştirme ve ticari boy sunucuda uygulanır.',
  },
  {
    no: '05',
    title: 'Dışa aktar',
    text: 'Aynı sonuçtan üretilen Excel veya PDF satın alma listesini indirin.',
  },
]

const V1_FEATURES = [
  'Excel metraj yükleme ve satır bazlı doğrulama',
  'Malzeme eşleştirme (deterministik, katalogla sınırlı)',
  'Kullanıcı onaylı belirsiz eşleşmeler',
  'BOX, IPE, HEA, UPN ve lama profilleri',
  'm · kg · t birimleri ve birim dönüşümü',
  'Fire ve tekrar eden kalemlerin birleştirilmesi',
  'Kaynak satıra kadar izlenebilirlik',
  'Excel ve PDF satın alma raporu',
]

const ROADMAP = [
  {
    version: 'V2',
    title: 'Geliştirme planı',
    items: [
      'Genişletilmiş malzeme ve profil kütüphanesi',
      'Gelişmiş AI eşleştirme',
      'Daha fazla metraj formatı desteği',
      'Gelişmiş satın alma ve tedarikçi analizleri',
    ],
  },
  {
    version: 'V3',
    title: 'Uzun vadeli hedefler',
    items: [
      'Tedarikçi portalı',
      'ERP/SAP entegrasyonları',
      'Proje ve analiz geçmişi',
      'Çoklu para birimi desteği',
    ],
  },
]

const NAV = [
  { href: '#hizli-baslangic', label: 'Hızlı başlangıç' },
  { href: '#ornekler', label: 'Örnekler' },
  { href: '#akis', label: 'Akış' },
  { href: '#ozellikler', label: 'Özellikler' },
  { href: '#yol-haritasi', label: 'Yol haritası' },
]

export default function LandingPage() {
  const navigate = useNavigate()
  const {
    analyzeView,
    counts,
    total,
    eligibleCount,
    calculation,
    saveTemplate,
    templateStatus,
    templateError,
    loadSample,
    sampleStatus,
    sampleError,
  } = useWorkflow()

  const nextStep = calculation
    ? { to: '/results', label: 'Sonuçları gör' }
    : analyzeView
      ? { to: '/review', label: 'Eşleşmeleri incele' }
      : { to: '/upload', label: 'Canlı demoyu başlat' }

  const downloadingTemplate = templateStatus === 'downloading'
  const loadingSample = sampleStatus === 'loading'

  /** Örnek veriyi yükleyip analizi başlatır; başarılıysa analiz ekranına geçer. */
  const startSample = async () => {
    const ok = await loadSample()
    if (ok) navigate('/analysis')
  }

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
            {NAV.map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="hidden rounded-md px-3 py-1.5 text-sm text-steel-600 transition-colors hover:bg-steel-100 hover:text-steel-900 md:inline-flex"
              >
                {item.label}
              </a>
            ))}
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
              Excel metrajını yükleyin; malzeme açıklamaları katalogla
              eşleştirilir, belirsiz satırları onaylarsınız ve fire, birim
              dönüşümü ve ticari boy yuvarlaması uygulanmış nihai listeyi Excel
              veya PDF olarak indirirsiniz. Hesaplamalar deterministik,
              eşleştirme şeffaftır.
            </p>

            <div className="mt-7 flex flex-wrap items-center gap-2.5">
              <Link
                to={nextStep.to}
                className="inline-flex h-11 items-center gap-2 rounded-md border border-ink bg-ink px-5 text-body font-medium text-white transition-colors duration-[120ms] hover:bg-steel-800"
              >
                {nextStep.label}
                <IconArrowRight />
              </Link>
              <button
                type="button"
                onClick={() => void saveTemplate()}
                disabled={downloadingTemplate}
                className="inline-flex h-11 items-center gap-2 rounded-md border border-steel-300 bg-white px-4 text-sm font-medium text-steel-800 transition-colors duration-[120ms] hover:bg-steel-50 disabled:cursor-not-allowed disabled:opacity-45 sm:px-5 sm:text-body"
              >
                <IconDownload />
                {downloadingTemplate
                  ? 'Şablon indiriliyor…'
                  : 'Örnek Excel Şablonunu İndir'}
              </button>
            </div>

            {templateError && (
              <p className="mt-3 flex items-start gap-2 text-sm text-danger-fg">
                <IconAlert className="mt-0.5" />
                <span>
                  {templateError.title}
                  {templateError.suggestion && ` ${templateError.suggestion}`}
                </span>
              </p>
            )}

            <p className="mt-4 text-sm text-steel-500">
              Şablon sunucuda üretilir (
              <span className="font-mono text-xs">GET /api/template</span>) ·
              hazır örnek dosyalar{' '}
              <a
                href="#ornekler"
                className="text-steel-700 underline underline-offset-2"
              >
                aşağıda
              </a>
              .
            </p>

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
        {/* Hızlı başlangıç                                                  */}
        {/* ---------------------------------------------------------------- */}
        <section
          id="hizli-baslangic"
          className="scroll-mt-20 border-t border-steel-200 py-12"
        >
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-h2 text-steel-900">
                Hızlı başlangıç ve örnek veri
              </h2>
              <p className="mt-1.5 max-w-2xl text-body text-steel-500">
                Dosya hazırlamadan deneyin. Örnek metraj gerçek bir dosyadır;
                yükleme, analiz ve onay akışı birebir aynı yoldan çalışır.
              </p>
            </div>
            <Badge tone="copper">Kurulum gerekmez</Badge>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
            {/* Eylemler */}
            <div className="rounded-lg border border-steel-200 bg-white p-5">
              <div className="space-y-2.5">
                <button
                  type="button"
                  onClick={() => void startSample()}
                  disabled={loadingSample}
                  className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md border border-ink bg-ink px-4 py-2 text-center text-body font-medium leading-tight text-white transition-colors duration-[120ms] hover:bg-steel-800 disabled:cursor-not-allowed disabled:opacity-45"
                >
                  <span aria-hidden>🚀</span>
                  <span className="min-w-0">
                    {loadingSample
                      ? 'Örnek veri hazırlanıyor…'
                      : 'Örnek Veri ile Hemen Dene (AI Demo)'}
                  </span>
                  {!loadingSample && <IconArrowRight />}
                </button>

                <div className="grid gap-2.5 sm:grid-cols-2">
                  <button
                    type="button"
                    onClick={() => void saveTemplate()}
                    disabled={downloadingTemplate}
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-steel-300 bg-white px-3 text-sm font-medium text-steel-800 transition-colors duration-[120ms] hover:bg-steel-50 disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    <span aria-hidden>📥</span>
                    {downloadingTemplate
                      ? 'İndiriliyor…'
                      : 'Boş Veri Şablonunu İndir'}
                  </button>

                  <a
                    href={SAMPLE_PROJECT_FILE.href}
                    download={SAMPLE_PROJECT_FILE.name}
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-steel-300 bg-white px-3 text-sm font-medium text-steel-800 transition-colors duration-[120ms] hover:bg-steel-50"
                  >
                    <span aria-hidden>📊</span>
                    Örnek Dolu Dosyayı İndir
                    <span className="sr-only">
                      : {SAMPLE_PROJECT_FILE.name}
                    </span>
                  </a>
                </div>
              </div>

              {templateError && (
                <p className="mt-3 flex items-start gap-2 text-sm text-danger-fg">
                  <IconAlert className="mt-0.5" />
                  <span>
                    {templateError.title}
                    {templateError.suggestion && ` ${templateError.suggestion}`}
                  </span>
                </p>
              )}

              {sampleError && (
                <p className="mt-3 flex items-start gap-2 text-sm text-danger-fg">
                  <IconAlert className="mt-0.5" />
                  <span>
                    {sampleError.message} {sampleError.suggestion}
                  </span>
                </p>
              )}

              <p className="mt-3 text-xs text-steel-500">
                “Hemen dene” dosya indirmez: örnek metrajı alıp doğrudan
                analize verir. Boş şablon sunucuda üretilir (
                <span className="font-mono">GET /api/template</span>).
              </p>
            </div>

            {/* Bilgi notu */}
            <div className="rounded-lg border border-dashed border-steel-300 bg-steel-50 p-5">
              <div className="flex items-center gap-2">
                <IconInfo className="text-steel-500" />
                <p className="text-sm font-semibold text-steel-800">
                  Örnek veri seti
                </p>
                <Badge tone="neutral">40 satır</Badge>
              </div>
              <p className="mt-2 text-sm text-steel-600">
                Örnek veri seti; <span className="font-medium">AI eşleştirme
                önerisi</span>, <span className="font-medium">onay akışı</span>{' '}
                ve <span className="font-medium">kapsam dışı satır
                raporlaması</span> özelliklerini test etmeniz için gerçekçi
                senaryolar içerir.
              </p>
              <ul className="mt-3 space-y-2 text-sm text-steel-600">
                {[
                  '14 katalog kaleminin tamamı; aynı kodu isteyen farklı iş kalemleri tek satın alma kaleminde birleşir.',
                  '5 satır onay bekler: AI yalnızca bu satırlarda öneri üretir, öneri otomatik onaylanmaz.',
                  'Yüksek fireli pozlar (%12 ve %9) sipariş miktarını net metrajın belirgin üzerine çıkarır.',
                  'Üç kapsam dışı nedeni birlikte görünür: katalog dışı kaplama, boş fire ve “adet” birimi.',
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <IconCheck className="mt-0.5 text-success-fg" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 font-mono text-xs text-steel-500">
                {SAMPLE_PROJECT_FILE.name}
              </p>
            </div>
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Örnek dosyalar                                                   */}
        {/* ---------------------------------------------------------------- */}
        <section
          id="ornekler"
          className="scroll-mt-20 border-t border-steel-200 py-12"
        >
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-h2 text-steel-900">Örnek dosyalar</h2>
              <p className="mt-1.5 max-w-2xl text-body text-steel-500">
                Hepsi gerçek uygulamadan üretildi. Metrajı indirip yükleyin veya
                rapor çıktısını inceleyin.
              </p>
            </div>
            <Badge tone="neutral">Gerçek dosyalar</Badge>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
            {/* Boş şablon — sunucuda üretilir */}
            <div className="flex flex-col justify-between rounded-lg border border-ink bg-ink p-5 text-white">
              <div>
                <div className="flex items-center gap-2">
                  <IconDownload className="text-copper-200" />
                  <p className="text-label tracking-[0.08em] text-copper-200 uppercase">
                    Başlangıç
                  </p>
                </div>
                <h3 className="mt-2 text-h3 text-white">Boş metraj şablonu</h3>
                <p className="mt-2 text-sm text-steel-300">
                  Zorunlu sütunlar ve kullanım sayfası dahil. Sunucuda üretilir,
                  her zaman güncel sürümdür.
                </p>
                <p className="mt-3 font-mono text-xs text-steel-400">
                  GET /api/template · .xlsx
                </p>
              </div>
              <button
                type="button"
                onClick={() => void saveTemplate()}
                disabled={downloadingTemplate}
                className="mt-5 inline-flex h-10 items-center justify-center gap-2 rounded-md bg-white px-4 text-body font-medium text-ink transition-colors duration-[120ms] hover:bg-steel-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <IconDownload />
                {downloadingTemplate ? 'İndiriliyor…' : 'Şablonu indir'}
              </button>
            </div>

            {/* Hazır örnekler */}
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {EXAMPLE_FILES.map((file) => (
                <li
                  key={file.name}
                  className="flex flex-col rounded-lg border border-steel-200 bg-white p-4"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="grid size-8 shrink-0 place-items-center rounded-sm bg-steel-100 text-steel-600">
                      <IconFile />
                    </span>
                    <Badge tone="neutral" mono>
                      {file.format}
                    </Badge>
                  </div>
                  <h3 className="mt-3 text-body font-semibold text-steel-900">
                    {file.label}
                  </h3>
                  <p className="mt-1 flex-1 text-sm text-steel-600">
                    {file.description}
                  </p>
                  <Badge
                    tone={file.kind === 'metraj' ? 'copper' : 'neutral'}
                    className="mt-2 self-start"
                  >
                    {file.kind === 'metraj' ? 'Yüklenebilir metraj' : 'Rapor çıktısı'}
                  </Badge>
                  <a
                    href={file.href}
                    {...(file.action === 'download'
                      ? { download: file.name }
                      : { target: '_blank', rel: 'noopener noreferrer' })}
                    className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-steel-800 underline underline-offset-2 hover:text-copper-700"
                  >
                    <IconDownload className="size-3.5" />
                    {file.action === 'download' ? 'İndir' : 'Görüntüle'}
                    <span className="sr-only">
                      : {file.label} ({file.name})
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Beş adımlı akış                                                  */}
        {/* ---------------------------------------------------------------- */}
        <section id="akis" className="scroll-mt-20 border-t border-steel-200 py-12">
          <h2 className="text-h2 text-steel-900">Nasıl çalışır?</h2>
          <p className="mt-1.5 max-w-2xl text-body text-steel-500">
            Beş adım, tek bir yönlendirilmiş süreç. Hesap gerektiren hiçbir değer
            arayüzde üretilmez.
          </p>

          <ol className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {FLOW_STEPS.map((step, index) => (
              <li
                key={step.no}
                className="relative rounded-lg border border-steel-200 bg-white p-5"
              >
                <span className="tabular font-mono text-xs text-copper-600">
                  {step.no}
                </span>
                <h3 className="mt-3 text-h3 text-steel-900">{step.title}</h3>
                <p className="mt-1.5 text-sm text-steel-600">{step.text}</p>
                {index < FLOW_STEPS.length - 1 && (
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
        {/* V1 özellikler                                                    */}
        {/* ---------------------------------------------------------------- */}
        <section
          id="ozellikler"
          className="scroll-mt-20 border-t border-steel-200 py-12"
        >
          <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-h2 text-steel-900">V1 — şu anda çalışıyor</h2>
                <Badge tone="success">Canlı</Badge>
              </div>
              <p className="mt-1.5 max-w-md text-body text-steel-500">
                Aşağıdaki özellikler bu demoda gerçekten çalışır; hesaplama
                motoru sunucudadır.
              </p>

              <div className="mt-4 rounded-md border border-steel-200 bg-white px-3.5 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <IconInfo className="text-steel-500" />
                  <p className="text-sm font-semibold text-steel-800">
                    AI eşleştirme
                  </p>
                  <Badge tone="neutral">Yapılandırmaya bağlı</Badge>
                </div>
                <p className="mt-1.5 text-sm text-steel-600">
                  AI etkin olduğunda yalnızca onay bekleyen satırlar için malzeme
                  eşleştirme önerileri üretir. Öneriler otomatik onaylanmaz.
                </p>
              </div>
            </div>

            <div className="rounded-lg border border-steel-200 bg-white p-5">
              <ul className="grid gap-2.5 sm:grid-cols-2">
                {V1_FEATURES.map((feature) => (
                  <li key={feature} className="flex items-start gap-2 text-sm">
                    <IconCheck className="mt-0.5 text-success-fg" />
                    <span className="text-steel-700">{feature}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-4 border-t border-steel-100 pt-3 text-xs text-steel-500">
                V1 kapsam dışı: ERP/tedarikçi entegrasyonu · CAD/BIM metraj
                çıkarma ve statik tasarım · kesim optimizasyonu · fiyat ve
                maliyet hesabı · kullanıcı hesabı ve çoklu proje.
              </p>
            </div>
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Yol haritası                                                     */}
        {/* ---------------------------------------------------------------- */}
        <section
          id="yol-haritasi"
          className="scroll-mt-20 border-t border-steel-200 py-12"
        >
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-h2 text-steel-900">Ürün yol haritası</h2>
              <p className="mt-1.5 max-w-2xl text-body text-steel-500">
                Aşağıdakiler henüz geliştirilmedi. Takvim taahhüdü değil, yön
                beyanıdır.
              </p>
            </div>
            <Badge tone="warning">Planlandı</Badge>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            {ROADMAP.map((phase) => (
              <div
                key={phase.version}
                className="rounded-lg border border-dashed border-steel-300 bg-steel-50 p-5"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs text-steel-500">
                    {phase.version}
                  </span>
                  <h3 className="text-body font-semibold text-steel-900">
                    {phase.title}
                  </h3>
                  <Badge tone="warning">Planlandı</Badge>
                </div>
                <ul className="mt-3 grid gap-2 text-sm text-steel-600 sm:grid-cols-2">
                  {phase.items.map((item) => (
                    <li key={item} className="flex items-start gap-2">
                      <span
                        aria-hidden
                        className="mt-1.5 size-1 shrink-0 rounded-full bg-steel-400"
                      />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-steel-200">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-6 sm:px-6">
          <p className="text-sm text-steel-500">BuildFlow AI</p>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="neutral">Hesaplama sunucuda</Badge>
            <Link
              to="/upload"
              className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-steel-700 transition-colors hover:bg-steel-100"
            >
              Demoyu başlat
              <IconArrowRight />
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
