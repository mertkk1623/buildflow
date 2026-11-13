import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ActionBar, AppShell, PageHeader } from '../components/layout/AppShell'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { SegmentedControl, SearchInput } from '../components/ui/Fields'
import {
  Alert,
  Badge,
  EmptyState,
  StatusBar,
} from '../components/ui/Status'
import { TBody, TD, TH, THead, TR, TableShell } from '../components/ui/Table'
import { IconAlert, IconArrowRight, IconSearch, IconUpload } from '../components/ui/icons'
import { ApiErrorNotice } from '../components/workflow/ApiErrorNotice'
import { MatchDrawer } from '../components/workflow/MatchDrawer'
import { describeCode } from '../lib/labels'
import { formatQuantity, formatWaste } from '../lib/format'
import { STATUS_META, cn } from '../lib/ui'
import { useWorkflow } from '../state/WorkflowContext'
import type { ReviewRow, ReviewStatus } from '../types/workflow'

/**
 * Review — 03.
 *
 * Ürünün kalbi. Kullanıcı her satırın ne olduğunu görür ve belirsiz satırı
 * onaylar. Onaysız hiçbir satır hesaba girmez; AI önerisi tek başına yeterli
 * değildir.
 */

type Filter = 'all' | ReviewStatus

export default function ReviewPage() {
  const navigate = useNavigate()
  const {
    rows,
    counts,
    total,
    eligibleCount,
    analyzeView,
    approveRow,
    rejectRow,
    clearDecision,
    runCalculation,
    stage,
    error,
  } = useWorkflow()

  const [filter, setFilter] = useState<Filter>('all')
  const [search, setSearch] = useState('')
  const [activeSourceRow, setActiveSourceRow] = useState<number | null>(null)

  const visibleRows = useMemo(() => {
    const query = search.trim().toLocaleLowerCase('tr-TR')

    return rows.filter((entry) => {
      if (filter !== 'all' && entry.status !== filter) return false
      if (!query) return true

      return (
        (entry.row.boq_no ?? '').toLocaleLowerCase('tr-TR').includes(query) ||
        (entry.row.description ?? '')
          .toLocaleLowerCase('tr-TR')
          .includes(query) ||
        (entry.matchedCode ?? '').toLocaleLowerCase('tr-TR').includes(query)
      )
    })
  }, [rows, filter, search])

  const activeRow = activeSourceRow
    ? (rows.find((entry) => entry.row.source_row === activeSourceRow) ?? null)
    : null

  const pendingCount = counts.pending
  const isCalculating = stage === 'calculating'

  if (!analyzeView) {
    return (
      <AppShell current="review">
        <PageHeader
          stepNo="03"
          title="Eşleşme incelemesi"
          description="Kural eşleşmeleri hazır. Belirsiz satırlar sizin onayınızı bekler."
        />
        <div className="rounded-lg border border-steel-200 bg-white">
          <EmptyState
            title="İncelenecek satır yok"
            description="Önce bir metraj dosyası yükleyin; satırlar analiz edildikten sonra burada listelenir."
            icon={<IconUpload className="size-6" />}
            action={
              <Link
                to="/upload"
                className="inline-flex h-10 items-center gap-2 rounded-md border border-ink bg-ink px-4 text-body font-medium text-white transition-colors hover:bg-steel-800"
              >
                Metraj yükle
                <IconArrowRight />
              </Link>
            }
          />
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell current="review">
      <PageHeader
        stepNo="03"
        title="Eşleşme incelemesi"
        description="Kural eşleşmeleri hazır. Belirsiz satırlar sizin onayınızı bekler."
        actions={
          <span className="text-sm text-steel-600">
            <span className="tabular font-mono text-steel-900">
              {eligibleCount}
            </span>{' '}
            / {total} hesaba girecek
          </span>
        }
      />

      {error && error.stage === 'calculate' && (
        <ApiErrorNotice error={error} className="mb-4" />
      )}

      {/* Özet şerit */}
      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-steel-200 bg-white px-3.5 py-2.5">
        <span className="text-sm text-steel-600">
          <span className="tabular font-mono font-medium text-steel-900">
            {total}
          </span>{' '}
          satır
        </span>
        <span aria-hidden className="text-steel-300">·</span>
        <span className="text-sm text-steel-600">
          <span className="tabular font-mono text-success-fg">{counts.rule}</span>{' '}
          kural
        </span>
        <span aria-hidden className="text-steel-300">·</span>
        <span className="text-sm text-steel-600">
          <span className="tabular font-mono text-copper-700">
            {counts['ai-approved']}
          </span>{' '}
          onaylı
        </span>
        <span aria-hidden className="text-steel-300">·</span>
        <span className="text-sm text-steel-600">
          <span className="tabular font-mono text-warning-fg">{pendingCount}</span>{' '}
          onay bekliyor
        </span>
        <span aria-hidden className="text-steel-300">·</span>
        <span className="text-sm text-steel-600">
          <span className="tabular font-mono text-danger-fg">{counts.rejected}</span>{' '}
          reddedildi
        </span>
        <span aria-hidden className="text-steel-300">·</span>
        <span className="text-sm text-steel-600">
          <span className="tabular font-mono text-steel-700">{counts.excluded}</span>{' '}
          hariç
        </span>
        {counts.invalid > 0 && (
          <>
            <span aria-hidden className="text-steel-300">·</span>
            <span className="text-sm text-steel-600">
              <span className="tabular font-mono text-danger-fg">{counts.invalid}</span>{' '}
              geçersiz
            </span>
          </>
        )}
      </div>

      {pendingCount > 0 && (
        <Alert
          tone="warning"
          title={`${pendingCount} satır onayınızı bekliyor`}
          icon={<IconAlert />}
          className="mb-4"
        >
          Bu satırlar siz karar verene kadar hesaba katılmaz ve raporda{' '}
          <span className="font-semibold">Hesaba Alınmayanlar</span> bölümünde
          listelenir. Ağırlık toplamı yalnızca ağırlığı hesaplanamayan gruplar
          olduğunda KISMİ olur.
        </Alert>
      )}

      <Card>
        <CardHeader
          title="Metraj satırları"
          description="Satıra tıklayarak deterministik sonucu, AI önerisini ve adayları görün."
          action={
            <div className="flex flex-wrap items-center gap-2">
              <SearchInput
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="BOQ no veya açıklama ara…"
                className="w-56"
              />
            </div>
          }
        />

        <CardBody className="border-b border-steel-100 py-3">
          <SegmentedControl<Filter>
            label="Durum filtresi"
            value={filter}
            onChange={setFilter}
            options={[
              { value: 'all', label: 'Tümü', count: total },
              {
                value: 'rule',
                label: 'Kural',
                count: counts.rule,
                tone: 'success',
              },
              {
                value: 'ai-approved',
                label: 'Onaylı',
                count: counts['ai-approved'],
                tone: 'copper',
              },
              {
                value: 'pending',
                label: 'Onay bekliyor',
                count: counts.pending,
                tone: 'warning',
              },
              {
                value: 'rejected',
                label: 'Reddedildi',
                count: counts.rejected,
                tone: 'danger',
              },
              {
                value: 'excluded',
                label: 'Hariç',
                count: counts.excluded,
              },
              {
                value: 'invalid',
                label: 'Geçersiz',
                count: counts.invalid,
                tone: 'danger',
              },
            ]}
          />
        </CardBody>

        {visibleRows.length === 0 ? (
          <EmptyState
            title="Bu filtrede satır yok"
            description="Filtreyi değiştirin veya aramayı temizleyin."
            icon={<IconSearch className="size-6" />}
            action={
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setFilter('all')
                  setSearch('')
                }}
              >
                Filtreleri temizle
              </Button>
            }
          />
        ) : (
          <TableShell minWidth={980}>
            <THead>
              <TR>
                <TH>BOQ No</TH>
                <TH>Metraj açıklaması</TH>
                <TH>Eşleşme</TH>
                <TH>AI</TH>
                <TH align="right">Miktar</TH>
                <TH align="right">Fire</TH>
                <TH>Durum</TH>
              </TR>
            </THead>
            <TBody>
              {visibleRows.map((entry) => (
                <RowItem
                  key={`${entry.row.source_row}-${entry.row.boq_no ?? 'yok'}`}
                  entry={entry}
                  active={activeSourceRow === entry.row.source_row}
                  onOpen={() => setActiveSourceRow(entry.row.source_row)}
                />
              ))}
            </TBody>
          </TableShell>
        )}

        <CardBody className="border-t border-steel-100 py-3">
          <p className="text-xs text-steel-500">
            {visibleRows.length} satır gösteriliyor. Miktarlar metrajdaki orijinal
            değerlerdir; fire uygulanmamıştır. Nihai hesaplama sunucuda yapılır.
          </p>
        </CardBody>
      </Card>

      <ActionBar
        hint={
          isCalculating
            ? 'Sunucu hesaplıyor…'
            : pendingCount > 0
              ? `${pendingCount} satır onay bekliyor · onaysız satır hesaba girmez`
              : 'Tüm satırlar karara bağlandı'
        }
      >
        <Link
          to="/analysis"
          className="inline-flex h-10 items-center gap-2 rounded-md border border-steel-300 bg-white px-4 text-body font-medium text-steel-800 transition-colors hover:bg-steel-50"
        >
          Geri
        </Link>

        <Button
          variant={pendingCount > 0 ? 'secondary' : 'primary'}
          trailingIcon={<IconArrowRight />}
          disabled={isCalculating}
          onClick={async () => {
            const result = await runCalculation()
            if (result) navigate('/results')
          }}
        >
          {isCalculating
            ? 'Hesaplanıyor…'
            : pendingCount > 0
              ? 'Kısmi listeyle hesapla'
              : 'Hesapla ve sonuçlara geç'}
        </Button>
      </ActionBar>

      <MatchDrawer
        row={activeRow}
        onClose={() => setActiveSourceRow(null)}
        onApprove={approveRow}
        onReject={rejectRow}
        onClearDecision={clearDecision}
      />
    </AppShell>
  )
}

function RowItem({
  entry,
  active,
  onOpen,
}: {
  entry: ReviewRow
  active: boolean
  onOpen: () => void
}) {
  const meta = STATUS_META[entry.status]
  const row = entry.row
  const aiSuggestion = row.ai?.suggestion

  const aiLabel = (() => {
    if (!aiSuggestion) return null
    switch (aiSuggestion.status) {
      case 'suggested':
        return {
          tone: 'copper' as const,
          text: aiSuggestion.suggested_code
            ? describeCode(row, aiSuggestion.suggested_code)
            : 'Öneri',
        }
      case 'ambiguous':
        return { tone: 'warning' as const, text: 'Belirsiz' }
      case 'no_match':
        return { tone: 'neutral' as const, text: 'Eşleşme yok' }
      default:
        return null
    }
  })()

  const aiError = row.ai?.error

  const matchLabel = entry.matchedCode
    ? describeCode(row, entry.matchedCode)
    : row.match.candidates.length > 1
      ? `${row.match.candidates.length} aday`
      : row.match.candidates[0]
        ? describeCode(row, row.match.candidates[0].code)
        : '—'

  return (
    <TR
      interactive
      onClick={onOpen}
      className={cn(active && 'bg-copper-50/40')}
      aria-label={`${row.boq_no ?? row.source_row} detayını aç`}
    >
      <TD className="relative whitespace-nowrap">
        <StatusBar tone={meta.tone} />
        <span className="ml-1 font-mono text-xs text-steel-700">
          {row.boq_no ?? `#${row.source_row}`}
        </span>
        <span className="ml-1.5 font-mono text-[10px] text-steel-400">
          s{row.source_row}
        </span>
      </TD>
      <TD>
        <p className="text-steel-900">{row.description ?? '—'}</p>
        {row.match.message && (
          <p className="mt-0.5 line-clamp-1 text-xs text-steel-500">
            {row.match.message}
          </p>
        )}
      </TD>
      <TD>
        <p
          className={cn(
            'text-sm',
            entry.matchedCode ? 'text-steel-800' : 'text-steel-500',
          )}
        >
          {matchLabel}
        </p>
        {entry.matchedCode && (
          <p className="font-mono text-xs text-steel-500">{entry.matchedCode}</p>
        )}
        {entry.decision?.action === 'approve' && (
          <p className="mt-0.5 text-[10px] font-medium tracking-wide text-copper-700 uppercase">
            kullanıcı onayı
          </p>
        )}
      </TD>
      <TD>
        {aiLabel ? (
          <div className="space-y-0.5">
            <Badge tone={aiLabel.tone}>AI</Badge>
            <p className="line-clamp-1 text-xs text-steel-500">{aiLabel.text}</p>
          </div>
        ) : aiError ? (
          <Badge tone="warning">AI hatası</Badge>
        ) : (
          <span className="font-mono text-xs text-steel-400">—</span>
        )}
      </TD>
      <TD align="right" className="whitespace-nowrap">
        <span className="tabular font-mono text-xs text-steel-800">
          {formatQuantity(row.quantity, row.unit)}
        </span>
      </TD>
      <TD align="right" className="whitespace-nowrap">
        <span className="tabular font-mono text-xs text-steel-800">
          {formatWaste(row.waste_percent)}
        </span>
      </TD>
      <TD>
        <Badge tone={meta.tone}>{meta.short}</Badge>
      </TD>
    </TR>
  )
}
