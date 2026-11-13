import { useEffect, useState } from 'react'

import { formatConfidence, formatQuantity, formatWaste } from '../../lib/format'
import { aiSuggestionView, decisionCapability, EXCLUSION_LABEL, type ReviewRow } from '../../types/workflow'
import { STATUS_META } from '../../lib/ui'
import { Button } from '../ui/Button'
import { Drawer } from '../ui/Drawer'
import { RadioCard } from '../ui/Fields'
import { Alert, Badge } from '../ui/Status'
import { IconAlert, IconInfo } from '../ui/icons'
import { describeCode } from '../../lib/labels'

/**
 * Eşleşme detay paneli — gerçek analiz verisiyle.
 *
 * Ayrım kuralı: deterministik eşleşme (`match`) ile AI önerisi (`ai`) hiçbir
 * zaman aynı görsel ağırlıkta sunulmaz. AI önerisi "öneri" olarak etiketlenir,
 * varsayılan seçili gelmez ve tek başına onay anlamına gelmez.
 *
 * Onay bekleyen satırda hiçbir aday varsayılan seçili değildir: kullanıcı
 * bilinçli olarak seçmeden "Onayla" etkinleşmez.
 */
export function MatchDrawer({
  row,
  onClose,
  onApprove,
  onReject,
  onClearDecision,
}: {
  row: ReviewRow | null
  onClose: () => void
  onApprove: (boqNo: string, code: string) => void
  onReject: (boqNo: string) => void
  onClearDecision: (boqNo: string) => void
}) {
  const [selected, setSelected] = useState<string | null>(null)
  const [customCode, setCustomCode] = useState('')

  const boqNo = row?.row.boq_no ?? null

  // Satır değişince seçim sıfırlanır: başka satırın kararı taşınmaz.
  useEffect(() => {
    setSelected(row?.matchedCode ?? null)
    setCustomCode('')
  }, [row?.row.source_row, row?.matchedCode])

  const meta = row ? STATUS_META[row.status] : null
  const capability = row ? decisionCapability(row) : null
  const ai = aiSuggestionView(row?.row.ai ?? null)

  const candidates = capability?.candidates ?? []
  const aiCode =
    ai.kind === 'suggested' && ai.code && !candidates.some((c) => c.code === ai.code)
      ? ai.code
      : null

  const effectiveCode = customCode.trim() || selected

  return (
    <Drawer
      open={Boolean(row)}
      onClose={onClose}
      title={row ? (row.row.boq_no ?? `Excel satırı ${row.row.source_row}`) : ''}
      subtitle={
        row ? (
          <span className="font-mono">
            Excel satırı {row.row.source_row}
          </span>
        ) : undefined
      }
      footer={
        row && capability ? (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  if (boqNo) onReject(boqNo)
                  onClose()
                }}
                disabled={!capability.canDecide}
              >
                Reddet
              </Button>
              {capability.canReset && boqNo && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    onClearDecision(boqNo)
                    setSelected(null)
                    setCustomCode('')
                  }}
                >
                  Kararı geri al
                </Button>
              )}
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-steel-500">
                {capability.canDecide
                  ? effectiveCode
                    ? 'Seçim hazır'
                    : 'Önce bir aday seçin'
                  : 'Karar verildi'}
              </span>
              <Button
                variant="primary"
                size="sm"
                disabled={!capability.canDecide || !effectiveCode}
                onClick={() => {
                  if (!boqNo || !effectiveCode) return
                  onApprove(boqNo, effectiveCode)
                  onClose()
                }}
              >
                Onayla
              </Button>
            </div>
          </div>
        ) : undefined
      }
    >
      {row && meta && capability && (
        <div className="space-y-4">
          {/* Durum ve kaynak veri */}
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={meta.tone}>{meta.label}</Badge>
            {row.row.ai?.suggestion && (
              <Badge tone="copper">AI değerlendirmesi var</Badge>
            )}
          </div>

          <p className="text-sm text-steel-600">{meta.hint}</p>

          <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 rounded-md border border-steel-200 bg-steel-50 px-3.5 py-3">
            <div>
              <dt className="text-label tracking-[0.06em] text-steel-500 uppercase">
                Metraj miktarı
              </dt>
              <dd className="tabular mt-0.5 font-mono text-body text-steel-900">
                {formatQuantity(row.row.quantity, row.row.unit)}
              </dd>
            </div>
            <div>
              <dt className="text-label tracking-[0.06em] text-steel-500 uppercase">
                Fire
              </dt>
              <dd className="tabular mt-0.5 font-mono text-body text-steel-900">
                {formatWaste(row.row.waste_percent)}
              </dd>
            </div>
          </dl>

          {/* Açıklama */}
          <div>
            <p className="text-label tracking-[0.08em] text-steel-500 uppercase">
              Açıklama
            </p>
            <p className="mt-1 font-mono text-sm text-steel-800">
              {row.row.description ?? '—'}
            </p>
          </div>

          {/* Deterministik eşleşme */}
          <section className="rounded-md border border-steel-200 bg-white px-3.5 py-3">
            <p className="text-label tracking-[0.06em] text-steel-500 uppercase">
              Deterministik sonuç
            </p>
            <p className="mt-1 text-sm text-steel-700">
              {row.row.match.message || 'Sunucu ek açıklama döndürmedi.'}
            </p>
            {row.row.match.matched_code && (
              <p className="mt-1.5 text-body font-medium text-steel-900">
                {describeCode(row.row, row.row.match.matched_code)}
                <span className="ml-2 font-mono text-xs text-steel-500">
                  {row.row.match.matched_code}
                </span>
              </p>
            )}
          </section>

          {/* AI önerisi — ayrı ve "öneri" olarak */}
          {ai.kind === 'suggested' && (
            <section className="rounded-md border border-copper-200 bg-copper-50/60 px-3.5 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-label tracking-[0.06em] text-copper-700 uppercase">
                  AI önerisi · onay gerekir
                </p>
                <Badge tone="copper">
                  güven: {formatConfidence(ai.confidence)}
                </Badge>
              </div>
              <p className="mt-1.5 text-body font-medium text-steel-900">
                {describeCode(row.row, ai.code)}
                <span className="ml-2 font-mono text-xs text-steel-500">
                  {ai.code}
                </span>
              </p>
              <p className="mt-1 text-sm text-steel-600">{ai.reason}</p>
              <p className="mt-2 text-xs text-steel-600">
                Öneri otomatik onaylanmaz; hesaba girmesi için bir aday seçip
                onaylamanız gerekir.
              </p>
            </section>
          )}

          {ai.kind === 'ambiguous' && (
            <Alert tone="warning" title="AI karar veremedi" icon={<IconAlert />}>
              {ai.reason || 'Açıklama birden fazla kaleme uyuyor.'}
            </Alert>
          )}

          {ai.kind === 'no_match' && (
            <Alert tone="neutral" title="AI eşleşme bulamadı" icon={<IconInfo />}>
              {ai.reason || 'Katalogda uygun kalem bulunamadı.'}
            </Alert>
          )}

          {ai.kind === 'error' && (
            <Alert
              tone="warning"
              title="AI önerisi kullanılamadı"
              icon={<IconAlert />}
            >
              <p>{ai.message}</p>
              <p className="mt-1 text-xs opacity-80">
                Analiz durmadı; satır kullanıcı onayı bekliyor.
              </p>
            </Alert>
          )}

          {/* Adaylar — deterministik adaylar */}
          {candidates.length > 0 && (
            <section>
              <h3 className="text-label tracking-[0.08em] text-steel-500 uppercase">
                {capability.canDecide
                  ? 'Katalog adayları'
                  : 'Değerlendirilen adaylar'}
              </h3>

              <div className="mt-2 space-y-2">
                {candidates.map((candidate) => {
                  const isAiSuggested = ai.kind === 'suggested' && ai.code === candidate.code
                  return (
                    <RadioCard
                      key={candidate.code}
                      name={`candidate-${row.row.source_row}`}
                      checked={selected === candidate.code && !customCode.trim()}
                      disabled={!capability.canDecide}
                      onChange={() => {
                        setSelected(candidate.code)
                        setCustomCode('')
                      }}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-mono text-xs text-steel-500">
                          {candidate.code}
                        </span>
                        <span className="flex flex-wrap items-center gap-1.5">
                          {isAiSuggested && <Badge tone="copper">AI önerisi</Badge>}
                          {candidate.mass_kg_per_m && (
                            <Badge tone="neutral">
                              {candidate.mass_kg_per_m} kg/m
                            </Badge>
                          )}
                        </span>
                      </div>
                      <p className="mt-1 text-body font-medium text-steel-900">
                        {candidate.label}
                      </p>
                      {candidate.commercial_length_m && (
                        <p className="mt-1 text-xs text-steel-500">
                          Ticari boy: {candidate.commercial_length_m} m
                        </p>
                      )}
                    </RadioCard>
                  )
                })}

                {aiCode && capability.canDecide && (
                  <RadioCard
                    name={`candidate-${row.row.source_row}`}
                    checked={selected === aiCode && !customCode.trim()}
                    disabled={!capability.canDecide}
                    onChange={() => {
                      setSelected(aiCode)
                      setCustomCode('')
                    }}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-mono text-xs text-steel-500">
                        {aiCode}
                      </span>
                      <Badge tone="copper">AI önerisi</Badge>
                    </div>
                    <p className="mt-1 text-body font-medium text-steel-900">
                      {describeCode(row.row, aiCode)}
                    </p>
                  </RadioCard>
                )}
              </div>
            </section>
          )}

          {/* Alternatif katalog kodu — sunucu doğrular */}
          {capability.canDecide && (
            <section>
              <label
                htmlFor={`custom-code-${row.row.source_row}`}
                className="text-label tracking-[0.08em] text-steel-500 uppercase"
              >
                Katalogdan başka bir kod
              </label>
              <input
                id={`custom-code-${row.row.source_row}`}
                type="text"
                value={customCode}
                onChange={(event) => {
                  setCustomCode(event.target.value)
                  if (event.target.value.trim()) setSelected(null)
                }}
                placeholder="ör. BOX-100-4-S235-B"
                className="mt-1.5 h-9 w-full rounded-md border border-steel-300 bg-white px-2.5 font-mono text-sm text-steel-900 placeholder:text-steel-500 focus:border-steel-400 focus:outline-none"
                spellCheck={false}
                autoComplete="off"
              />
              <p className="mt-1 text-xs text-steel-500">
                Kod katalogda yoksa veya açıklamayla çelişiyorsa sunucu isteği
                reddeder.
              </p>
            </section>
          )}

          {/* Hariç tutulma nedeni */}
          {row.row.match.exclusion_reason && (
            <Alert
              tone="warning"
              title="Hesaba katılmıyor"
              icon={<IconAlert />}
            >
              <span className="font-medium">
                {EXCLUSION_LABEL[row.row.match.exclusion_reason]}.
              </span>{' '}
              {row.row.match.message}
            </Alert>
          )}

          {/* Satır uyarıları */}
          {row.row.issues.length > 0 && (
            <Alert tone="danger" title="Satır uyarıları" icon={<IconAlert />}>
              <ul className="space-y-1.5">
                {row.row.issues.map((issue, index) => (
                  <li key={`${issue.code}-${index}`}>
                    <span className="font-medium">{issue.column ?? 'Satır'}:</span>{' '}
                    {issue.message}
                    {issue.suggestion && (
                      <span className="block text-xs opacity-80">
                        {issue.suggestion}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </Alert>
          )}

          {/* Sunucu notları */}
          {row.row.notes.length > 0 && (
            <Alert tone="neutral" title="Not" icon={<IconInfo />}>
              <ul className="space-y-1">
                {row.row.notes.map((note, index) => (
                  <li key={`${note}-${index}`}>{note}</li>
                ))}
              </ul>
            </Alert>
          )}

          {/* Değişmez güvenlik notları */}
          <div className="space-y-1.5 rounded-md border border-dashed border-steel-300 px-3.5 py-3">
            <p className="text-xs text-steel-600">
              Öneri güveni kalibre edilmiş bir doğruluk oranı değildir; yalnızca
              açıklamanın katalogla örtüşme derecesini gösterir.
            </p>
            <p className="text-xs text-steel-600">
              Miktar AI eşleştirmesine gönderilmez ve AI hiçbir hesaplanmış
              değeri değiştirmez. Nihai hesap sunucuda yapılır.
            </p>
          </div>
        </div>
      )}
    </Drawer>
  )
}
