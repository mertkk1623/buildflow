import { act, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  WorkflowProvider,
  toWorkflowError,
  useWorkflow,
  type WorkflowContextValue,
} from './WorkflowContext'
import { ApiAbortError, ApiConnectionError, ApiError } from '../lib/api'
import type { RowDecision } from '../types/workflow'
import {
  MISSING_COLUMN_ERROR,
  analysisWithAi,
  analysisWithInvalidRow,
  makeAnalysis,
  makeCalculation,
  makePartialCalculation,
} from '../test/fixtures/demo'
import {
  callsTo,
  errorResponse,
  installFetchMock,
  jsonResponse,
} from '../test/server'
import { metrajFile } from '../test/harness'

/**
 * Akış katmanı testleri.
 *
 * Testler sahte state kurmaz: `analyze` ve `runCalculation` gerçek `fetch`
 * taklidiyle çalışır. Böylece "ekrana ne gidiyor" ile "sunucuya ne gidiyor"
 * aynı akışta doğrulanır.
 */

let workflow: WorkflowContextValue

function Probe() {
  workflow = useWorkflow()
  return (
    <div>
      <span data-testid="stage">{workflow.stage}</span>
      <span data-testid="total">{workflow.total}</span>
      <span data-testid="eligible">{workflow.eligibleCount}</span>
      <span data-testid="held">{workflow.heldCount}</span>
      <span data-testid="error">{workflow.error?.title ?? ''}</span>
      <span data-testid="errorStage">{workflow.error?.stage ?? ''}</span>
      <span data-testid="calc">
        {workflow.calculation?.summary.total_order_length_m ?? 'yok'}
      </span>
      <span data-testid="unsendable">{workflow.unsendable.length}</span>
    </div>
  )
}

function setup() {
  render(
    <WorkflowProvider>
      <Probe />
    </WorkflowProvider>,
  )
}

async function analyzeDemo() {
  const file = metrajFile('metraj.xlsx')
  await act(async () => {
    await workflow.analyze(file)
  })
}


describe('analyze', () => {
  it('analizi sunucudan alır ve görünüme aktarır', async () => {
    const analysis = makeAnalysis()
    installFetchMock({ 'POST /api/analyze': () => jsonResponse(analysis) })
    setup()

    const file = metrajFile('metraj.xlsx')
    await act(async () => {
      await workflow.analyze(file)
    })

    expect(screen.getByTestId('stage').textContent).toBe('reviewing')
    expect(screen.getByTestId('total').textContent).toBe('18')
    expect(workflow.analysis).toEqual(analysis)
    expect(workflow.fileName).toBe('metraj.xlsx')
    expect(workflow.fileSize).toBe(file.size)
    expect(workflow.analyzeView?.sheetName).toBe('Metraj')
    expect(workflow.analyzeView?.summary.pending).toBe(4)
    expect(workflow.rows).toHaveLength(18)
  })

  it('hesaba uygun / hesap dışı sayılarını türetir', async () => {
    installFetchMock({ 'POST /api/analyze': () => jsonResponse(makeAnalysis()) })
    setup()
    await analyzeDemo()

    // 10 kural satırı eşleşmiş; 4 pending + 4 excluded hesap dışı.
    expect(screen.getByTestId('eligible').textContent).toBe('10')
    expect(screen.getByTestId('held').textContent).toBe('8')
  })

  it('uyarıları ve yok sayılan sütunları korur', async () => {
    installFetchMock({
      'POST /api/analyze': () =>
        jsonResponse(
          analysisWithInvalidRow(),
        ),
    })
    setup()
    await analyzeDemo()

    expect(workflow.analyzeView?.warnings).toEqual([
      '1 satır veri olarak okunamadı; hesaba katılmaz.',
    ])
    expect(workflow.counts.invalid).toBe(1)
    expect(workflow.total).toBe(19)
  })

  it('AI çıktısını satırlara taşır, otomatik onaylamaz', async () => {
    installFetchMock({ 'POST /api/analyze': () => jsonResponse(analysisWithAi()) })
    setup()
    await analyzeDemo()

    expect(workflow.analyzeView?.aiEnabled).toBe(true)
    expect(workflow.analyzeView?.aiSuggested).toBe(1)
    expect(workflow.analyzeView?.aiErrors).toBe(1)

    expect(workflow.counts['ai-approved']).toBe(0)
    expect(workflow.counts.pending).toBe(4)
  })

  it('analiz hatasını kullanıcıya gösterilebilir biçimde saklar', async () => {
    installFetchMock({
      'POST /api/analyze': () => errorResponse(MISSING_COLUMN_ERROR.error, 422),
    })
    setup()
    await analyzeDemo()

    expect(screen.getByTestId('stage').textContent).toBe('error')
    expect(screen.getByTestId('errorStage').textContent).toBe('analyze')
    expect(workflow.error?.title).toContain('eksik')
    expect(workflow.error?.suggestion).toContain('Şablondaki başlıkları')
    expect(workflow.analysis).toBeNull()
  })

  it('bağlantı hatasında ham ayrıntı göstermez', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )
    setup()
    await analyzeDemo()

    expect(workflow.stage).toBe('error')
    expect(workflow.error?.title).toBe('Bağlantı kurulamadı')
    expect(workflow.error?.suggestion).toContain('Backend servisinin')
    expect(JSON.stringify(workflow.error)).not.toContain('Failed to fetch')
  })

  it('yeni dosya seçildiğinde eski kararlar ve sonuç temizlenir', async () => {
    installFetchMock({ 'POST /api/analyze': () => jsonResponse(makeAnalysis()) })
    setup()
    await analyzeDemo()

    act(() => {
      workflow.approveRow('BOQ-003', 'IPE-200-S235')
    })
    expect(workflow.rows.filter((row) => row.decision !== null)).toHaveLength(1)

    await analyzeDemo()
    expect(workflow.rows.every((row) => row.decision === null)).toBe(true)
    expect(workflow.calculation).toBeNull()
  })
})

describe('kararlar', () => {
  beforeEach(async () => {
    installFetchMock({ 'POST /api/analyze': () => jsonResponse(makeAnalysis()) })
    setup()
    await analyzeDemo()
  })

  it('onay kararı satırı listeye katar', () => {
    act(() => {
      workflow.approveRow('BOQ-003', 'IPE-200-S235')
    })

    const entry = workflow.rows.find((row) => row.row.boq_no === 'BOQ-003')!
    expect(entry.status).toBe('ai-approved')
    expect(entry.matchedCode).toBe('IPE-200-S235')
    expect(workflow.counts['ai-approved']).toBe(1)
    expect(workflow.counts.pending).toBe(3)
    expect(workflow.eligibleCount).toBe(11)
  })

  it('AI önerisi olan satır karar verilmeden hesaba girmez', async () => {
    // AI'lı analiz yükle.
    installFetchMock({ 'POST /api/analyze': () => jsonResponse(analysisWithAi()) })
    await analyzeDemo()

    expect(workflow.eligibleCount).toBe(10)
    expect(workflow.rows.every((row) => row.decision === null)).toBe(true)

    // Alternatif kodla onayla → listeye girer.
    act(() => {
      workflow.approveRow('BOQ-009', 'FLAT-40x5-S235-G')
    })
    expect(workflow.eligibleCount).toBe(11)
  })

  it('red kararı satırı hesap dışı bırakır', () => {
    act(() => {
      workflow.rejectRow('BOQ-018')
    })

    const entry = workflow.rows.find((row) => row.row.boq_no === 'BOQ-018')!
    expect(entry.status).toBe('rejected')
    expect(entry.matchedCode).toBeNull()
    expect(workflow.counts.rejected).toBe(1)
  })

  it('karar geri alınabilir', () => {
    act(() => {
      workflow.approveRow('BOQ-003', 'IPE-200-S235')
    })
    act(() => {
      workflow.clearDecision('BOQ-003')
    })

    const entry = workflow.rows.find((row) => row.row.boq_no === 'BOQ-003')!
    expect(entry.status).toBe('pending')
    expect(entry.decision).toBeNull()
    expect(workflow.rows.filter((row) => row.decision !== null)).toHaveLength(0)
  })

  it('karar değişince eski hesaplama geçersizleşir', async () => {
    installFetchMock({
      'POST /api/analyze': () => jsonResponse(makeAnalysis()),
      'POST /api/calculate': () => jsonResponse(makeCalculation()),
    })
    await analyzeDemo()

    await act(async () => {
      await workflow.runCalculation()
    })
    expect(workflow.calculation).not.toBeNull()

    act(() => {
      workflow.approveRow('BOQ-009', 'FLAT-40x5-S235-B')
    })
    expect(workflow.calculation).toBeNull()
    expect(workflow.calculationRequest).toBeNull()
  })
})

describe('runCalculation', () => {
  it('istenen gövdeyi gönderir ve yanıtı olduğu gibi saklar', async () => {
    const calculation = makeCalculation()
    const { calls } = installFetchMock({
      'POST /api/analyze': () => jsonResponse(makeAnalysis()),
      'POST /api/calculate': () => jsonResponse(calculation),
    })
    setup()
    await analyzeDemo()

    const decisions: Record<string, RowDecision> = {
      'BOQ-003': { action: 'approve', code: 'IPE-200-S235', reason: 'demo' },
      'BOQ-018': { action: 'reject', reason: 'demo' },
    }
    act(() => {
      workflow.approveRow('BOQ-003', decisions['BOQ-003'].action === 'approve' ? (decisions['BOQ-003'] as { code: string }).code : '')
      workflow.rejectRow('BOQ-018')
    })

    await act(async () => {
      await workflow.runCalculation()
    })

    expect(screen.getByTestId('stage').textContent).toBe('done')
    expect(workflow.calculation).toEqual(calculation)
    expect(workflow.calculation?.summary.known_weight_kg).toBe('18005.820')

    const [call] = callsTo(calls, 'POST', '/api/calculate')
    const body = call.json as {
      rows: { boq_no: string; quantity: string }[]
      decisions: { boq_no: string; action: string; code: string | null }[]
    }

    expect(body.rows).toHaveLength(18)
    expect(body.decisions).toHaveLength(2)
    expect(body.rows[0]).toEqual({
      source_row: 2,
      boq_no: 'BOQ-001',
      description: 'BOX 100×100×4 S235 siyah',
      quantity: '96',
      unit: 'm',
      waste_percent: '5',
    })
    expect(JSON.stringify(body)).not.toContain('matched_code')
  })

  it('rapor için aynı gövdeyi saklar', async () => {
    installFetchMock({
      'POST /api/analyze': () => jsonResponse(makeAnalysis()),
      'POST /api/calculate': () => jsonResponse(makeCalculation()),
    })
    setup()
    await analyzeDemo()

    await act(async () => {
      await workflow.runCalculation()
    })

    expect(workflow.calculationRequest).not.toBeNull()
    expect(workflow.calculationRequest?.rows).toHaveLength(18)
  })

  it('PARTIAL sonucu bozmadan saklar', async () => {
    installFetchMock({
      'POST /api/analyze': () => jsonResponse(makeAnalysis()),
      'POST /api/calculate': () => jsonResponse(makePartialCalculation()),
    })
    setup()
    await analyzeDemo()

    await act(async () => {
      await workflow.runCalculation()
    })

    const group = workflow.calculation!.groups[0]
    expect(group.status).toBe('PARTIAL')
    expect(group.order_length_m).toBeNull()
    expect(group.weight_kg).toBeNull()
    expect(group.total_gross_metres).toBe('63.00')
    expect(workflow.calculation!.summary.weight_complete).toBe(false)
  })

  it('gönderilemeyen satırları korur', async () => {
    installFetchMock({
      'POST /api/analyze': () => jsonResponse(analysisWithInvalidRow()),
      'POST /api/calculate': () => jsonResponse(makeCalculation()),
    })
    setup()
    await analyzeDemo()

    await act(async () => {
      await workflow.runCalculation()
    })

    expect(workflow.unsendable).toHaveLength(1)
    expect(workflow.unsendable[0].boq_no).toBe('BOQ-019')
    expect(screen.getByTestId('unsendable').textContent).toBe('1')
  })

  it('hesaplama hatasında aşamayı error yapar, eski sonucu temizler', async () => {
    installFetchMock({
      'POST /api/analyze': () => jsonResponse(makeAnalysis()),
      'POST /api/calculate': () =>
        errorResponse(
          { code: 'invalid-decision', message: 'Kullanıcı kararı geçersiz.', detail: 'x', suggestion: 'y' },
          409,
        ),
    })
    setup()
    await analyzeDemo()

    let result = null
    await act(async () => {
      result = await workflow.runCalculation()
    })

    expect(result).toBeNull()
    expect(workflow.stage).toBe('error')
    expect(workflow.error?.stage).toBe('calculate')
    expect(workflow.error?.title).toBe('Kullanıcı kararı geçersiz.')
    expect(workflow.calculation).toBeNull()
  })

  it('analiz yoksa çağrı yapmaz', async () => {
    const { calls } = installFetchMock()
    setup()

    let result = null
    await act(async () => {
      result = await workflow.runCalculation()
    })

    expect(result).toBeNull()
    expect(callsTo(calls, 'POST', '/api/calculate')).toHaveLength(0)
  })
})

describe('şablon indirme', () => {
  it('şablonu indirir ve durumu idle’a döndürür', async () => {
    const { calls } = installFetchMock({
      'GET /api/template': () =>
        new Response('xlsx', {
          status: 200,
          headers: {
            'Content-Type':
              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'Content-Disposition': 'attachment; filename="buildflow-metraj-sablonu.xlsx"',
          },
        }),
    })
    setup()

    await act(async () => {
      await workflow.saveTemplate()
    })

    expect(callsTo(calls, 'GET', '/api/template')).toHaveLength(1)
    expect(workflow.templateStatus).toBe('idle')
    expect(workflow.templateError).toBeNull()
  })

  it('şablon hatasını ayrı tutar (analiz akışını bozmaz)', async () => {
    installFetchMock({
      'GET /api/template': () =>
        errorResponse({ code: 'server-error', message: 'Şablon üretilemedi.' }, 500),
    })
    setup()

    await act(async () => {
      await workflow.saveTemplate()
    })

    expect(workflow.templateStatus).toBe('error')
    expect(workflow.templateError?.stage).toBe('template')
    expect(workflow.stage).toBe('idle')
    expect(workflow.error).toBeNull()
  })
})

describe('reset ve dismissError', () => {
  it('reset tüm durumu başlangıca döndürür', async () => {
    installFetchMock({ 'POST /api/analyze': () => jsonResponse(makeAnalysis()) })
    setup()
    await analyzeDemo()

    act(() => {
      workflow.approveRow('BOQ-003', 'IPE-200-S235')
    })
    act(() => {
      workflow.reset()
    })

    expect(workflow.stage).toBe('idle')
    expect(workflow.analysis).toBeNull()
    expect(workflow.rows).toEqual([])
    expect(workflow.total).toBe(0)
  })

  it('dismissError analiz varsa reviewing’e döner', async () => {
    installFetchMock({
      'POST /api/analyze': () => jsonResponse(makeAnalysis()),
      'POST /api/calculate': () => errorResponse({ code: 'x', message: 'hata' }, 500),
    })
    setup()
    await analyzeDemo()

    await act(async () => {
      await workflow.runCalculation()
    })
    expect(workflow.stage).toBe('error')

    act(() => {
      workflow.dismissError()
    })
    expect(workflow.stage).toBe('reviewing')
    expect(workflow.error).toBeNull()
  })

  it('dismissError analiz yoksa idle’a döner', async () => {
    installFetchMock({
      'POST /api/analyze': () => errorResponse({ code: 'x', message: 'hata' }, 500),
    })
    setup()
    await analyzeDemo()
    expect(workflow.stage).toBe('error')

    act(() => {
      workflow.dismissError()
    })
    expect(workflow.stage).toBe('idle')
  })
})

describe('toWorkflowError', () => {
  it('ApiError zarfını taşır', () => {
    const error = toWorkflowError(
      'analyze',
      new ApiError(422, MISSING_COLUMN_ERROR.error),
    )
    expect(error).toMatchObject({
      stage: 'analyze',
      title: MISSING_COLUMN_ERROR.error.message,
      detail: MISSING_COLUMN_ERROR.error.detail,
      suggestion: MISSING_COLUMN_ERROR.error.suggestion,
    })
  })

  it('bağlantı hatasına çözüm önerisi ekler', () => {
    const error = toWorkflowError('calculate', new ApiConnectionError())
    expect(error.title).toBe('Bağlantı kurulamadı')
    expect(error.suggestion).toContain('Backend servisinin')
  })

  it('iptal edilen isteği hata olarak sunmaz', () => {
    const error = toWorkflowError('analyze', new ApiAbortError())
    expect(error.title).toBe('İstek iptal edildi')
    expect(error.suggestion).toContain('yeniden başlat')
  })

  it('bilinmeyen değer için genel mesaj verir', () => {
    const error = toWorkflowError('report', 'beklenmeyen')
    expect(error.title).toBe('Beklenmeyen bir hata oluştu')
    expect(error.stage).toBe('report')
  })
})
