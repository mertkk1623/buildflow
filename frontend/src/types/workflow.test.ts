import { describe, expect, it } from 'vitest'

import {
  EXCLUSION_LABEL,
  SKIP_LABEL,
  aiSuggestionView,
  countStatuses,
  decisionCapability,
  deriveReviewRows,
  deriveReviewStatus,
  findCandidate,
  matchMessage,
  type RowDecision,
} from './workflow'
import {
  AI_AMBIGUOUS_FLAT,
  AI_ERROR_HEA,
  AI_NO_MATCH,
  AI_SUGGESTED_IPE200,
  analysisWithAi,
  makeAnalysis,
} from '../test/fixtures/demo'

/**
 * Görünüm modeli testleri.
 *
 * Kritik kural: **AI önerisi tek başına hiçbir zaman `ai-approved` üretmez.**
 * Bu, ürünün en önemli güvenlik iddiasıdır ve burada kilitlenir.
 */

const AI_ROWS = analysisWithAi().rows

function rowByNo(rows: ReturnType<typeof makeAnalysis>['rows'], boqNo: string) {
  const row = rows.find((item) => item.boq_no === boqNo)
  if (!row) throw new Error(`Satır bulunamadı: ${boqNo}`)
  return row
}

describe('deriveReviewStatus', () => {
  it('karar yokken sunucu durumunu aynen verir', () => {
    const row = rowByNo(makeAnalysis().rows, 'BOQ-003')
    expect(deriveReviewStatus(row, null)).toBe('pending')
  })

  it('onay kararı `ai-approved` üretir', () => {
    const row = rowByNo(makeAnalysis().rows, 'BOQ-003')
    expect(deriveReviewStatus(row, { action: 'approve', code: 'IPE-200-S235', reason: '' })).toBe(
      'ai-approved',
    )
  })

  it('red kararı `rejected` üretir', () => {
    const row = rowByNo(makeAnalysis().rows, 'BOQ-003')
    expect(deriveReviewStatus(row, { action: 'reject', reason: '' })).toBe('rejected')
  })

  it('AI önerisi olan satır karar olmadan `pending` kalır', () => {
    const row = rowByNo(AI_ROWS, 'BOQ-003')
    expect(row.ai?.suggestion?.status).toBe('suggested')
    expect(deriveReviewStatus(row, null)).toBe('pending')
  })

  it('AI belirsiz/eşleşme yok/hata durumları karar üretmez', () => {
    for (const boqNo of ['BOQ-004', 'BOQ-006', 'BOQ-009']) {
      const row = rowByNo(AI_ROWS, boqNo)
      expect(row.ai).not.toBeNull()
      expect(deriveReviewStatus(row, null)).toBe('pending')
    }
  })
})

describe('deriveReviewRows', () => {
  it('AI önerileri uygulandıktan sonra bile hiçbir satır otomatik onaylanmaz', () => {
    const rows = deriveReviewRows(AI_ROWS, {})
    const counts = countStatuses(rows)

    expect(counts['ai-approved']).toBe(0)
    expect(counts.rejected).toBe(0)
    // Analizdeki 4 onay bekleyen satır hâlâ onay bekliyor.
    expect(counts.pending).toBe(4)
  })

  it('onay kararı eşleşen kodu kullanıcı koduna çevirir', () => {
    const decisions: Record<string, RowDecision> = {
      'BOQ-009': { action: 'approve', code: 'FLAT-40x5-S235-G', reason: '' },
    }
    const rows = deriveReviewRows(makeAnalysis().rows, decisions)
    const entry = rows.find((row) => row.row.boq_no === 'BOQ-009')!

    expect(entry.status).toBe('ai-approved')
    expect(entry.matchedCode).toBe('FLAT-40x5-S235-G')
    expect(entry.decision).toEqual(decisions['BOQ-009'])
  })

  it('red kararı eşleşen kodu temizler', () => {
    const rows = deriveReviewRows(makeAnalysis().rows, {
      'BOQ-018': { action: 'reject', reason: 'kalite çelişkisi' },
    })
    const entry = rows.find((row) => row.row.boq_no === 'BOQ-018')!

    expect(entry.status).toBe('rejected')
    expect(entry.matchedCode).toBeNull()
  })

  it('kural satırı karar verilmeden eşleşmiş kodu korur', () => {
    const rows = deriveReviewRows(makeAnalysis().rows, {})
    const entry = rows.find((row) => row.row.boq_no === 'BOQ-001')!

    expect(entry.status).toBe('rule')
    expect(entry.matchedCode).toBe('BOX-100-4-S235-B')
  })

  it('BOQ No boş satır için karar aramaz', () => {
    const rows = makeAnalysis().rows
    const withoutNo = { ...rows[0], boq_no: null }
    const [entry] = deriveReviewRows([withoutNo], {
      '': { action: 'approve', code: 'X', reason: '' },
    })
    expect(entry.decision).toBeNull()
    expect(entry.matchedCode).toBe('BOX-100-4-S235-B')
  })

  it('ham analiz satırını değiştirmez', () => {
    const analysis = makeAnalysis()
    const before = JSON.stringify(analysis.rows)
    deriveReviewRows(analysis.rows, {
      'BOQ-003': { action: 'approve', code: 'IPE-200-S235', reason: '' },
    })
    expect(JSON.stringify(analysis.rows)).toBe(before)
  })
})

describe('countStatuses', () => {
  it('demo dağılımını doğru sayar (karar öncesi)', () => {
    const counts = countStatuses(deriveReviewRows(makeAnalysis().rows, {}))
    expect(counts).toEqual({
      rule: 10,
      'ai-approved': 0,
      pending: 4,
      rejected: 0,
      excluded: 4,
      invalid: 0,
    })
  })

  it('kararlar uygulandığında onay/red sayıları değişir', () => {
    const counts = countStatuses(
      deriveReviewRows(makeAnalysis().rows, {
        'BOQ-003': { action: 'approve', code: 'IPE-200-S235', reason: '' },
        'BOQ-004': { action: 'approve', code: 'IPE-240-S355', reason: '' },
        'BOQ-006': { action: 'approve', code: 'HEA-200-S235', reason: '' },
        'BOQ-018': { action: 'reject', reason: '' },
      }),
    )

    expect(counts['ai-approved']).toBe(3)
    expect(counts.rejected).toBe(1)
    expect(counts.pending).toBe(1)
    expect(counts.rule).toBe(10)
    // BOQ-018 `excluded` iken red kararıyla `rejected` olur: hariç 3'e düşer.
    expect(counts.excluded).toBe(3)
    expect(counts.invalid).toBe(0)
  })

  it('boş listede tüm sayaçlar sıfırdır', () => {
    expect(countStatuses([])).toEqual({
      rule: 0,
      'ai-approved': 0,
      pending: 0,
      rejected: 0,
      excluded: 0,
      invalid: 0,
    })
  })
})

describe('decisionCapability', () => {
  it('yalnızca pending satırda karar verilebilir', () => {
    const rows = deriveReviewRows(makeAnalysis().rows, {})
    for (const entry of rows) {
      const capability = decisionCapability(entry)
      expect(capability.canDecide).toBe(entry.row.status === 'pending')
    }
  })

  it('karar verilmiş satırda geri alma mümkündür', () => {
    const rows = deriveReviewRows(makeAnalysis().rows, {
      'BOQ-003': { action: 'approve', code: 'IPE-200-S235', reason: '' },
    })
    const entry = rows.find((row) => row.row.boq_no === 'BOQ-003')!
    const capability = decisionCapability(entry)

    expect(capability.canDecide).toBe(false)
    expect(capability.canReset).toBe(true)
  })

  it('adaylar sunucudan geldiği gibi aktarılır', () => {
    const rows = deriveReviewRows(makeAnalysis().rows, {})
    const entry = rows.find((row) => row.row.boq_no === 'BOQ-009')!
    const capability = decisionCapability(entry)

    expect(capability.candidates.map((candidate) => candidate.code)).toEqual([
      'FLAT-40x5-S235-B',
      'FLAT-40x5-S235-G',
    ])
    expect(capability.candidates[0].label).toContain('Lama')
  })

  it('hariç tutulmuş satırda karar verilemez', () => {
    const rows = deriveReviewRows(makeAnalysis().rows, {})
    const entry = rows.find((row) => row.row.boq_no === 'BOQ-014')!
    expect(decisionCapability(entry).canDecide).toBe(false)
    expect(decisionCapability(entry).canReset).toBe(false)
  })
})

describe('aiSuggestionView', () => {
  it('null → AI çalışmadı', () => {
    expect(aiSuggestionView(null)).toEqual({ kind: 'none' })
  })

  it('öneri kod, güven ve gerekçeyi taşır', () => {
    const view = aiSuggestionView(AI_SUGGESTED_IPE200)
    expect(view).toMatchObject({
      kind: 'suggested',
      code: 'IPE-200-S235',
      confidence: '0.9',
    })
  })

  it('belirsiz öneri aday kodlarını listeler', () => {
    const view = aiSuggestionView(AI_AMBIGUOUS_FLAT)
    expect(view.kind).toBe('ambiguous')
    if (view.kind !== 'ambiguous') return
    expect(view.candidateCodes).toEqual(['FLAT-40x5-S235-B', 'FLAT-40x5-S235-G'])
  })

  it('eşleşme yok durumunu ayrı gösterir', () => {
    expect(aiSuggestionView(AI_NO_MATCH).kind).toBe('no_match')
  })

  it('sağlayıcı hatasını kullanıcıya gösterilebilir metinle verir', () => {
    const view = aiSuggestionView(AI_ERROR_HEA)
    expect(view.kind).toBe('error')
    if (view.kind !== 'error') return
    expect(view.code).toBe('provider-unavailable')
    expect(view.message).toContain('ulaşılamadı')
  })

  it('öneri kodu boşsa öneri olarak sunulmaz', () => {
    const view = aiSuggestionView({
      suggestion: {
        status: 'suggested',
        suggested_code: null,
        confidence: null,
        reason: 'x',
        candidate_codes: [],
      },
      error: null,
    })
    expect(view.kind).toBe('suggested')
    if (view.kind !== 'suggested') return
    expect(view.code).toBe('')
  })
})

describe('yardımcılar', () => {
  it('findCandidate adayı bulur, bulunamazsa undefined verir', () => {
    const [row] = makeAnalysis().rows
    expect(findCandidate(row.match.candidates, 'BOX-100-4-S235-B')?.family).toBe('BOX')
    expect(findCandidate(row.match.candidates, 'YOK')).toBeUndefined()
  })

  it('matchMessage sunucu metnini aynen verir', () => {
    const [row] = makeAnalysis().rows
    expect(matchMessage(row.match)).toBe(row.match.message)
  })

  it('hariç tutma ve atlama etiketleri eksiksiz', () => {
    expect(EXCLUSION_LABEL.waste).toBe('Fire tanımsız')
    expect(EXCLUSION_LABEL.unit).toBe('Birim desteklenmiyor')
    expect(EXCLUSION_LABEL.catalog).toBe('Katalog dışı')
    expect(EXCLUSION_LABEL['missing-mass']).toBeDefined()
    expect(SKIP_LABEL.pending).toBe('Onay bekliyor')
    expect(SKIP_LABEL.rejected).toBe('Kullanıcı reddetti')
    expect(SKIP_LABEL['unknown-code']).toBeDefined()
  })
})
