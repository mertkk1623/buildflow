import { useRef, useState, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ActionBar, AppShell, PageHeader } from '../components/layout/AppShell'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { Alert, Badge } from '../components/ui/Status'
import {
  IconAlert,
  IconArrowRight,
  IconDownload,
  IconFile,
  IconInfo,
  IconUpload,
} from '../components/ui/icons'
import { ApiErrorNotice, WarningList } from '../components/workflow/ApiErrorNotice'
import { DEMO_METRAJ_FILE, EXAMPLE_FILES } from '../lib/examples'
import { formatFileSize } from '../lib/format'
import { cn } from '../lib/ui'
import { useWorkflow } from '../state/WorkflowContext'

/**
 * Upload — 01.
 *
 * Tek iş: `.xlsx` metraj dosyasını `/api/analyze`'e göndermek. Doğrulama
 * iki katmanda yapılır: burada yalnızca uzantı/boyut (hızlı geri bildirim),
 * gerçek içerik doğrulaması sunucuda (`unsupported-format`, `corrupt-file`,
 * `missing-column`).
 */

/** Sunucu sınırı: `BUILDFLOW_MAX_UPLOAD_BYTES`, varsayılan 10 MB. */
const MAX_FILE_BYTES = 10 * 1024 * 1024

/** Denemek için hazır dosyalar — ana sayfayla aynı kaynaktan gelir. */
const DEMO_METRAJ = DEMO_METRAJ_FILE
const DEMO_REPORTS = EXAMPLE_FILES.filter((file) => file.kind === 'rapor')

const TEMPLATE_COLUMNS = [
  { name: 'BOQ No', note: 'Benzersiz satır kimliği' },
  { name: 'Açıklama', note: 'Malzeme tanımı (serbest metin)' },
  { name: 'Miktar', note: 'Sıfırdan büyük sayı' },
  { name: 'Birim', note: 'm · kg · t' },
  { name: 'Fire (%)', note: 'Zorunlu: boşsa satır hesaba girmez' },
]

/** İstemci tarafı ön kontrol: yalnızca hızlı geri bildirim, otorite değil. */
function localFileProblem(file: File): string | null {
  if (!file.name.toLowerCase().endsWith('.xlsx')) {
    return `Desteklenmeyen dosya biçimi: "${file.name}". Yalnızca .xlsx okunur (.xls, .xlsm, .csv desteklenmez).`
  }
  if (file.size === 0) {
    return 'Seçilen dosya boş (0 bayt).'
  }
  if (file.size > MAX_FILE_BYTES) {
    return `Dosya çok büyük (${formatFileSize(file.size)}). En fazla ${formatFileSize(MAX_FILE_BYTES)} yüklenebilir.`
  }
  return null
}

export default function UploadPage() {
  const navigate = useNavigate()
  const {
    analyze,
    stage,
    fileName,
    fileSize,
    analyzeView,
    error,
    templateStatus,
    templateError,
    saveTemplate,
    reset,
  } = useWorkflow()

  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const isAnalyzing = stage === 'analyzing'

  const handleFile = (file: File | undefined) => {
    if (!file) return
    const problem = localFileProblem(file)
    setLocalError(problem)
    if (problem) return
    void analyze(file)
  }

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragging(false)
    if (isAnalyzing) return
    handleFile(event.dataTransfer.files[0])
  }

  return (
    <AppShell current="upload">
      <PageHeader
        stepNo="01"
        title="Metraj yükleme"
        description="Belgelenmiş Excel şablonunu yükleyin. Dosya sunucuda doğrulanır, satırlar ve birimler okunur."
        actions={
          <>
            <Button
              variant="secondary"
              size="sm"
              icon={<IconFile />}
              onClick={() => void saveTemplate()}
              disabled={templateStatus === 'downloading'}
            >
              {templateStatus === 'downloading'
                ? 'Şablon indiriliyor…'
                : 'Şablonu indir'}
            </Button>
            <Badge tone="neutral">.xlsx · en fazla 10 MB</Badge>
          </>
        }
      />

      {templateError && (
        <ApiErrorNotice error={templateError} className="mb-5" />
      )}

      {localError && (
        <Alert tone="danger" title="Dosya seçilemedi" icon={<IconAlert />} className="mb-5">
          {localError}
        </Alert>
      )}

      {error && error.stage === 'analyze' && (
        <ApiErrorNotice error={error} className="mb-5" />
      )}

      {analyzeView && (
        <Alert
          tone="success"
          title="Analiz tamamlandı"
          icon={<IconInfo />}
          className="mb-5"
          action={
            <Link
              to="/analysis"
              className="inline-flex h-9 items-center gap-2 rounded-md border border-success-br bg-white px-3 text-sm font-medium text-success-fg transition-colors hover:bg-success-bg"
            >
              Analizi gör
              <IconArrowRight />
            </Link>
          }
        >
          <span className="font-medium">{analyzeView.fileName}</span> —{' '}
          {analyzeView.sheetName} sayfası, {analyzeView.summary.total} satır (
          {analyzeView.summary.rule} kural, {analyzeView.summary.pending} onay
          bekliyor, {analyzeView.summary.excluded} hariç
          {analyzeView.summary.invalidRows > 0
            ? `, ${analyzeView.summary.invalidRows} geçersiz`
            : ''}
          ).
        </Alert>
      )}

      <div className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
        {/* Sol: dosya alanı */}
        <div className="space-y-4">
          <Card>
            <CardHeader
              title="Metraj dosyası"
              description=".xlsx · en fazla 10 MB · ilk sayfa ya da 'Metraj' sayfası okunur"
              action={
                <Badge tone={isAnalyzing ? 'copper' : 'neutral'}>
                  {isAnalyzing ? 'Analiz ediliyor' : 'Hazır'}
                </Badge>
              }
            />
            <CardBody>
              <div
                onDragOver={(event) => {
                  event.preventDefault()
                  if (!isAnalyzing) setDragging(true)
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                className={cn(
                  'rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors duration-[120ms]',
                  dragging
                    ? 'border-copper-500 bg-copper-50/50'
                    : 'border-steel-300 bg-steel-50',
                  isAnalyzing && 'opacity-70',
                )}
              >
                <span className="mx-auto grid size-11 place-items-center rounded-full bg-white text-steel-500 ring-1 ring-steel-200">
                  <IconUpload className="size-5" />
                </span>

                <p className="mt-3 text-body font-semibold text-steel-800">
                  {isAnalyzing
                    ? 'Dosya sunucuda analiz ediliyor…'
                    : 'Excel dosyasını sürükleyin'}
                </p>
                <p className="mt-1 text-sm text-steel-500">
                  {isAnalyzing
                    ? 'Satırlar okunuyor ve malzeme eşleştirmesi yapılıyor.'
                    : 'veya dosya seçin — .xlsx biçimi'}
                </p>

                <div className="mt-4 flex flex-col items-center gap-2">
                  <input
                    ref={inputRef}
                    type="file"
                    accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    className="sr-only"
                    onChange={(event) => {
                      handleFile(event.target.files?.[0])
                      // Aynı dosya yeniden seçilebilsin.
                      event.target.value = ''
                    }}
                    disabled={isAnalyzing}
                    aria-label="Metraj dosyası seç"
                  />
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<IconUpload />}
                    onClick={() => inputRef.current?.click()}
                    disabled={isAnalyzing}
                  >
                    {isAnalyzing ? 'Analiz sürüyor…' : 'Dosya seç'}
                  </Button>
                  <p className="text-xs text-steel-500">
                    Desteklenen biçim: .xlsx · en fazla 10 MB
                  </p>
                </div>
              </div>

              {/* Seçilen dosya */}
              {fileName && (
                <div className="mt-4 rounded-md border border-steel-200 bg-white">
                  <div className="flex items-center gap-3 px-3.5 py-3">
                    <span className="grid size-8 shrink-0 place-items-center rounded-sm bg-steel-100 text-steel-600">
                      <IconFile />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-steel-900">
                        {fileName}
                      </p>
                      <p className="truncate text-xs text-steel-500">
                        {fileSize !== null
                          ? `${formatFileSize(fileSize)} · sunucuya gönderildi`
                          : 'Seçilen dosya'}
                      </p>
                    </div>
                    <Badge
                      tone={
                        isAnalyzing
                          ? 'copper'
                          : analyzeView
                            ? 'success'
                            : 'neutral'
                      }
                    >
                      {isAnalyzing
                        ? 'Analiz ediliyor'
                        : analyzeView
                          ? `${analyzeView.summary.total} satır`
                          : 'Yüklendi'}
                    </Badge>
                  </div>

                  {analyzeView && (
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 border-t border-steel-100 px-3.5 py-3 text-sm sm:grid-cols-4">
                      {[
                        ['Satır', String(analyzeView.summary.total)],
                        ['Kural', String(analyzeView.summary.rule)],
                        ['Onay bekliyor', String(analyzeView.summary.pending)],
                        ['Hariç', String(analyzeView.summary.excluded)],
                      ].map(([label, value]) => (
                        <div key={label}>
                          <dt className="text-xs text-steel-500">{label}</dt>
                          <dd className="tabular font-mono text-steel-900">
                            {value}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  )}
                </div>
              )}
            </CardBody>
          </Card>

          {/* Analizden dönen uyarılar — kaybolmaz */}
          {analyzeView && analyzeView.warnings.length > 0 && (
            <WarningList
              warnings={analyzeView.warnings}
              title="Analiz uyarıları"
            />
          )}

          {analyzeView && analyzeView.ignoredColumns.length > 0 && (
            <Alert tone="info" title="Yok sayılan sütunlar" icon={<IconInfo />}>
              <p>
                Şablon dışı sütunlar okunmadı:{' '}
                <span className="font-mono text-xs">
                  {analyzeView.ignoredColumns.join(', ')}
                </span>
              </p>
              <p className="mt-1 text-xs opacity-80">
                Bu sütunlar hesaba katılmaz; veri kaybı olmaması için yalnızca
                şablon sütunlarını kullanın.
              </p>
            </Alert>
          )}
        </div>

        {/* Sağ: gereksinimler */}
        <div className="space-y-4">
          <Card>
            <CardHeader title="Şablon gereksinimleri" />
            <CardBody className="space-y-4">
              <div>
                <p className="text-label tracking-[0.08em] text-steel-500 uppercase">
                  Zorunlu sütunlar
                </p>
                <ul className="mt-2 space-y-1.5">
                  {TEMPLATE_COLUMNS.map((column) => (
                    <li key={column.name} className="flex gap-2 text-sm">
                      <span className="font-mono text-xs text-steel-500">·</span>
                      <span className="text-steel-800">{column.name}</span>
                      <span className="text-steel-500">— {column.note}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <p className="text-label tracking-[0.08em] text-steel-500 uppercase">
                  Desteklenen birimler
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {['m', 'kg', 't'].map((unit) => (
                    <Badge key={unit} tone="neutral" mono>
                      {unit}
                    </Badge>
                  ))}
                  <Badge tone="neutral">adet desteklenmiyor</Badge>
                </div>
              </div>

              <div>
                <p className="text-label tracking-[0.08em] text-steel-500 uppercase">
                  Malzeme aileleri
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {['BOX', 'IPE', 'HEA', 'UPN', 'Lama'].map((family) => (
                    <Badge key={family} tone="neutral" mono>
                      {family}
                    </Badge>
                  ))}
                </div>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Örnek dosyalar"
              description="Denemek için hazır, gerçek uygulamadan üretilmiş dosyalar."
              action={<Badge tone="neutral">Gerçek dosyalar</Badge>}
            />
            <CardBody className="space-y-3">
              {DEMO_METRAJ && (
                <a
                  href={DEMO_METRAJ.href}
                  download={DEMO_METRAJ.name}
                  className="flex items-start gap-2.5 rounded-md border border-copper-br bg-copper-bg px-3 py-2.5 transition-colors hover:brightness-[0.98]"
                >
                  <IconDownload className="mt-0.5 text-copper-700" />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-steel-900">
                      Örnek metrajı indir
                    </span>
                    <span className="block text-xs text-steel-600">
                      Yüklenebilir · 18 satır · 4 onay bekleyen satır · AI
                      önerisini test eder · .xlsx
                    </span>
                  </span>
                </a>
              )}

              <Alert tone="info" title="Şablon ile örnek aynı şey değil" icon={<IconInfo />}>
                <span className="block">
                  <span className="font-medium">Şablon</span> (yukarıdaki
                  “Şablonu indir”) boş bir başlangıç dosyasıdır; satırları
                  kasıtlı olarak ya tam tanımlı ya geçersizdir, bu yüzden AI’ya
                  iş bırakmaz.
                </span>
                <span className="mt-1 block">
                  <span className="font-medium">Örnek metraj</span> ise gerçek
                  bir dosyadır: 4 satır onay bekler, AI önerisi ve kapsam dışı
                  davranışı burada görülür.
                </span>
              </Alert>

              <div className="space-y-2">
                <p className="text-label tracking-[0.08em] text-steel-500 uppercase">
                  Örnek raporlar
                </p>
                {DEMO_REPORTS.map((file) => (
                  <a
                    key={file.name}
                    href={file.href}
                    {...(file.action === 'download'
                      ? { download: file.name }
                      : { target: '_blank', rel: 'noopener noreferrer' })}
                    className="flex items-center justify-between gap-2 text-sm text-steel-700 underline underline-offset-2 hover:text-copper-700"
                  >
                    <span>{file.label}</span>
                    <span className="font-mono text-xs text-steel-500">
                      {file.format}
                    </span>
                  </a>
                ))}
              </div>

              <p className="text-xs text-steel-500">
                Bu dosyalar örnek çıktıdır; yükleme akışı yalnızca metraj
                dosyasını kabul eder.
              </p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Dosya işleme" />
            <CardBody className="space-y-2.5">
              <p className="text-sm text-steel-600">
                Dosya sunucuda analiz edilir ve işlem sonunda geçici dosya
                silinir. Analiz sonucu sunucuda saklanmaz.
              </p>
              <p className="text-xs text-steel-500">
                {analyzeView?.aiEnabled
                  ? 'AI yalnızca onay bekleyen satırlar için öneri üretir; öneri otomatik onaylanmaz.'
                  : 'AI önerileri isteğe bağlıdır; kapalıyken hiçbir ağ çağrısı yapılmaz ve belirsiz satırlar sizin kararınıza düşer.'}
              </p>
              {analyzeView && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full"
                  onClick={reset}
                >
                  Yeni dosya ile başla
                </Button>
              )}
            </CardBody>
          </Card>
        </div>
      </div>

      <ActionBar
        hint={
          isAnalyzing
            ? 'Dosya analiz ediliyor…'
            : analyzeView
              ? `${analyzeView.summary.total} satır analiz edildi`
              : 'Dosya seçilmedi · analiz başlatılmadı'
        }
      >
        <Link
          to="/"
          className="inline-flex h-10 items-center gap-2 rounded-md border border-steel-300 bg-white px-4 text-body font-medium text-steel-800 transition-colors hover:bg-steel-50"
        >
          Ana sayfa
        </Link>
        <Button
          variant="primary"
          trailingIcon={<IconArrowRight />}
          disabled={!analyzeView}
          onClick={() => {
            if (analyzeView) navigate('/analysis')
          }}
        >
          Analize geç
        </Button>
      </ActionBar>

      <p className="mt-4 text-center text-xs text-steel-500">
        Ana sayfaya{' '}
        <Link to="/" className="text-steel-700 underline underline-offset-2">
          dönebilirsiniz
        </Link>
        .
      </p>
    </AppShell>
  )
}
