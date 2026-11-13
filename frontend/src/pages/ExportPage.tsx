import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { ActionBar, AppShell, PageHeader } from '../components/layout/AppShell'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { Alert, Badge, EmptyState } from '../components/ui/Status'
import {
  IconAlert,
  IconCheck,
  IconFile,
  IconInfo,
  IconUpload,
} from '../components/ui/icons'
import { ApiErrorNotice } from '../components/workflow/ApiErrorNotice'
import { downloadReport, triggerDownload, type ReportKind } from '../lib/api'
import { formatDecimal, formatQuantity } from '../lib/format'
import { useWorkflow, toWorkflowError, type WorkflowError } from '../state/WorkflowContext'

/**
 * Export — 05.
 *
 * Excel/PDF raporu `/api/report/{kind}` üzerinden indirilir. Gövde
 * `/api/calculate` ile aynıdır: sunucu raporu aynı hesaplama çekirdeğinden
 * üretir, istemci dosya oluşturmaz.
 */

type DownloadState = 'idle' | 'working' | 'done'

export default function ExportPage() {
  const { calculation, calculationRequest, analyzeView, summaryError } =
    useWorkflowSafe()

  const [states, setStates] = useState<Record<ReportKind, DownloadState>>({
    excel: 'idle',
    pdf: 'idle',
  })
  const [errors, setErrors] = useState<
    Partial<Record<ReportKind, WorkflowError>>
  >({})
  const [lastFile, setLastFile] = useState<
    Partial<Record<ReportKind, string>>
  >({})

  const isPartial =
    calculation !== null &&
    (calculation.summary.partial_groups > 0 ||
      calculation.summary.skipped_rows > 0)

  // Raporun gerçek davranışı (backend `app/reports/`): KISMİ ibaresi yalnızca
  // *ağırlığı* hesaplanamayan grup varsa basılır. Atlanan satırlar raporda
  // ayrı bir bölümde ("Hesaba Alınmayanlar") nedenleriyle listelenir; bu,
  // ağırlık toplamını KISMİ yapmaz. Bu ayrım kullanıcıya yanlış vaat
  // verilmemesi için metinlerde korunur.
  const hasPartialGroups = calculation?.summary.partial_groups
    ? calculation.summary.partial_groups > 0
    : false

  const download = async (kind: ReportKind) => {
    if (!calculationRequest) return

    setStates((previous) => ({ ...previous, [kind]: 'working' }))
    setErrors((previous) => {
      const next = { ...previous }
      delete next[kind]
      return next
    })

    try {
      const result = await downloadReport(kind, calculationRequest)
      triggerDownload(result)
      setStates((previous) => ({ ...previous, [kind]: 'done' }))
      setLastFile((previous) => ({ ...previous, [kind]: result.filename }))
    } catch (error) {
      setStates((previous) => ({ ...previous, [kind]: 'idle' }))
      setErrors((previous) => ({
        ...previous,
        [kind]: toWorkflowError('report', error),
      }))
    }
  }

  if (!calculation || !calculationRequest) {
    return (
      <AppShell current="export">
        <PageHeader
          stepNo="05"
          title="Dışa aktarma"
          description="Satın alma listesini Excel veya PDF olarak indirin."
        />
        {summaryError && (
          <ApiErrorNotice error={summaryError} className="mb-4" />
        )}
        <div className="rounded-lg border border-steel-200 bg-white">
          <EmptyState
            title="İndirilecek rapor yok"
            description={
              analyzeView
                ? 'Önce hesaplamayı çalıştırın; rapor aynı sonuçtan üretilir.'
                : 'Önce bir metraj dosyası yükleyin ve hesaplamayı tamamlayın.'
            }
            icon={<IconUpload className="size-6" />}
            action={
              <Link
                to={analyzeView ? '/results' : '/upload'}
                className="inline-flex h-10 items-center gap-2 rounded-md border border-ink bg-ink px-4 text-body font-medium text-white transition-colors hover:bg-steel-800"
              >
                {analyzeView ? 'Sonuçlara git' : 'Metraj yükle'}
              </Link>
            }
          />
        </div>
      </AppShell>
    )
  }

  const { groups, summary } = calculation

  return (
    <AppShell current="export">
      <PageHeader
        stepNo="05"
        title="Dışa aktarma"
        description="Satın alma listesini Excel veya PDF olarak indirin. Dosyalar sunucuda üretilir."
        badge={
          <Badge tone={isPartial ? 'warning' : 'success'}>
            {hasPartialGroups
              ? 'Kısmi ağırlık'
              : isPartial
                ? 'Hesap dışı satır var'
                : 'Tam liste'}
          </Badge>
        }
      />

      {isPartial && (
        <Alert
          tone="warning"
          title={
            hasPartialGroups
              ? 'Rapor KISMİ ağırlık toplamı içerecek'
              : 'Raporda hesaba katılmayan satırlar var'
          }
          icon={<IconAlert />}
          className="mb-5"
        >
          {hasPartialGroups ? (
            <>
              {summary.partial_groups} grupta eksik veri var; ağırlığı
              hesaplanamayan gruplar toplama dahil edilmez ve rapor bunu açıkça
              KISMİ olarak işaretler. Eksik değerler boş bırakılır, sıfır
              yazılmaz.
              {summary.skipped_rows > 0 && (
                <> Ayrıca {summary.skipped_rows} satır hesaba katılmadı.</>
              )}
            </>
          ) : (
            <>
              {summary.skipped_rows} satır hesaba katılmadı. Bu satırlar raporda
              &quot;Hesaba Alınmayanlar&quot; bölümünde nedenleriyle listelenir;
              ağırlık toplamı etkilenmediği için rapor KISMİ sayılmaz.
            </>
          )}
        </Alert>
      )}

      <div className="grid gap-5 md:grid-cols-2">
        <ExportCard
          kind="excel"
          icon={<IconFile />}
          title="Excel çalışma kitabı"
          description="Biçimlendirilmiş çalışma kitabı: satın alma listesi, hesaplama izi ve hesaba girmeyen satırlar."
          contents={[
            'Satın alma sayfası — sunucunun hesapladığı değerler',
            'Hesaplama izi — kaynak BOQ satırları ve dönüşümler',
            'Hesaba girmeyen satırlar ve nedenleri',
            'Uyarılar ve varsayımlar',
          ]}
          state={states.excel}
          lastFile={lastFile.excel}
          error={errors.excel}
          onDownload={() => void download('excel')}
        />

        <ExportCard
          kind="pdf"
          icon={<IconFile />}
          title="PDF satın alma raporu"
          description="Kısa, okunabilir bir rapor; TAM / KISMİ durumu ve sınırlamalar açıkça belirtilir."
          contents={[
            'Özet ve TAM / KISMİ durumu',
            'Kalem tablosu — fire, sipariş boyu, ağırlık',
            'Kaynak satır izlenebilirliği',
            'Varsayımlar ve sınırlamalar',
          ]}
          state={states.pdf}
          lastFile={lastFile.pdf}
          error={errors.pdf}
          onDownload={() => void download('pdf')}
        />
      </div>

      {/* Rapor içeriği önizlemesi — sunucu verisinden */}
      <Card className="mt-5">
        <CardHeader
          title="Rapora girecek malzemeler"
          description={`${groups.length} grup · ${summary.calculated_rows} kaynak satır`}
          action={<Badge tone="neutral">{groups.length} kalem</Badge>}
        />
        {groups.length === 0 ? (
          <CardBody>
            <p className="text-sm text-steel-600">
              Onaylanmış malzeme yok; rapor üretilemez. Eşleştirme ekranında en az
              bir satırı onaylayın.
            </p>
          </CardBody>
        ) : (
          <ul className="divide-y divide-steel-100">
            {groups.map((group) => (
              <li
                key={group.code}
                className="flex flex-col gap-1 px-5 py-2.5 sm:flex-row sm:flex-wrap sm:items-baseline sm:gap-x-3"
              >
                <span className="font-mono text-xs text-steel-500">
                  {group.code}
                </span>
                <span className="min-w-0 flex-1 text-sm text-steel-800">
                  {group.product_label}
                </span>
                <Badge tone={group.status === 'FULL' ? 'success' : 'warning'}>
                  {group.status === 'FULL' ? 'TAM' : 'KISMİ'}
                </Badge>
                <span className="tabular text-xs whitespace-nowrap text-steel-600">
                  {formatQuantity(group.total_gross_metres, 'm')} brüt ·{' '}
                  {formatDecimal(group.weight_kg, { precise: true, suffix: 'kg' })}
                </span>
              </li>
            ))}
          </ul>
        )}
        <CardBody className="border-t border-steel-100 py-3">
          <p className="text-xs text-steel-500">
            Bu liste yalnızca önizlemedir; indirilen dosyayı sunucu üretir.
          </p>
        </CardBody>
      </Card>

      <Card className="mt-5">
        <CardHeader
          title="Her iki çıktıda yer alacak bilgiler"
          description="Bunlar süsleme değil, raporun doğru okunması için zorunlu."
        />
        <CardBody>
          <ul className="space-y-2.5">
            {[
              {
                tone: isPartial ? ('warning' as const) : ('success' as const),
                text: hasPartialGroups
                  ? `KISMİ ağırlık uyarısı görünür olacak — ${summary.partial_groups} grupta eksik veri var.`
                  : isPartial
                    ? `Hesaba katılmayan ${summary.skipped_rows} satır raporda nedenleriyle listelenecek.`
                    : 'TAM LİSTE ibaresi görünür olacak.',
              },
              {
                tone: 'neutral' as const,
                text: 'Ağırlıklar teorik çıplak çelik ağırlığıdır; galvaniz kaplama dahil değildir.',
              },
              {
                tone: 'neutral' as const,
                text: 'Kesim optimizasyonu yapılmamıştır; ticari boy yuvarlaması hesap motoru kuralına göre uygulanır.',
              },
              {
                tone: 'neutral' as const,
                text: 'AI önerileri yalnızca kullanıcı onayıyla listeye girer; AI hiçbir hesaplanmış değeri değiştirmez.',
              },
            ].map((item) => (
              <li key={item.text} className="flex items-start gap-2.5">
                <IconCheck className="mt-0.5 shrink-0 text-steel-500" />
                <span className="text-sm text-steel-700">{item.text}</span>
              </li>
            ))}
          </ul>
        </CardBody>
      </Card>

      <Alert tone="info" icon={<IconInfo />} className="mt-5">
        <p className="text-sm text-steel-700">
          Rapor indirme isteği, hesaplama ile <span className="font-semibold">aynı
          gövdeyi</span> gönderir. Sunucu kararları yeniden doğrular; geçersiz bir
          karar varsa dosya üretilmez ve hata gösterilir.
        </p>
      </Alert>

      <ActionBar hint="Dosyalar sunucuda üretilir · doğru MIME ve dosya adı">
        <Link
          to="/results"
          className="inline-flex h-10 items-center gap-2 rounded-md border border-steel-300 bg-white px-4 text-body font-medium text-steel-800 transition-colors hover:bg-steel-50"
        >
          Geri
        </Link>
        <Button
          variant="primary"
          icon={<IconFile />}
          disabled={states.excel === 'working' || groups.length === 0}
          onClick={() => void download('excel')}
        >
          {states.excel === 'working' ? 'Excel hazırlanıyor…' : 'Excel indir'}
        </Button>
        <Button
          variant="secondary"
          icon={<IconFile />}
          disabled={states.pdf === 'working' || groups.length === 0}
          onClick={() => void download('pdf')}
        >
          {states.pdf === 'working' ? 'PDF hazırlanıyor…' : 'PDF indir'}
        </Button>
      </ActionBar>

      <p className="mt-4 text-center text-xs text-steel-500">
        <Link to="/" className="text-steel-700 underline underline-offset-2">
          Ana sayfaya dön
        </Link>
      </p>
    </AppShell>
  )
}

/** Context'te rapor hatası yok; bağlantı hatasını genel hatadan okur. */
function useWorkflowSafe() {
  const workflow = useWorkflow()
  return { ...workflow, summaryError: workflow.error }
}

function ExportCard({
  icon,
  title,
  description,
  contents,
  state,
  lastFile,
  error,
  onDownload,
}: {
  kind: ReportKind
  icon: ReactNode
  title: string
  description: string
  contents: string[]
  state: DownloadState
  lastFile?: string
  error?: WorkflowError
  onDownload: () => void
}) {
  return (
    <Card>
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            <span className="text-steel-500">{icon}</span>
            {title}
          </span>
        }
        action={
          <Badge tone={state === 'done' ? 'success' : 'neutral'}>
            {state === 'working'
              ? 'Hazırlanıyor'
              : state === 'done'
                ? 'İndirildi'
                : 'Hazır'}
          </Badge>
        }
      />
      <CardBody className="space-y-3">
        <p className="text-sm text-steel-600">{description}</p>

        <ul className="space-y-1.5">
          {contents.map((item) => (
            <li key={item} className="flex items-start gap-2 text-sm text-steel-700">
              <span
                aria-hidden
                className="mt-1.5 size-1 shrink-0 rounded-full bg-steel-400"
              />
              {item}
            </li>
          ))}
        </ul>

        {error && <ApiErrorNotice error={error} />}

        {lastFile && state === 'done' && (
          <p className="rounded-md border border-success-br bg-success-bg px-3 py-2 text-xs text-success-fg">
            İndirildi: <span className="font-mono">{lastFile}</span>
          </p>
        )}

        <Button
          variant="secondary"
          size="sm"
          className="w-full"
          onClick={onDownload}
          disabled={state === 'working'}
        >
          {state === 'working' ? 'Hazırlanıyor…' : 'İndir'}
        </Button>
      </CardBody>
    </Card>
  )
}
