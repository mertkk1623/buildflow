/**
 * Arayüz durum tipleri.
 *
 * Bu tipler **hesaplama sözleşmesi değildir**: sunucudan gelen `AnalyzeRow`
 * ile kullanıcı kararını birleştiren görünüm modelidir. Hesaplanmış hiçbir
 * değer burada üretilmez; `CalculateResponse` olduğu gibi gösterilir.
 */

import type {
  AiOut,
  AnalyzeRow,
  CandidateOut,
  DecimalString,
  ExclusionReason,
  MatchOut,
  MatchStatusOut,
} from './api'

/**
 * Kullanıcının satır kararı.
 *
 * `approve` bir katalog kodu ister; `reject` kodsuzdur. Sunucu her ikisini de
 * `apply_decisions` içinde yeniden doğrular — bu tip yalnızca istek gövdesini
 * kurmak içindir, otorite değildir.
 */
export type RowDecision =
  | { action: 'approve'; code: string; reason: string }
  | { action: 'reject'; reason: string }

/**
 * Arayüzde gösterilen satır durumu.
 *
 * `rule`/`pending`/`excluded`/`invalid` sunucudan gelir. `ai-approved` ve
 * `rejected` **yalnızca** kullanıcı kararı varsa oluşur; AI önerisi tek başına
 * bu durumları üretmez.
 */
export type ReviewStatus =
  | 'rule'
  | 'ai-approved'
  | 'pending'
  | 'rejected'
  | 'excluded'
  | 'invalid'

/** Analiz satırı + kullanıcı kararı. Türetilmiş, sunucuya gönderilmez. */
export type ReviewRow = {
  /** Analizdeki ham satır — hiçbir alanı değiştirilmez. */
  row: AnalyzeRow
  /** Kullanıcı kararı; yoksa `null`. */
  decision: RowDecision | null
  /** Karar varsa onaylanan katalog kodu, yoksa sunucunun `matched_code`'u. */
  matchedCode: string | null
  /** Karar uygulandıktan sonraki görünüm durumu. */
  status: ReviewStatus
}

/** Durum filtresi ve rozet sayaçları. */
export type StatusCounts = Record<ReviewStatus, number>

/** Tek bir satırın karar yapılabilir olup olmadığı. */
export type DecisionCapability = {
  /** Onay/red verilebilir mi? (yalnızca `pending` satırlar) */
  canDecide: boolean
  /** Karar geri alınabilir mi? (karar verilmiş her satır) */
  canReset: boolean
  /** Seçilebilecek katalog adayları. */
  candidates: CandidateOut[]
}

/** AI önerisinin arayüzdeki durumu — her zaman "öneri", asla "karar" değil. */
export type AiSuggestionView =
  | { kind: 'off' }
  | { kind: 'none' }
  | {
      kind: 'suggested'
      code: string
      confidence: DecimalString | null
      reason: string
    }
  | { kind: 'ambiguous'; reason: string; candidateCodes: string[] }
  | { kind: 'no_match'; reason: string }
  | { kind: 'error'; code: string; message: string }

/** Analiz özetinin arayüzde gösterilen hali. */
export type AnalyzeView = {
  fileName: string
  sheetName: string
  summary: {
    total: number
    valid: number
    invalid: number
    blankSkipped: number
    rule: number
    pending: number
    excluded: number
    invalidRows: number
  }
  aiEnabled: boolean
  aiProvider: string
  aiEvaluated: number
  aiSuggested: number
  aiAmbiguous: number
  aiNoMatch: number
  aiErrors: number
  warnings: string[]
  ignoredColumns: string[]
}

/** Sonuç ekranının okuduğu, sunucudan **aynen** gelen hesaplama özeti. */
export type CalculationView = {
  groups: import('./api').GroupOut[]
  skipped: import('./api').SkippedRowOut[]
  summary: import('./api').CalculationSummaryOut
  warnings: string[]
  /** Hesaplama sırasında gönderilen gövde — rapor da aynısını kullanır. */
  request: import('./api').CalculateRequest
}

/** Uygulama akışındaki aşama. */
export type WorkflowStage =
  | 'idle'
  | 'analyzing'
  | 'reviewing'
  | 'calculating'
  | 'done'
  | 'error'

/* --------------------------------------------------------------------------
 * Saf yardımcılar — React'ten bağımsız, test edilebilir.
 * -------------------------------------------------------------------------- */

/** Satırın görünüm durumunu karar + sunucu durumundan türetir. */
export function deriveReviewStatus(
  row: AnalyzeRow,
  decision: RowDecision | null,
): ReviewStatus {
  if (decision?.action === 'approve') return 'ai-approved'
  if (decision?.action === 'reject') return 'rejected'
  return row.status
}

/** Kararları uygulayarak görünüm satırlarını kurar. */
export function deriveReviewRows(
  rows: AnalyzeRow[],
  decisions: Record<string, RowDecision>,
): ReviewRow[] {
  return rows.map((row) => {
    const decision = row.boq_no ? (decisions[row.boq_no] ?? null) : null
    const matchedCode =
      decision?.action === 'approve'
        ? decision.code
        : decision?.action === 'reject'
          ? null
          : row.match.matched_code

    return {
      row,
      decision,
      matchedCode,
      status: deriveReviewStatus(row, decision),
    }
  })
}

export function countStatuses(rows: ReviewRow[]): StatusCounts {
  const counts: StatusCounts = {
    rule: 0,
    'ai-approved': 0,
    pending: 0,
    rejected: 0,
    excluded: 0,
    invalid: 0,
  }
  for (const row of rows) counts[row.status] += 1
  return counts
}

/** Sunucu karar verilebilir mi diyor? Yalnızca kararsız `pending` satırlar. */
export function decisionCapability(row: ReviewRow): DecisionCapability {
  // `row.row.status` sunucunun **analiz** durumudur; karar verildiğinde
  // değişmez. Bu yüzden karar varlığı ayrıca kontrol edilir: karar verilmiş
  // satırda yeniden onay/red verilemez, önce "kararı geri al" gerekir.
  const pending = row.row.status === 'pending' && row.decision === null
  return {
    canDecide: pending,
    canReset: row.decision !== null,
    candidates: row.row.match.candidates,
  }
}

/** AI alanını arayüz görünümüne çevirir. `null` → AI çalışmadı. */
export function aiSuggestionView(ai: AiOut | null): AiSuggestionView {
  if (ai === null) return { kind: 'none' }
  if (ai.error) {
    return { kind: 'error', code: ai.error.code, message: ai.error.message }
  }
  const suggestion = ai.suggestion
  if (!suggestion) return { kind: 'none' }

  switch (suggestion.status) {
    case 'suggested':
      return {
        kind: 'suggested',
        // `suggested_code` doğrulamadan geçmiştir; yine de boşsa öneri yoktur.
        code: suggestion.suggested_code ?? '',
        confidence: suggestion.confidence,
        reason: suggestion.reason,
      }
    case 'ambiguous':
      return {
        kind: 'ambiguous',
        reason: suggestion.reason,
        candidateCodes: suggestion.candidate_codes,
      }
    case 'no_match':
      return { kind: 'no_match', reason: suggestion.reason }
    default:
      return { kind: 'none' }
  }
}

/** Sunucunun döndürdüğü adaylar arasından kodla arama. */
export function findCandidate(
  candidates: CandidateOut[],
  code: string,
): CandidateOut | undefined {
  return candidates.find((candidate) => candidate.code === code)
}

/** Hariç tutulma nedeni için kısa Türkçe başlık. */
export const EXCLUSION_LABEL: Record<ExclusionReason, string> = {
  waste: 'Fire tanımsız',
  unit: 'Birim desteklenmiyor',
  catalog: 'Katalog dışı',
  'missing-mass': 'Ağırlık verisi eksik',
}

/** Hesaplamada atlanan satırın nedeni. */
export const SKIP_LABEL: Record<string, string> = {
  pending: 'Onay bekliyor',
  rejected: 'Kullanıcı reddetti',
  excluded: 'Hesap kapsamı dışı',
  invalid: 'Veri geçersiz',
  'unknown-code': 'Kod katalogda yok',
}

/** Sunucu `match` nesnesinin kullanıcıya gösterilebilir açıklaması. */
export function matchMessage(match: MatchOut): string {
  return match.message
}

export type { AnalyzeRow, CandidateOut, DecimalString, MatchStatusOut }
