import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ActionBar, AppShell, PageHeader } from '../components/layout/AppShell'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { Alert, Badge, EmptyState } from '../components/ui/Status'
import { IconAlert, IconArrowRight, IconInfo, IconUpload } from '../components/ui/icons'
import { ApiErrorNotice, WarningList } from '../components/workflow/ApiErrorNotice'
import { PurchaseListTable } from '../components/workflow/PurchaseListTable'
import { formatDecimal } from '../lib/format'
import { SKIP_LABEL, cn } from '../lib/ui'
import { useWorkflow } from '../state/WorkflowContext'
import type { StatusCounts } from '../types/workflow'

/**
 * Karar özeti — sıfır olan kalemleri hiç yazmaz.
 *
 * "0 onay bekliyor, 0 reddedildi" gibi gürültü yerine yalnızca gerçekten
 * gerçekleşmiş kararlar listelenir. Tüm sayaçlar sıfırsa açık bir metin döner.
 */
function decisionSummary(counts: StatusCounts): string {
  const parts: string[] = []

  if (counts.rule > 0) parts.push(`${counts.rule} kural`)
  if (counts['ai-approved'] > 0) parts.push(`${counts['ai-approved']} kullanıcı onayı`)
  if (counts.pending > 0) parts.push(`${counts.pending} onay bekliyor`)
  if (counts.rejected > 0) parts.push(`${counts.rejected} reddedildi`)
  if (counts.excluded > 0) parts.push(`${counts.excluded} hariç`)
  if (counts.invalid > 0) parts.push(`${counts.invalid} geçersiz`)

  return parts.length > 0 ? parts.join(', ') : 'karar bekleyen satır yok'
}

/**
 * Results — 04.
 *
 * `/api/calculate` yanıtını gösterir. Hiçbir değer istemcide hesaplanmaz:
 * brüt, sipariş boyu, ağırlık ve artan boy doğrudan sunucudan gelir.
 * FULL/PARTIAL durumu grup düzeyinde ve özet düzeyinde açıkça gösterilir.
 */
export default function ResultsPage() {
  const navigate = useNavigate()
  const {
    calculation,
    analyzeView,
    unsendable,
    counts,
    heldCount,
    error,
    stage,
    runCalculation,
  } = useWorkflow()

  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [retrying, setRetrying] = useState(false)

  const toggle = (code: string) => {
    setExpanded((previous) => {
      const next = new Set(previous)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }

  if (!calculation) {
    return (
      <AppShell current="results">
        <PageHeader
          stepNo="04"
          title="Satın alma listesi"
          description="Hesaplama sonucu burada gösterilir."
        />
        {error && error.stage === 'calculate' && (
          <ApiErrorNotice error={error} className="mb-4" />
        )}
        <div className="rounded-lg border border-steel-200 bg-white">
          <EmptyState
            title={
              analyzeView
                ? 'Hesaplama henüz çalıştırılmadı'
                : 'Gösterilecek sonuç yok'
            }
            description={
              analyzeView
                ? 'Kararlarınızı gönderip satın alma listesini üretin.'
                : 'Önce bir metraj dosyası yükleyin ve analizi tamamlayın.'
            }
            icon={<IconUpload className="size-6" />}
            action={
              <Button
                variant="primary"
                disabled={stage === 'calculating'}
                onClick={async () => {
                  if (!analyzeView) {
                    navigate('/upload')
                    return
                  }
                  await runCalculation()
                }}
              >
                {analyzeView ? 'Hesapla' : 'Metraj yükle'}
              </Button>
            }
          />
        </div>
      </AppShell>
    )
  }

  const { summary, groups, skipped, warnings } = calculation

  // İki ayrı kavram — karıştırılmamalı:
  // 1. KISMİ: yalnızca ağırlığı hesaplanamayan (PARTIAL) grup varsa.
  // 2. Hesap dışı satır: hesaba katılmayan satır var; raporda ayrı bölümde
  //    listelenir, ağırlık toplamını KISMİ yapmaz.
  // Aynı ayrım `ExportPage` içinde de korunur.
  const hasPartialGroups = summary.partial_groups > 0
  const hasSkippedRows = summary.skipped_rows > 0
  const hasWarning = hasPartialGroups || hasSkippedRows

  return (
    <AppShell current="results">
      <PageHeader
        stepNo="04"
        title="Satın alma listesi"
        description="Sunucunun hesapladığı nihai liste. Miktarlar fire ve ticari boy kurallarıyla üretildi."
        badge={
          <Badge tone={hasWarning ? 'warning' : 'success'}>
            {hasPartialGroups
              ? 'Kısmi ağırlık'
              : hasSkippedRows
                ? 'Hesap dışı satır var'
                : 'Tam sonuç'}
          </Badge>
        }
      />

      {error && error.stage === 'calculate' && (
        <ApiErrorNotice error={error} className="mb-4" />
      )}

      {/* Liste durumu — tek baskın sinyal. KISMİ yalnızca ağırlık içindir. */}
      <div
        className={
          hasWarning
            ? 'mb-4 flex flex-wrap items-start gap-3 rounded-lg border border-warning-br bg-warning-bg px-4 py-3'
            : 'mb-4 flex flex-wrap items-start gap-3 rounded-lg border border-success-br bg-success-bg px-4 py-3'
        }
      >
        <IconAlert
          className={hasWarning ? 'mt-0.5 text-warning-fg' : 'mt-0.5 text-success-fg'}
        />
        <div className="min-w-0 flex-1">
          <p
            className={
              hasWarning
                ? 'text-body font-semibold text-warning-fg'
                : 'text-body font-semibold text-success-fg'
            }
          >
            {hasPartialGroups
              ? 'KISMİ AĞIRLIK'
              : hasSkippedRows
                ? 'HESAP DIŞI SATIR VAR'
                : 'TAM LİSTE'}
          </p>
          <p className="mt-0.5 text-sm text-steel-700">
            {hasPartialGroups && hasSkippedRows
              ? `${summary.partial_groups} grupta eksik veri var; ağırlığı hesaplanamayan gruplar toplama dahil edilmez. Ayrıca ${summary.skipped_rows} satır hesaba katılmadı ve raporda "Hesaba Alınmayanlar" bölümünde listelenir. Eksik değerler "—" olarak gösterilir; sıfır sayılmaz.`
              : hasPartialGroups
                ? `${summary.partial_groups} grupta eksik veri var; ağırlığı hesaplanamayan gruplar toplama dahil edilmez. Eksik değerler "—" olarak gösterilir; sıfır sayılmaz.`
                : hasSkippedRows
                  ? `${summary.skipped_rows} satır hesaba katılmadı ve raporda "Hesaba Alınmayanlar" bölümünde nedenleriyle listelenir. Tüm gruplar tam veriyle hesaplandı; ağırlık toplamı KISMİ değildir.`
                  : 'Tüm satırlar hesaba katıldı ve tam veriyle hesaplandı.'}
          </p>
        </div>
        {stage === 'done' && (
          <Button
            variant="secondary"
            size="sm"
            disabled={retrying}
            onClick={async () => {
              setRetrying(true)
              await runCalculation()
              setRetrying(false)
            }}
          >
            Yeniden hesapla
          </Button>
        )}
      </div>

      {/* Özet */}
      <div className="mb-4 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-steel-600">
        <span>
          <span className="tabular font-mono text-steel-900">
            {summary.input_rows}
          </span>{' '}
          satır gönderildi
        </span>
        <span aria-hidden className="text-steel-300">·</span>
        <span>
          <span className="tabular font-mono text-steel-900">
            {summary.calculated_rows}
          </span>{' '}
          hesaba girdi
        </span>
        <span aria-hidden className="text-steel-300">·</span>
        <span>
          <span className="tabular font-mono text-steel-900">
            {summary.groups}
          </span>{' '}
          malzeme grubu
        </span>
        <span aria-hidden className="text-steel-300">·</span>
        <span>
          <span className="tabular font-mono text-steel-900">
            {summary.merges}
          </span>{' '}
          birleşme
        </span>
        <span aria-hidden className="text-steel-300">·</span>
        <span>
          <span className="tabular font-mono text-steel-900">
            {summary.full_groups}
          </span>
          {" / "}
          <span className="tabular font-mono text-warning-fg">
            {summary.partial_groups}
          </span>{' '}
          TAM / KISMİ
        </span>
        <span aria-hidden className="text-steel-300">·</span>
        <span>
          <span className="tabular font-mono text-steel-900">
            {summary.skipped_rows}
          </span>{' '}
          hariç
        </span>
      </div>

      {/* Toplamlar — yalnızca sunucunun hesapladığı değerler */}
      <div className="mb-5 grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-steel-200 bg-white px-4 py-3">
          <p className="text-label tracking-[0.08em] text-steel-500 uppercase">
            Toplam sipariş boyu
          </p>
          <p className="tabular mt-1 font-mono text-h2 text-steel-900">
            {formatDecimal(summary.total_order_length_m, {
              precise: true,
              suffix: 'm',
            })}
          </p>
          <p className="mt-0.5 text-xs text-steel-500">
            Ticari boy yuvarlaması uygulanmış sipariş uzunluğu.
          </p>
        </div>
        <div className="rounded-lg border border-steel-200 bg-white px-4 py-3">
          <p className="text-label tracking-[0.08em] text-steel-500 uppercase">
            Bilinen toplam ağırlık
          </p>
          <p className="tabular mt-1 font-mono text-h2 text-steel-900">
            {formatDecimal(summary.known_weight_kg, {
              precise: true,
              suffix: 'kg',
            })}
          </p>
          <p
            className={cn(
              'mt-0.5 text-xs',
              summary.weight_complete ? 'text-steel-500' : 'text-warning-fg',
            )}
          >
            {summary.weight_complete
              ? 'Tüm grupların ağırlığı hesaplandı. Teorik çıplak çelik ağırlığı.'
              : 'Kısmi toplam: ağırlığı hesaplanamayan gruplar dahil edilmedi.'}
          </p>
        </div>
      </div>

      {warnings.length > 0 && (
        <div className="mb-5">
          <WarningList warnings={warnings} title="Hesaplama uyarıları" />
        </div>
      )}

      {/* Malzeme grupları */}
      <Card>
        <CardHeader
          title="Malzeme grupları"
          description="Satır detayında dönüşüm izi ve kaynak BOQ satırları görünür."
          action={
            <Badge tone="neutral">
              {groups.length} grup · {summary.calculated_rows} kaynak satır
            </Badge>
          }
        />
        {groups.length === 0 ? (
          <EmptyState
            title="Satın alma kalemi oluşmadı"
            description="Onaylanmış satır yok. Eşleştirme ekranında en az bir satırı onaylayın."
            icon={<IconAlert className="size-6" />}
            action={
              <Link
                to="/review"
                className="inline-flex h-10 items-center gap-2 rounded-md border border-steel-300 bg-white px-4 text-body font-medium text-steel-800 transition-colors hover:bg-steel-50"
              >
                Eşleştirmeye git
              </Link>
            }
          />
        ) : (
          <PurchaseListTable
            groups={groups}
            expanded={expanded}
            onToggle={toggle}
          />
        )}
        <CardBody className="border-t border-steel-100 py-3">
          <p className="text-xs text-steel-500">
            Ağırlık <span className="font-medium text-steel-700">teorik çıplak
            çelik</span> ağırlığıdır; galvaniz kaplama ve tedarikçi kantar
            farkları dahil değildir. Kesim optimizasyonu yapılmamıştır.
          </p>
        </CardBody>
      </Card>

      {/* Hesaba girmeyen satırlar */}
      {(skipped.length > 0 || unsendable.length > 0) && (
        <Card className="mt-5">
          <CardHeader
            title="Listeye girmeyen satırlar"
            description="Her satırın nedeni ayrı gösterilir; hiçbir satır sessizce düşürülmez."
            action={
              <Badge tone="warning">
                {skipped.length + unsendable.length} satır
              </Badge>
            }
          />
          <ul className="divide-y divide-steel-100">
            {skipped.map((row) => (
              <li
                key={`skip-${row.boq_no}-${row.source_row ?? 'yok'}`}
                className="flex flex-wrap gap-x-3 gap-y-1.5 px-5 py-3"
              >
                <span className="w-24 shrink-0 font-mono text-xs whitespace-nowrap text-steel-700">
                  {row.boq_no}
                  {row.source_row !== null && (
                    <span className="ml-1 text-steel-400">s{row.source_row}</span>
                  )}
                </span>
                <span className="min-w-0 flex-1 text-sm text-steel-800">
                  {row.message}
                </span>
                <Badge tone="warning" className="shrink-0">
                  {SKIP_LABEL[row.status] ?? row.status}
                </Badge>
              </li>
            ))}

            {unsendable.map((row) => (
              <li
                key={`unsendable-${row.boq_no}-${row.source_row ?? 'yok'}`}
                className="flex flex-wrap gap-x-3 gap-y-1.5 px-5 py-3"
              >
                <span className="w-24 shrink-0 font-mono text-xs whitespace-nowrap text-steel-700">
                  {row.boq_no}
                  {row.source_row !== null && (
                    <span className="ml-1 text-steel-400">s{row.source_row}</span>
                  )}
                </span>
                <span className="min-w-0 flex-1 text-sm text-steel-800">
                  {row.message}
                </span>
                <Badge tone="danger" className="shrink-0">
                  {row.status === 'invalid' ? 'Geçersiz' : 'Gönderilemedi'}
                </Badge>
              </li>
            ))}
          </ul>
          <CardBody className="border-t border-steel-100 py-3">
            <div className="flex items-start gap-2">
              <IconInfo className="mt-0.5 shrink-0 text-steel-500" />
              <p className="text-xs text-steel-600">
                Onay bekleyen satırı{' '}
                <Link to="/review" className="underline underline-offset-2">
                  eşleştirme ekranında
                </Link>{' '}
                onaylarsanız listeye dahil olur; sonucu yeniden hesaplamanız
                gerekir.
              </p>
            </div>
          </CardBody>
        </Card>
      )}

      <Alert tone="neutral" icon={<IconInfo />} className="mt-5">
        <p className="text-sm text-steel-700">
          <span className="font-semibold">Bu bir satın alma listesidir.</span>{' '}
          Aynı koda düşen satırlar birleştirildi, fire uygulandı ve sipariş boyu
          ticari boya yuvarlandı. Fiyat, tedarikçi ve kesim optimizasyonu bu
          sürümün kapsamı dışındadır.
        </p>
      </Alert>

      <p className="mt-3 text-xs text-steel-500">
        Karar özeti: {decisionSummary(counts)}. Hesap dışı toplam: {heldCount}.
      </p>

      <ActionBar hint="Sunucu hesaplaması tamamlandı · rapor indirilebilir">
        <Link
          to="/review"
          className="inline-flex h-10 items-center gap-2 rounded-md border border-steel-300 bg-white px-4 text-body font-medium text-steel-800 transition-colors hover:bg-steel-50"
        >
          Geri
        </Link>
        <Button
          variant="primary"
          trailingIcon={<IconArrowRight />}
          onClick={() => navigate('/export')}
        >
          Dışa aktarmaya geç
        </Button>
      </ActionBar>
    </AppShell>
  )
}
