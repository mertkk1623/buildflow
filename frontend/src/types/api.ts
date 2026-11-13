/**
 * Backend sözleşmesi — `backend/app/api/schemas.py` ile birebir hizalıdır.
 *
 * Kurallar
 * --------
 * 1. Tüm `Decimal` alanlar JSON'da **string** gelir (bkz. `DecimalStr`).
 *    `number`'a çevrilip hesaplama yapılmaz; yalnızca gösterim için okunur.
 * 2. Eksik değer `null`'dır; `0` yazılmaz. Bu ayrım arayüzde korunur.
 * 3. Bu tipler istemci tarafında **üretilmez**; yalnızca yanıtı okumak için
 *    kullanılır. `ClientRow`/`ClientDecision` ise sunucuya gönderilen ve
 *    sunucunun `extra="forbid"` ile doğruladığı alan kümesidir.
 */

/** Sunucudan gelen ondalık değer — kayıpsız metin (`"18.00582"`). */
export type DecimalString = string

/* --------------------------------------------------------------------------
 * Ortak
 * -------------------------------------------------------------------------- */

export type FieldIssue = {
  source_row: number | null
  boq_no: string | null
  column: string | null
  code: string
  message: string
  suggestion: string
}

/* --------------------------------------------------------------------------
 * Health
 * -------------------------------------------------------------------------- */

export type HealthResponse = {
  status: string
  environment: string
}

/* --------------------------------------------------------------------------
 * Analyze
 * -------------------------------------------------------------------------- */

export type CandidateOut = {
  code: string
  family: string
  family_label: string
  size: string
  grade: string
  coating: string
  label: string
  mass_kg_per_m: DecimalString | null
  commercial_length_m: DecimalString | null
}

export type MatchStatusOut = 'rule' | 'pending' | 'excluded' | 'invalid'

export type ExclusionReason =
  | 'waste'
  | 'unit'
  | 'catalog'
  | 'missing-mass'

export type MatchOut = {
  status: MatchStatusOut
  matched_code: string | null
  candidate_codes: string[]
  candidates: CandidateOut[]
  exclusion_reason: ExclusionReason | null
  message: string
}

export type AiSuggestionStatus = 'suggested' | 'ambiguous' | 'no_match'

/** AI'nın önerisi — **karar değildir** ve hesaplamaya girmez. */
export type AiSuggestionOut = {
  status: AiSuggestionStatus
  suggested_code: string | null
  confidence: DecimalString | null
  reason: string
  candidate_codes: string[]
}

export type AiErrorCode =
  | 'not-configured'
  | 'invalid-payload'
  | 'unknown-status'
  | 'bad-confidence'
  | 'invalid-code'
  | 'inconsistent-response'
  | 'provider-unavailable'
  | 'provider-error'

export type AiErrorOut = {
  code: AiErrorCode
  message: string
}

/** Bir satırın AI değerlendirmesi: öneri **veya** hata (ikisi birden olmaz). */
export type AiOut = {
  suggestion: AiSuggestionOut | null
  error: AiErrorOut | null
}

export type AiSummaryOut = {
  enabled: boolean
  provider: string
  evaluated_rows: number
  suggested: number
  ambiguous: number
  no_match: number
  errors: number
}

export type AnalyzeRow = {
  /** Excel'deki 1 tabanlı satır numarası — izlenebilirlik anahtarı. */
  source_row: number
  boq_no: string | null
  description: string | null
  quantity: DecimalString | null
  unit: string | null
  /** Fire yüzdesi; tanımsızsa `null` (sıfır değil). */
  waste_percent: DecimalString | null
  status: MatchStatusOut
  match: MatchOut
  ai: AiOut | null
  issues: FieldIssue[]
  notes: string[]
}

export type AnalyzeSummaryOut = {
  total_rows: number
  valid_rows: number
  invalid_rows: number
  blank_rows_skipped: number
  rule: number
  pending: number
  excluded: number
  invalid: number
}

export type AnalyzeResponse = {
  rows: AnalyzeRow[]
  summary: AnalyzeSummaryOut
  ai: AiSummaryOut
  warnings: string[]
  ignored_columns: string[]
  sheet_name: string
}

/* --------------------------------------------------------------------------
 * Calculate — istek (sunucu `extra="forbid"` uygular)
 * -------------------------------------------------------------------------- */

/**
 * Sunucuya geri gönderilen ham BOQ satırı.
 *
 * Burada **yalnızca** ham veri vardır: eşleşme durumu, katalog kodu veya
 * hesaplanmış değer yoktur. Sunucu `match_status`/`matched_code` alanlarını
 * şemada barındırmaz; gönderilirse istek 422 ile reddedilir.
 */
export type ClientRow = {
  source_row: number
  boq_no: string
  description: string
  quantity: DecimalString
  unit: string
  waste_percent: DecimalString | null
}

export type DecisionAction = 'approve' | 'reject'

/** Kullanıcı kararı: onay (kod ile) veya red. Durum alanı **yoktur**. */
export type ClientDecision = {
  boq_no: string
  action: DecisionAction
  code: string | null
  reason: string
}

export type CalculateRequest = {
  rows: ClientRow[]
  decisions: ClientDecision[]
}

/* --------------------------------------------------------------------------
 * Calculate — yanıt
 * -------------------------------------------------------------------------- */

export type WasteSource = 'row' | 'catalog' | 'none'

export type SourceRowOut = {
  source_row: number | null
  boq_no: string
  description: string
  source_quantity: DecimalString
  source_unit: string | null
  net_metres: DecimalString | null
  waste_percent: DecimalString | null
  gross_metres: DecimalString | null
  gross_quantity: DecimalString | null
  fire_quantity: DecimalString | null
  waste_source: WasteSource
  conversion_steps: string[]
}

export type CalculationField =
  | 'fire'
  | 'conversion'
  | 'commercial-length'
  | 'mass'

export type MissingFieldOut = {
  field: CalculationField
  message: string
  boq_no: string | null
  source_row: number | null
}

export type GroupStatus = 'FULL' | 'PARTIAL'

export type GroupOut = {
  code: string
  family: string
  family_label: string
  size: string
  grade: string
  coating: string
  product_label: string

  status: GroupStatus
  missing_fields: CalculationField[]
  missing: MissingFieldOut[]

  mass_kg_per_m: DecimalString | null
  commercial_length_m: DecimalString | null
  bar_count: DecimalString | null
  total_gross_metres: DecimalString | null
  order_length_m: DecimalString | null
  rounding_surplus_m: DecimalString | null
  weight_kg: DecimalString | null

  weight_label: string
  weight_note: string

  merged: boolean
  source_boq_nos: string[]
  /** `source_boq_nos` ile paralel Excel satır numaraları. */
  source_rows: number[]
  sources: SourceRowOut[]
  notes: string[]
}

export type SkippedStatus =
  | 'pending'
  | 'rejected'
  | 'excluded'
  | 'invalid'
  | 'unknown-code'

export type SkippedRowOut = {
  source_row: number | null
  boq_no: string
  status: SkippedStatus
  match_status:
    | 'rule'
    | 'ai-approved'
    | 'pending'
    | 'rejected'
    | 'excluded'
    | 'invalid'
    | null
  matched_code: string | null
  message: string
}

export type CalculationSummaryOut = {
  input_rows: number
  calculated_rows: number
  skipped_rows: number
  groups: number
  merged_groups: number
  merges: number
  full_groups: number
  partial_groups: number
  total_order_length_m: DecimalString | null
  known_weight_kg: DecimalString | null
  weight_complete: boolean
}

export type CalculateResponse = {
  groups: GroupOut[]
  skipped: SkippedRowOut[]
  summary: CalculationSummaryOut
  warnings: string[]
}

/* --------------------------------------------------------------------------
 * Hata zarfı
 * -------------------------------------------------------------------------- */

export type ApiIssue = {
  source_row: number | null
  boq_no: string | null
  column: string | null
  code: string | null
  message: string
  suggestion: string
}

export type ApiErrorBody = {
  code: string
  message: string
  detail: string
  suggestion: string
  issues: ApiIssue[]
}

export type ApiErrorEnvelope = {
  error: ApiErrorBody
}
