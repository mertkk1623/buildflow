import { describe, expect, it } from 'vitest'

import {
  approveDecision,
  buildCalculateRequest,
  isSendableRow,
  rejectDecision,
} from './payload'
import type { AnalyzeRow } from '../types/api'
import type { RowDecision } from '../types/workflow'
import { analysisWithInvalidRow, makeAnalysis } from '../test/fixtures/demo'

/**
 * İstek gövdesi testleri.
 *
 * Buradaki asıl iddia "alanlar doğru" değil, **fazladan alan yok**: sunucu
 * `extra="forbid"` uygular ve eşleşme/hesap alanları gönderilirse isteği
 * reddeder. Testler gövdeyi JSON'a çevirip anahtar kümesini birebir doğrular.
 */

const ALLOWED_ROW_KEYS = [
  'source_row',
  'boq_no',
  'description',
  'quantity',
  'unit',
  'waste_percent',
].sort()

const ALLOWED_DECISION_KEYS = ['boq_no', 'action', 'code', 'reason'].sort()

function rowKeys(payload: unknown): string[] {
  const rows = (payload as { rows: Record<string, unknown>[] }).rows
  return [...new Set(rows.flatMap((row) => Object.keys(row)))].sort()
}

describe('isSendableRow', () => {
  it('sağlıklı satırı gönderilebilir sayar', () => {
    const [row] = makeAnalysis().rows
    expect(isSendableRow(row)).toBe(true)
  })

  it('geçersiz satırı reddeder', () => {
    const rows = analysisWithInvalidRow().rows
    const invalid = rows.find((row) => row.status === 'invalid')!
    expect(isSendableRow(invalid)).toBe(false)
  })

  it.each([
    ['boq_no boş', { boq_no: '   ' }],
    ['açıklama boş', { description: '' }],
    ['birim boş', { unit: ' ' }],
    ['miktar yok', { quantity: null }],
    ['miktar sıfır', { quantity: '0' }],
    ['miktar negatif', { quantity: '-3' }],
    ['miktar okunamaz', { quantity: 'abc' }],
    ['satır numarası 1', { source_row: 1 }],
  ])('%s → gönderilemez', (_label, patch) => {
    const [base] = makeAnalysis().rows
    const row: AnalyzeRow = { ...base, ...patch }
    expect(isSendableRow(row)).toBe(false)
  })

  it('miktarı float’a çevirmez; ham metni korur', () => {
    const row = makeAnalysis().rows.find((item) => item.boq_no === 'BOQ-004')!
    expect(row.quantity).toBe('0.84')
  })
})

describe('buildCalculateRequest — gövde güvenliği', () => {
  const analysis = makeAnalysis()
  const decisions: Record<string, RowDecision> = {
    'BOQ-003': approveDecision('IPE-200-S235'),
    'BOQ-004': rejectDecision(),
  }

  it('yalnızca ClientRow alanlarını gönderir', () => {
    const { request } = buildCalculateRequest(analysis.rows, decisions)
    expect(rowKeys(request)).toEqual(ALLOWED_ROW_KEYS)
  })

  it('istek JSON’unda eşleşme/hesap alanı yoktur', () => {
    const { request } = buildCalculateRequest(analysis.rows, decisions)
    const serialized = JSON.stringify(request)

    for (const forbidden of [
      'matched_code',
      'match_status',
      'match',
      'candidates',
      'ai',
      'status',
      'net_metres',
      'gross_metres',
      'weight_kg',
      'order_length_m',
      'bar_count',
      'fire_quantity',
      'conversion_steps',
      'waste_source',
      'mass_kg_per_m',
    ]) {
      expect(serialized).not.toContain(`"${forbidden}"`)
    }
  })

  it('karar gövdesi yalnızca dört alan taşır ve durum alanı yoktur', () => {
    const { request } = buildCalculateRequest(analysis.rows, decisions)
    expect(request.decisions.length).toBe(2)

    for (const decision of request.decisions) {
      expect(Object.keys(decision).sort()).toEqual(ALLOWED_DECISION_KEYS)
      expect(JSON.stringify(decision)).not.toContain('"status"')
    }
  })

  it('reddedilen karar kod taşımaz', () => {
    const { request } = buildCalculateRequest(analysis.rows, decisions)
    const reject = request.decisions.find((item) => item.action === 'reject')!
    expect(reject.code).toBeNull()
  })

  it('onaylanan karar kodu aynen taşır', () => {
    const { request } = buildCalculateRequest(analysis.rows, decisions)
    const approve = request.decisions.find((item) => item.action === 'approve')!
    expect(approve.code).toBe('IPE-200-S235')
    expect(approve.reason.length).toBeGreaterThan(0)
  })

  it('18 satırın tamamını, sayıları değiştirmeden gönderir', () => {
    const { request, unsendable } = buildCalculateRequest(analysis.rows, {})
    expect(request.rows).toHaveLength(18)
    expect(unsendable).toEqual([])
    expect(request.decisions).toEqual([])
  })

  it('miktar ve fire ham metin olarak kalır', () => {
    const { request } = buildCalculateRequest(analysis.rows, {})
    const byNo = new Map(request.rows.map((row) => [row.boq_no, row]))

    expect(byNo.get('BOQ-001')?.quantity).toBe('96')
    expect(byNo.get('BOQ-004')?.quantity).toBe('0.84')
    expect(byNo.get('BOQ-006')?.quantity).toBe('3.2')
    expect(byNo.get('BOQ-012')?.waste_percent).toBeNull()
    expect(typeof byNo.get('BOQ-004')?.quantity).toBe('string')
  })

  it('eşleşmiş olsa bile sunucunun kodu gövdeye sızmaz', () => {
    const { request } = buildCalculateRequest(analysis.rows, {})
    expect(JSON.stringify(request)).not.toContain('BOX-100-4-S235-B')
  })
})

describe('buildCalculateRequest — atlanan satırların korunumu', () => {
  it('geçersiz satırı isteğe koymaz, nedeniyle birlikte döndürür', () => {
    const analysis = analysisWithInvalidRow()
    const { request, unsendable } = buildCalculateRequest(analysis.rows, {})

    expect(request.rows.map((row) => row.boq_no)).not.toContain('BOQ-019')
    expect(request.rows).toHaveLength(18)

    const dropped = unsendable.find((row) => row.boq_no === 'BOQ-019')
    expect(dropped).toBeDefined()
    expect(dropped?.status).toBe('invalid')
    expect(dropped?.message).toContain('Miktar okunamadı')
    expect(dropped?.source_row).toBe(20)
  })

  it('hiçbir satır sessizce kaybolmaz: istek + atlanan = tüm satırlar', () => {
    const analysis = analysisWithInvalidRow()
    const { request, unsendable } = buildCalculateRequest(analysis.rows, {})
    expect(request.rows.length + unsendable.length).toBe(analysis.rows.length)
  })

  it('yinelenen BOQ No ikinci satırı göndermez', () => {
    const analysis = makeAnalysis()
    const duplicate: AnalyzeRow = {
      ...analysis.rows[0],
      source_row: 99,
      description: 'kopya satır',
    }
    const { request, unsendable } = buildCalculateRequest(
      [...analysis.rows, duplicate],
      {},
    )

    expect(request.rows.filter((row) => row.boq_no === 'BOQ-001')).toHaveLength(1)
    expect(unsendable).toHaveLength(1)
    expect(unsendable[0].message).toContain('Aynı BOQ No')
  })

  it('gönderilemeyen satırın kararı da gönderilmez', () => {
    const analysis = analysisWithInvalidRow()
    const { request } = buildCalculateRequest(analysis.rows, {
      'BOQ-019': approveDecision('BOX-100-4-S235-B'),
    })
    expect(request.decisions.some((item) => item.boq_no === 'BOQ-019')).toBe(false)
  })

  it('olmayan BOQ No için karar sessizce atlanır', () => {
    const analysis = makeAnalysis()
    const { request } = buildCalculateRequest(analysis.rows, {
      'BOQ-999': approveDecision('BOX-100-4-S235-B'),
    })
    expect(request.decisions).toEqual([])
  })
})

describe('buildCalculateRequest — kaynak kimliği', () => {
  it('source_row ve boq_no tekildir', () => {
    const { request } = buildCalculateRequest(makeAnalysis().rows, {})
    const rows = request.rows.map((row) => row.source_row)
    const numbers = request.rows.map((row) => row.boq_no)

    expect(new Set(rows).size).toBe(rows.length)
    expect(new Set(numbers).size).toBe(numbers.length)
  })

  it('source_row Excel satır numarasını korur', () => {
    const { request } = buildCalculateRequest(makeAnalysis().rows, {})
    const first = request.rows[0]
    expect(first.source_row).toBe(2)
    expect(first.boq_no).toBe('BOQ-001')
  })

  it('demoyla aynı sonucu üretir: 18 satır, 4 karar', () => {
    const { request } = buildCalculateRequest(makeAnalysis().rows, {
      'BOQ-003': approveDecision('IPE-200-S235'),
      'BOQ-004': approveDecision('IPE-240-S355'),
      'BOQ-006': approveDecision('HEA-200-S235'),
      'BOQ-018': rejectDecision(),
    })
    expect(request.rows).toHaveLength(18)
    expect(request.decisions).toHaveLength(4)
    expect(request.decisions.filter((item) => item.action === 'approve')).toHaveLength(3)
    expect(request.decisions.filter((item) => item.action === 'reject')).toHaveLength(1)
  })
})
