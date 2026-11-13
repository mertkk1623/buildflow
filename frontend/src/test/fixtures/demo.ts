/**
 * Test fixture'ları — **gerçek backend çıktısından** üretilmiştir.
 *
 * Kaynak: `backend/tests/fixtures/demo_boq.py` (18 satır + 4 karar) ve motorun
 * kilitli çıktısı (8 grup, 5 birleşme, 966 m, 18.005,820 kg). Buradaki hiçbir
 * sayı elle uydurulmamıştır; hepsi sunucunun ürettiği JSON'dan kopyalanmıştır.
 * Amaç, arayüzün gerçek sözleşmeyle test edilmesi.
 */

import type {
  AiOut,
  AiSummaryOut,
  AnalyzeResponse,
  AnalyzeRow,
  CalculateRequest,
  CalculateResponse,
  CandidateOut,
  DecimalString,
  ExclusionReason,
  FieldIssue,
  GroupOut,
  MatchStatusOut,
  SkippedRowOut,
  SourceRowOut,
} from '../../types/api'

/* --------------------------------------------------------------------------
 * Katalog adayları (sunucunun `CandidateOut.label` biçimiyle)
 * -------------------------------------------------------------------------- */

function candidate(
  code: string,
  family: string,
  familyLabel: string,
  size: string,
  grade: string,
  coating: string,
  massKgPerM: DecimalString,
  commercialLengthM: DecimalString,
): CandidateOut {
  return {
    code,
    family,
    family_label: familyLabel,
    size,
    grade,
    coating,
    // Sunucu etiketi: `${family_label} ${size} · ${grade} · ${coating}`.
    label: `${familyLabel} ${size} · ${grade} · ${coating}`,
    mass_kg_per_m: massKgPerM,
    commercial_length_m: commercialLengthM,
  }
}

export const CANDIDATES: Record<string, CandidateOut> = {
  'BOX-100-4-S235-B': candidate(
    'BOX-100-4-S235-B',
    'BOX',
    'Kutu profil',
    '100×100×4',
    'S235',
    'siyah',
    '11.70',
    '6',
  ),
  'BOX-100-4-S235-G': candidate(
    'BOX-100-4-S235-G',
    'BOX',
    'Kutu profil',
    '100×100×4',
    'S235',
    'galvaniz',
    '11.70',
    '6',
  ),
  'BOX-150-100-5-S235-B': candidate(
    'BOX-150-100-5-S235-B',
    'BOX',
    'Kutu profil',
    '150×100×5',
    'S235',
    'siyah',
    '18.30',
    '6',
  ),
  'IPE-200-S235': candidate(
    'IPE-200-S235',
    'IPE',
    'IPE',
    '200',
    'S235',
    'siyah',
    '22.40',
    '12',
  ),
  'IPE-240-S355': candidate(
    'IPE-240-S355',
    'IPE',
    'IPE',
    '240',
    'S355',
    'siyah',
    '30.70',
    '12',
  ),
  'HEA-200-S235': candidate(
    'HEA-200-S235',
    'HEA',
    'HEA',
    '200',
    'S235',
    'siyah',
    '42.30',
    '12',
  ),
  'UPN-160-S235': candidate(
    'UPN-160-S235',
    'UPN',
    'UPN',
    '160',
    'S235',
    'siyah',
    '18.80',
    '12',
  ),
  'FLAT-40x5-S235-B': candidate(
    'FLAT-40x5-S235-B',
    'FLAT',
    'Lama',
    '40×5',
    'S235',
    'siyah',
    '1.570',
    '6',
  ),
  'FLAT-40x5-S235-G': candidate(
    'FLAT-40x5-S235-G',
    'FLAT',
    'Lama',
    '40×5',
    'S235',
    'galvaniz',
    '1.570',
    '6',
  ),
}

/* --------------------------------------------------------------------------
 * Analyze — 18 satır
 * -------------------------------------------------------------------------- */

const RULE_MESSAGE = 'Dört özellik eksiksiz ve katalogda tek kalem eşleşti.'

const MISSING_QUALITY_COATING =
  'Eksik özellik(ler): kalite, kaplama. Otomatik eşleştirme yapılmaz; kullanıcı onayı gerekir.'

const MISSING_COATING =
  'Eksik özellik(ler): kaplama. Otomatik eşleştirme yapılmaz; kullanıcı onayı gerekir.'

type RowSpec = {
  row: number
  no: string
  description: string
  quantity: DecimalString | null
  unit: string | null
  waste: DecimalString | null
  status: MatchStatusOut
  matched?: string | null
  candidates?: string[]
  exclusion?: ExclusionReason | null
  message: string
  issues?: FieldIssue[]
  notes?: string[]
}

const DEMO_ROW_SPECS: RowSpec[] = [
  {
    row: 2,
    no: 'BOQ-001',
    description: 'BOX 100×100×4 S235 siyah',
    quantity: '96',
    unit: 'm',
    waste: '5',
    status: 'rule',
    matched: 'BOX-100-4-S235-B',
    candidates: ['BOX-100-4-S235-B'],
    message: RULE_MESSAGE,
  },
  {
    row: 3,
    no: 'BOQ-002',
    description: 'kutu profil 100/100/4 S235 galvaniz',
    quantity: '48',
    unit: 'm',
    waste: '5',
    status: 'rule',
    matched: 'BOX-100-4-S235-G',
    candidates: ['BOX-100-4-S235-G'],
    message: RULE_MESSAGE,
  },
  {
    row: 4,
    no: 'BOQ-003',
    description: 'IPE 200',
    quantity: '1240',
    unit: 'kg',
    waste: '3',
    status: 'pending',
    candidates: ['IPE-200-S235'],
    message: MISSING_QUALITY_COATING,
  },
  {
    row: 5,
    no: 'BOQ-004',
    description: 'ipe240 s355',
    quantity: '0.84',
    unit: 't',
    waste: '3',
    status: 'pending',
    candidates: ['IPE-240-S355'],
    message: MISSING_COATING,
  },
  {
    row: 6,
    no: 'BOQ-005',
    description: 'HEA 200 S235 siyah',
    quantity: '132',
    unit: 'm',
    waste: '4',
    status: 'rule',
    matched: 'HEA-200-S235',
    candidates: ['HEA-200-S235'],
    message: RULE_MESSAGE,
  },
  {
    row: 7,
    no: 'BOQ-006',
    description: 'hea 200',
    quantity: '3.2',
    unit: 't',
    waste: '4',
    status: 'pending',
    candidates: ['HEA-200-S235'],
    message: MISSING_QUALITY_COATING,
  },
  {
    row: 8,
    no: 'BOQ-007',
    description: 'UPN 160 S235 siyah',
    quantity: '54',
    unit: 'm',
    waste: '4',
    status: 'rule',
    matched: 'UPN-160-S235',
    candidates: ['UPN-160-S235'],
    message: RULE_MESSAGE,
  },
  {
    row: 9,
    no: 'BOQ-008',
    description: 'lama 40×5 S235 siyah',
    quantity: '210',
    unit: 'kg',
    waste: '5',
    status: 'rule',
    matched: 'FLAT-40x5-S235-B',
    candidates: ['FLAT-40x5-S235-B'],
    message: RULE_MESSAGE,
  },
  {
    row: 10,
    no: 'BOQ-009',
    description: 'lama 40×5',
    quantity: '180',
    unit: 'kg',
    waste: '5',
    status: 'pending',
    candidates: ['FLAT-40x5-S235-B', 'FLAT-40x5-S235-G'],
    message: MISSING_QUALITY_COATING,
  },
  {
    row: 11,
    no: 'BOQ-010',
    description: 'UPN 160 S235 siyah',
    quantity: '0.32',
    unit: 't',
    waste: '4',
    status: 'rule',
    matched: 'UPN-160-S235',
    candidates: ['UPN-160-S235'],
    message: RULE_MESSAGE,
  },
  {
    row: 12,
    no: 'BOQ-011',
    description: 'kutu profil 150×100×5 S235 siyah',
    quantity: '60',
    unit: 'm',
    waste: '5',
    status: 'rule',
    matched: 'BOX-150-100-5-S235-B',
    candidates: ['BOX-150-100-5-S235-B'],
    message: RULE_MESSAGE,
  },
  {
    row: 13,
    no: 'BOQ-012',
    description: 'BOX 100×100×4 S235 siyah',
    quantity: '60',
    unit: 'm',
    waste: null,
    status: 'excluded',
    candidates: ['BOX-100-4-S235-B'],
    exclusion: 'waste',
    message:
      'Satırda fire oranı yok ve katalogda varsayılan fire tanımlı değil. Eksik fire sıfır kabul edilmez. Eşleşen kalem BOX-100-4-S235-B olsa da fire tanımsız olduğu için hesaba girmez.',
  },
  {
    row: 14,
    no: 'BOQ-013',
    description: 'BOX 100×100×4 S235 siyah',
    quantity: '84',
    unit: 'm',
    waste: '5',
    status: 'rule',
    matched: 'BOX-100-4-S235-B',
    candidates: ['BOX-100-4-S235-B'],
    message: RULE_MESSAGE,
  },
  {
    row: 15,
    no: 'BOQ-014',
    description: 'profil 100×100',
    quantity: '12',
    unit: 'adet',
    waste: '5',
    status: 'excluded',
    candidates: [],
    exclusion: 'unit',
    message: "Birim 'adet' desteklenmiyor. Desteklenen birimler: m, kg, t.",
    issues: [
      {
        source_row: 15,
        boq_no: 'BOQ-014',
        column: 'Birim',
        code: 'unit',
        message: "Birim 'adet' bu sürümde hesap kapsamı dışında.",
        suggestion:
          "Satır korunur ve 'kapsam dışı' olarak raporlanır. Hesaplamak için birimi m, kg veya t olarak girin.",
      },
    ],
  },
  {
    row: 16,
    no: 'BOQ-015',
    description: 'muhtelif bağlantı elemanı',
    quantity: '40',
    unit: 'kg',
    waste: null,
    status: 'excluded',
    candidates: [],
    exclusion: 'catalog',
    message:
      'Açıklama katalogdaki malzeme ailelerinden hiçbiriyle eşleşmiyor. Eksik özellikler: grup, ölçü, kalite, kaplama',
  },
  {
    row: 17,
    no: 'BOQ-016',
    description: 'lama 40×5 S235 siyah',
    quantity: '150',
    unit: 'kg',
    waste: '5',
    status: 'rule',
    matched: 'FLAT-40x5-S235-B',
    candidates: ['FLAT-40x5-S235-B'],
    message: RULE_MESSAGE,
  },
  {
    row: 18,
    no: 'BOQ-017',
    description: 'IPE 240 S355 siyah',
    quantity: '0.45',
    unit: 't',
    waste: '3',
    status: 'rule',
    matched: 'IPE-240-S355',
    candidates: ['IPE-240-S355'],
    message: RULE_MESSAGE,
  },
  {
    row: 19,
    no: 'BOQ-018',
    description: 'IPE 200 S355',
    quantity: '620',
    unit: 'kg',
    waste: '3',
    status: 'excluded',
    candidates: [],
    exclusion: 'catalog',
    message:
      'Bilinen özelliklerle eşleşen katalog kalemi yok. Eksik özellikler: kaplama',
  },
]

export function makeRow(spec: RowSpec, ai: AiOut | null = null): AnalyzeRow {
  return {
    source_row: spec.row,
    boq_no: spec.no,
    description: spec.description,
    quantity: spec.quantity,
    unit: spec.unit,
    waste_percent: spec.waste,
    status: spec.status,
    match: {
      status: spec.status,
      matched_code: spec.matched ?? null,
      candidate_codes: spec.candidates ?? [],
      candidates: (spec.candidates ?? []).map((code) => CANDIDATES[code]),
      exclusion_reason: spec.exclusion ?? null,
      message: spec.message,
    },
    ai,
    issues: spec.issues ?? [],
    notes: spec.notes ?? [],
  }
}

const DEMO_AI_SUMMARY: AiSummaryOut = {
  enabled: false,
  provider: 'none',
  evaluated_rows: 0,
  suggested: 0,
  ambiguous: 0,
  no_match: 0,
  errors: 0,
}

function summarizeAi(ai: Record<string, AiOut>): AiSummaryOut {
  const values = Object.values(ai)
  const count = (status: string) =>
    values.filter((item) => item.suggestion?.status === status).length

  return {
    enabled: true,
    provider: 'scripted',
    evaluated_rows: values.length,
    suggested: count('suggested'),
    ambiguous: count('ambiguous'),
    no_match: count('no_match'),
    errors: values.filter((item) => item.error !== null).length,
  }
}

/** Demo analizi. `ai` verilirse yalnızca o satırlara AI çıktısı eklenir. */
export function makeAnalysis(
  options: {
    ai?: Record<string, AiOut>
    warnings?: string[]
    ignoredColumns?: string[]
  } = {},
): AnalyzeResponse {
  const ai = options.ai ?? {}
  const rows = DEMO_ROW_SPECS.map((spec) => makeRow(spec, ai[spec.no] ?? null))

  return {
    rows,
    summary: {
      total_rows: rows.length,
      valid_rows: rows.length,
      invalid_rows: 0,
      blank_rows_skipped: 0,
      rule: 10,
      pending: 4,
      excluded: 4,
      invalid: 0,
    },
    ai: options.ai ? summarizeAi(ai) : DEMO_AI_SUMMARY,
    warnings: options.warnings ?? [],
    ignored_columns: options.ignoredColumns ?? [],
    sheet_name: 'Metraj',
  }
}

/* --------------------------------------------------------------------------
 * Analyze — geçersiz satırlı senaryo (atlanan satırların korunumu)
 * -------------------------------------------------------------------------- */

/** Geçersiz satır: miktar okunamadı → `status: invalid`, `quantity: null`. */
export function analysisWithInvalidRow(): AnalyzeResponse {
  const base = makeAnalysis()
  const invalid = makeRow({
    row: 20,
    no: 'BOQ-019',
    description: 'BOQ numarası yinelenen satır',
    quantity: null,
    unit: 'm',
    waste: '5',
    status: 'invalid',
    candidates: [],
    message: 'Satır geçersiz: Miktar okunamadı.',
    issues: [
      {
        source_row: 20,
        boq_no: 'BOQ-019',
        column: 'Miktar',
        code: 'invalid-quantity',
        message: 'Miktar okunamadı.',
        suggestion: 'Miktarı sayı olarak girin.',
      },
    ],
  })

  return {
    ...base,
    rows: [...base.rows, invalid],
    summary: {
      ...base.summary,
      total_rows: base.summary.total_rows + 1,
      valid_rows: base.summary.valid_rows,
      invalid_rows: 1,
      invalid: 1,
    },
    warnings: ['1 satır veri olarak okunamadı; hesaba katılmaz.'],
  }
}

/* --------------------------------------------------------------------------
 * AI senaryoları
 * -------------------------------------------------------------------------- */

export const AI_SUGGESTED_IPE200: AiOut = {
  suggestion: {
    status: 'suggested',
    suggested_code: 'IPE-200-S235',
    confidence: '0.9',
    reason: 'Aday, açıklamadaki özelliklerle uyuşuyor.',
    candidate_codes: ['IPE-200-S235'],
  },
  error: null,
}

export const AI_AMBIGUOUS_FLAT: AiOut = {
  suggestion: {
    status: 'ambiguous',
    suggested_code: null,
    confidence: null,
    reason: 'Açıklamada kaplama belirtilmemiş; iki aday da olası.',
    candidate_codes: ['FLAT-40x5-S235-B', 'FLAT-40x5-S235-G'],
  },
  error: null,
}

export const AI_ERROR_HEA: AiOut = {
  suggestion: null,
  error: {
    code: 'provider-unavailable',
    message: 'AI servisine ulaşılamadı.',
  },
}

export const AI_NO_MATCH: AiOut = {
  suggestion: {
    status: 'no_match',
    suggested_code: null,
    confidence: null,
    reason: 'Açıklama adaylardan hiçbiriyle güvenilir biçimde eşleşmiyor.',
    candidate_codes: [],
  },
  error: null,
}

/** AI açık senaryo: 1 öneri, 1 belirsiz, 1 hata, 1 eşleşme yok. */
export function analysisWithAi(): AnalyzeResponse {
  return makeAnalysis({
    ai: {
      'BOQ-003': AI_SUGGESTED_IPE200,
      'BOQ-009': AI_AMBIGUOUS_FLAT,
      'BOQ-006': AI_ERROR_HEA,
      'BOQ-004': AI_NO_MATCH,
    },
    warnings: [
      'Bazı satırlar için AI önerisi kullanılamadı; bu satırlar kullanıcı onayı beklemeye devam ediyor.',
    ],
  })
}

/* --------------------------------------------------------------------------
 * Calculate — kilitli demo sonucu
 * -------------------------------------------------------------------------- */

function sourceRow(
  spec: {
    row: number
    no: string
    description: string
    quantity: DecimalString
    unit: string
    net: DecimalString | null
    waste: DecimalString | null
    gross: DecimalString | null
    grossQuantity: DecimalString | null
    fire: DecimalString | null
    steps: string[]
    wasteSource?: SourceRowOut['waste_source']
  },
): SourceRowOut {
  return {
    source_row: spec.row,
    boq_no: spec.no,
    description: spec.description,
    source_quantity: spec.quantity,
    source_unit: spec.unit,
    net_metres: spec.net,
    waste_percent: spec.waste,
    gross_metres: spec.gross,
    gross_quantity: spec.grossQuantity,
    fire_quantity: spec.fire,
    waste_source: spec.wasteSource ?? 'row',
    conversion_steps: spec.steps,
  }
}

type GroupSpec = {
  code: string
  status: GroupOut['status']
  mass: DecimalString | null
  length: DecimalString | null
  bars: DecimalString | null
  gross: DecimalString | null
  order: DecimalString | null
  surplus: DecimalString | null
  weight: DecimalString | null
  merged: boolean
  notes: string[]
  sources: SourceRowOut[]
  missingFields?: GroupOut['missing_fields']
  missing?: GroupOut['missing']
}

function groupFromSpec(spec: GroupSpec): GroupOut {
  const product = CANDIDATES[spec.code]
  return {
    code: spec.code,
    family: product.family,
    family_label: product.family_label,
    size: product.size,
    grade: product.grade,
    coating: product.coating,
    product_label: product.label,
    status: spec.status,
    missing_fields: spec.missingFields ?? [],
    missing: spec.missing ?? [],
    mass_kg_per_m: spec.mass,
    commercial_length_m: spec.length,
    bar_count: spec.bars,
    total_gross_metres: spec.gross,
    order_length_m: spec.order,
    rounding_surplus_m: spec.surplus,
    weight_kg: spec.weight,
    weight_label: 'Teorik çıplak çelik ağırlığı',
    weight_note:
      'Çıplak çelik kütlesi. Gerçek sevkiyat veya tedarikçi kantar ağırlığı değildir.',
    merged: spec.merged,
    source_boq_nos: spec.sources.map((source) => source.boq_no),
    source_rows: spec.sources.map((source) => source.source_row ?? 0),
    sources: spec.sources,
    notes: spec.notes,
  }
}

const DEMO_GROUPS: GroupSpec[] = [
  {
    code: 'BOX-100-4-S235-B',
    status: 'FULL',
    mass: '11.70',
    length: '6',
    bars: '32',
    gross: '189.0000',
    order: '192',
    surplus: '3.0000',
    weight: '2246.40',
    merged: true,
    notes: [
      'Yuvarlama nedeniyle 3.000 m fazla sipariş edildi.',
      '2 kaynak satır aynı katalog kodunda birleştirildi: BOQ-001, BOQ-013',
    ],
    sources: [
      sourceRow({
        row: 2,
        no: 'BOQ-001',
        description: 'BOX 100×100×4 S235 siyah',
        quantity: '96',
        unit: 'm',
        net: '96',
        waste: '5.00',
        gross: '100.8000',
        grossQuantity: '100.8000',
        fire: '4.8000',
        steps: ['Zaten metre: miktar (m) = 96'],
      }),
      sourceRow({
        row: 14,
        no: 'BOQ-013',
        description: 'BOX 100×100×4 S235 siyah',
        quantity: '84',
        unit: 'm',
        net: '84',
        waste: '5.00',
        gross: '88.2000',
        grossQuantity: '88.2000',
        fire: '4.2000',
        steps: ['Zaten metre: miktar (m) = 84'],
      }),
    ],
  },
  {
    code: 'BOX-100-4-S235-G',
    status: 'FULL',
    mass: '11.70',
    length: '6',
    bars: '9',
    gross: '50.4000',
    order: '54',
    surplus: '3.6000',
    weight: '631.80',
    merged: false,
    notes: ['Yuvarlama nedeniyle 3.600 m fazla sipariş edildi.'],
    sources: [
      sourceRow({
        row: 3,
        no: 'BOQ-002',
        description: 'kutu profil 100/100/4 S235 galvaniz',
        quantity: '48',
        unit: 'm',
        net: '48',
        waste: '5.00',
        gross: '50.4000',
        grossQuantity: '50.4000',
        fire: '2.4000',
        steps: ['Zaten metre: miktar (m) = 48'],
      }),
    ],
  },
  {
    code: 'IPE-200-S235',
    status: 'FULL',
    mass: '22.40',
    length: '12',
    bars: '5',
    gross: '57.017857142857142857142857145800',
    order: '60',
    surplus: '2.982142857142857142857142854200',
    weight: '1344.00',
    merged: false,
    notes: ['Yuvarlama nedeniyle 2.982 m fazla sipariş edildi.'],
    sources: [
      sourceRow({
        row: 4,
        no: 'BOQ-003',
        description: 'IPE 200',
        quantity: '1240',
        unit: 'kg',
        net: '55.35714285714285714285714286',
        waste: '3.00',
        gross: '57.017857142857142857142857145800',
        grossQuantity: '1277.2000',
        fire: '37.2000',
        steps: [
          'Kilogram → metre: 1240 kg ÷ 22.40 kg/m = 55.35714285714285714285714286',
        ],
      }),
    ],
  },
  {
    code: 'IPE-240-S355',
    status: 'FULL',
    mass: '30.70',
    length: '12',
    bars: '4',
    gross: '43.280130293159609120521172632800',
    order: '48',
    surplus: '4.719869706840390879478827367200',
    weight: '1473.60',
    merged: true,
    notes: [
      'Yuvarlama nedeniyle 4.720 m fazla sipariş edildi.',
      '2 kaynak satır aynı katalog kodunda birleştirildi: BOQ-004, BOQ-017',
    ],
    sources: [
      sourceRow({
        row: 5,
        no: 'BOQ-004',
        description: 'ipe240 s355',
        quantity: '0.84',
        unit: 't',
        net: '27.36156351791530944625407166',
        waste: '3.00',
        gross: '28.182410423452768729641693809800',
        grossQuantity: '0.865200',
        fire: '0.025200',
        steps: [
          'Ton → kilogram: 0.84 t × 1000 = 840',
          'Kilogram → metre: 840.00 kg ÷ 30.70 kg/m = 27.36156351791530944625407166',
        ],
      }),
      sourceRow({
        row: 18,
        no: 'BOQ-017',
        description: 'IPE 240 S355 siyah',
        quantity: '0.45',
        unit: 't',
        net: '14.65798045602605863192182410',
        waste: '3.00',
        gross: '15.097719869706840390879478823000',
        grossQuantity: '0.463500',
        fire: '0.013500',
        steps: [
          'Ton → kilogram: 0.45 t × 1000 = 450',
          'Kilogram → metre: 450.00 kg ÷ 30.70 kg/m = 14.6579804560260586319218241',
        ],
      }),
    ],
  },
  {
    code: 'HEA-200-S235',
    status: 'FULL',
    mass: '42.30',
    length: '12',
    bars: '18',
    gross: '215.956122931442080378250591012000',
    order: '216',
    surplus: '0.043877068557919621749408988000',
    weight: '9136.80',
    merged: true,
    notes: [
      'Yuvarlama nedeniyle 0.044 m fazla sipariş edildi.',
      '2 kaynak satır aynı katalog kodunda birleştirildi: BOQ-005, BOQ-006',
    ],
    sources: [
      sourceRow({
        row: 6,
        no: 'BOQ-005',
        description: 'HEA 200 S235 siyah',
        quantity: '132',
        unit: 'm',
        net: '132',
        waste: '4.00',
        gross: '137.2800',
        grossQuantity: '137.2800',
        fire: '5.2800',
        steps: ['Zaten metre: miktar (m) = 132'],
      }),
      sourceRow({
        row: 7,
        no: 'BOQ-006',
        description: 'hea 200',
        quantity: '3.2',
        unit: 't',
        net: '75.65011820330969267139479905',
        waste: '4.00',
        gross: '78.676122931442080378250591012000',
        grossQuantity: '3.32800',
        fire: '0.12800',
        steps: [
          'Ton → kilogram: 3.2 t × 1000 = 3200',
          'Kilogram → metre: 3200.0 kg ÷ 42.30 kg/m = 75.65011820330969267139479905',
        ],
      }),
    ],
  },
  {
    code: 'UPN-160-S235',
    status: 'FULL',
    mass: '18.80',
    length: '12',
    bars: '7',
    gross: '73.862127659574468085106382981600',
    order: '84',
    surplus: '10.137872340425531914893617018400',
    weight: '1579.20',
    merged: true,
    notes: [
      'Yuvarlama nedeniyle 10.138 m fazla sipariş edildi.',
      '2 kaynak satır aynı katalog kodunda birleştirildi: BOQ-007, BOQ-010',
    ],
    sources: [
      sourceRow({
        row: 8,
        no: 'BOQ-007',
        description: 'UPN 160 S235 siyah',
        quantity: '54',
        unit: 'm',
        net: '54',
        waste: '4.00',
        gross: '56.1600',
        grossQuantity: '56.1600',
        fire: '2.1600',
        steps: ['Zaten metre: miktar (m) = 54'],
      }),
      sourceRow({
        row: 11,
        no: 'BOQ-010',
        description: 'UPN 160 S235 siyah',
        quantity: '0.32',
        unit: 't',
        net: '17.02127659574468085106382979',
        waste: '4.00',
        gross: '17.702127659574468085106382981600',
        grossQuantity: '0.332800',
        fire: '0.012800',
        steps: [
          'Ton → kilogram: 0.32 t × 1000 = 320',
          'Kilogram → metre: 320.00 kg ÷ 18.80 kg/m = 17.02127659574468085106382979',
        ],
      }),
    ],
  },
  {
    code: 'FLAT-40x5-S235-B',
    status: 'FULL',
    mass: '1.570',
    length: '6',
    bars: '41',
    gross: '240.764331210191082802547770689000',
    order: '246',
    surplus: '5.235668789808917197452229311000',
    weight: '386.220',
    merged: true,
    notes: [
      'Yuvarlama nedeniyle 5.236 m fazla sipariş edildi.',
      '2 kaynak satır aynı katalog kodunda birleştirildi: BOQ-008, BOQ-016',
    ],
    sources: [
      sourceRow({
        row: 9,
        no: 'BOQ-008',
        description: 'lama 40×5 S235 siyah',
        quantity: '210',
        unit: 'kg',
        net: '133.7579617834394904458598726',
        waste: '5.00',
        gross: '140.44585987261146496815286623000',
        grossQuantity: '220.5000',
        fire: '10.5000',
        steps: [
          'Kilogram → metre: 210 kg ÷ 1.570 kg/m = 133.7579617834394904458598726',
        ],
      }),
      sourceRow({
        row: 17,
        no: 'BOQ-016',
        description: 'lama 40×5 S235 siyah',
        quantity: '150',
        unit: 'kg',
        net: '95.54140127388535031847133758',
        waste: '5.00',
        gross: '100.318471337579617834394904459000',
        grossQuantity: '157.5000',
        fire: '7.5000',
        steps: [
          'Kilogram → metre: 150 kg ÷ 1.570 kg/m = 95.54140127388535031847133758',
        ],
      }),
    ],
  },
  {
    code: 'BOX-150-100-5-S235-B',
    status: 'FULL',
    mass: '18.30',
    length: '6',
    bars: '11',
    gross: '63.0000',
    order: '66',
    surplus: '3.0000',
    weight: '1207.80',
    merged: false,
    notes: ['Yuvarlama nedeniyle 3.000 m fazla sipariş edildi.'],
    sources: [
      sourceRow({
        row: 12,
        no: 'BOQ-011',
        description: 'kutu profil 150×100×5 S235 siyah',
        quantity: '60',
        unit: 'm',
        net: '60',
        waste: '5.00',
        gross: '63.0000',
        grossQuantity: '63.0000',
        fire: '3.0000',
        steps: ['Zaten metre: miktar (m) = 60'],
      }),
    ],
  },
]

const DEMO_SKIPPED: SkippedRowOut[] = [
  {
    source_row: 10,
    boq_no: 'BOQ-009',
    status: 'pending',
    match_status: 'pending',
    matched_code: null,
    message: 'Satır henüz onaylanmadı (pending); hesaplamaya alınmaz.',
  },
  {
    source_row: 13,
    boq_no: 'BOQ-012',
    status: 'excluded',
    match_status: 'excluded',
    matched_code: null,
    message: 'Satır hesap kapsamı dışında bırakıldı; hesaplamaya alınmaz.',
  },
  {
    source_row: 15,
    boq_no: 'BOQ-014',
    status: 'excluded',
    match_status: 'excluded',
    matched_code: null,
    message: 'Satır hesap kapsamı dışında bırakıldı; hesaplamaya alınmaz.',
  },
  {
    source_row: 16,
    boq_no: 'BOQ-015',
    status: 'excluded',
    match_status: 'excluded',
    matched_code: null,
    message: 'Satır hesap kapsamı dışında bırakıldı; hesaplamaya alınmaz.',
  },
  {
    source_row: 19,
    boq_no: 'BOQ-018',
    status: 'rejected',
    match_status: 'rejected',
    matched_code: null,
    message: 'Satır reddedildi; hesaplamaya alınmaz.',
  },
]

/** Kilitli demo sonucu: 8 grup, 5 birleşme, 966 m, 18.005,820 kg, tümü FULL. */
export function makeCalculation(): CalculateResponse {
  return {
    groups: DEMO_GROUPS.map(groupFromSpec),
    skipped: DEMO_SKIPPED,
    summary: {
      input_rows: 18,
      calculated_rows: 13,
      skipped_rows: 5,
      groups: 8,
      merged_groups: 5,
      merges: 5,
      full_groups: 8,
      partial_groups: 0,
      total_order_length_m: '966',
      known_weight_kg: '18005.820',
      weight_complete: true,
    },
    warnings: [],
  }
}

/**
 * PARTIAL senaryosu: ticari boy bilinmiyor.
 *
 * Brüt m (63.00) hesaplanabilir; sipariş, artan ve ağırlık `null`'dır — `0`
 * değil. Arayüz bu ayrımı korumalıdır.
 */
export function makePartialCalculation(): CalculateResponse {
  return {
    groups: [
      groupFromSpec({
        code: 'BOX-100-4-S235-B',
        status: 'PARTIAL',
        mass: '11.70',
        length: null,
        bars: null,
        gross: '63.00',
        order: null,
        surplus: null,
        weight: null,
        merged: false,
        missingFields: ['commercial-length'],
        missing: [
          {
            field: 'commercial-length',
            message:
              'Ticari boy tanımlı değil. Varsayılan boy kullanılmaz; sipariş miktarı yuvarlanamadı.',
            boq_no: null,
            source_row: null,
          },
        ],
        notes: [
          'Teorik ağırlık hesaplanmadı: ticari boy bilinmediği için sipariş uzunluğu üretilemedi.',
        ],
        sources: [
          sourceRow({
            row: 2,
            no: 'BOQ-100',
            description: 'BOX 100×100×4 S235 siyah',
            quantity: '60',
            unit: 'm',
            net: '60',
            waste: '5',
            gross: '63.00',
            grossQuantity: '63.00',
            fire: '3.00',
            steps: ['Zaten metre: miktar (m) = 60'],
          }),
        ],
      }),
    ],
    skipped: [],
    summary: {
      input_rows: 1,
      calculated_rows: 1,
      skipped_rows: 0,
      groups: 1,
      merged_groups: 0,
      merges: 0,
      full_groups: 0,
      partial_groups: 1,
      total_order_length_m: null,
      known_weight_kg: '0',
      weight_complete: false,
    },
    warnings: [],
  }
}

/* --------------------------------------------------------------------------
 * Calculate isteği (rapor gövdesi de aynısıdır)
 * -------------------------------------------------------------------------- */

/** Demo metrajın ham satırları — yalnızca istemcinin göndermesi izinli alanlar. */
export function demoRequest(): CalculateRequest {
  return {
    rows: DEMO_ROW_SPECS.map((spec) => ({
      source_row: spec.row,
      boq_no: spec.no,
      description: spec.description,
      quantity: spec.quantity as string,
      unit: spec.unit as string,
      waste_percent: spec.waste,
    })),
    decisions: [
      {
        boq_no: 'BOQ-003',
        action: 'approve',
        code: 'IPE-200-S235',
        reason: 'Kalite ve kaplama açıklamada yok; demo kararı S235 siyah.',
      },
      {
        boq_no: 'BOQ-004',
        action: 'approve',
        code: 'IPE-240-S355',
        reason: 'Kaplama belirtilmemiş; demo kararı siyah.',
      },
      {
        boq_no: 'BOQ-006',
        action: 'approve',
        code: 'HEA-200-S235',
        reason: 'Kalite ve kaplama eksik; demo kararı S235 siyah.',
      },
      {
        boq_no: 'BOQ-018',
        action: 'reject',
        code: null,
        reason:
          'Kalite çelişkisi: açıklamada S355, katalogda IPE 200 yalnızca S235. Kalite düşürülmez.',
      },
    ],
  }
}

/* --------------------------------------------------------------------------
 * Hata zarfları — `backend/app/api/errors.py` ile birebir
 * -------------------------------------------------------------------------- */

export function errorEnvelope(
  code: string,
  message: string,
  options: {
    detail?: string
    suggestion?: string
    issues?: FieldIssue[]
  } = {},
) {
  return {
    error: {
      code,
      message,
      detail: options.detail ?? '',
      suggestion: options.suggestion ?? '',
      issues: options.issues ?? [],
    },
  }
}

export const MISSING_COLUMN_ERROR = errorEnvelope(
  'missing-column',
  'Zorunlu kolon(lar) eksik: Birim',
  {
    detail: 'Bulunan kolonlar: BOQ No, Açıklama, Miktar',
    suggestion:
      "Şablondaki başlıkları kullanın: 'BOQ No', 'Açıklama', 'Miktar', 'Birim', 'Fire (%)'.",
  },
)

export const INVALID_DECISION_ERROR = errorEnvelope(
  'invalid-decision',
  'Kullanıcı kararı geçersiz.',
  {
    detail: "BOQ-009: 'FLAT-40x5-S235-G' kodu satırın açıklamasıyla çelişiyor.",
    suggestion:
      'Yalnızca sunucunun döndürdüğü aday kodlar arasından seçim yapın.',
    issues: [
      {
        source_row: null,
        boq_no: 'BOQ-009',
        column: null,
        code: 'FLAT-40x5-S235-G',
        message: 'Kod satırın açıklamasıyla çelişiyor.',
        suggestion: 'Sunucunun döndürdüğü aday kodlardan birini seçin.',
      },
    ],
  },
)

export const REPORT_EMPTY_ERROR = errorEnvelope(
  'report-empty',
  'Rapor üretilecek onaylanmış kalem yok.',
  {
    detail: 'Hiçbir satır hesaba girmedi.',
    suggestion:
      'Eşleştirme ekranında en az bir satırı onaylayın ve yeniden hesaplayın.',
  },
)

export const CORRUPT_FILE_ERROR = errorEnvelope(
  'corrupt-file',
  'Dosya geçerli bir .xlsx paketi değil.',
  {
    detail: 'Dosya okunamadı.',
    suggestion: 'Dosyayı Excel ile yeniden kaydedip tekrar yükleyin.',
  },
)
