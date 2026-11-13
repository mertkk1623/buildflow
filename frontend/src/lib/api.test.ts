import { describe, expect, it, vi } from 'vitest'

import {
  ApiAbortError,
  ApiConnectionError,
  ApiError,
  REPORT_FALLBACK_NAMES,
  analyzeFile,
  calculate,
  describeApiError,
  downloadReport,
  downloadTemplate,
  fetchHealth,
  filenameFromDisposition,
  isAbortError,
  isApiError,
  triggerDownload,
} from './api'
import { callsTo, errorResponse, fileResponse, installFetchMock, jsonResponse } from '../test/server'
import {
  CORRUPT_FILE_ERROR,
  INVALID_DECISION_ERROR,
  MISSING_COLUMN_ERROR,
  REPORT_EMPTY_ERROR,
  demoRequest,
  makeAnalysis,
  makeCalculation,
} from '../test/fixtures/demo'
import { metrajFile } from '../test/harness'

/**
 * API istemcisi testleri.
 *
 * Kapsanan sözleşmeler:
 * 1. Sunucunun hata zarfı **tek** `ApiError` tipine dönüşür; ham gövde sızmaz.
 * 2. Ağ hatası ve iptal ayrı tiplerdir.
 * 3. İndirmelerde dosya adı `Content-Disposition`'dan okunur (RFC 5987 dahil).
 * 4. İstek hiçbir zaman kimlik bilgisi taşımaz.
 */

const XLSX_MIME =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
const PDF_MIME = 'application/pdf'

describe('filenameFromDisposition', () => {
  it('RFC 5987 biçimini çözer', () => {
    expect(
      filenameFromDisposition(
        "attachment; filename=\"rapor.xlsx\"; filename*=UTF-8''buildflow-satin-alma-20261113-1042.xlsx",
        'yedek.xlsx',
      ),
    ).toBe('buildflow-satin-alma-20261113-1042.xlsx')
  })

  it('Türkçe karakterli adı kod çözerek verir', () => {
    expect(
      filenameFromDisposition(
        `attachment; filename*=UTF-8''${encodeURIComponent('satın-alma-özet.pdf')}`,
        'yedek.pdf',
      ),
    ).toBe('satın-alma-özet.pdf')
  })

  it('düz biçimi okur', () => {
    expect(
      filenameFromDisposition('attachment; filename="buildflow.xlsx"', 'yedek.xlsx'),
    ).toBe('buildflow.xlsx')
  })

  it('tırnaksız düz biçimi okur', () => {
    expect(
      filenameFromDisposition('attachment; filename=buildflow.pdf', 'yedek.pdf'),
    ).toBe('buildflow.pdf')
  })

  it('başlık yoksa yedek adı verir', () => {
    expect(filenameFromDisposition(null, 'yedek.xlsx')).toBe('yedek.xlsx')
  })

  it('yol ayırıcı içeren bozuk adı temizler', () => {
    expect(
      filenameFromDisposition('attachment; filename="C:\\\\Users\\\\x\\\\rapor.xlsx"', 'yedek.xlsx'),
    ).toBe('rapor.xlsx')
  })

  it('bozuk yüzde kodlamasında düz biçime düşer', () => {
    expect(
      filenameFromDisposition(
        "attachment; filename=\"rapor.pdf\"; filename*=UTF-8''%%%bozuk",
        'yedek.pdf',
      ),
    ).toBe('rapor.pdf')
  })
})

describe('hata dönüşümü', () => {
  it('sunucu zarfını ApiError’a çevirir ve güvenli alanları korur', async () => {
    installFetchMock({
      'POST /api/analyze': () =>
        errorResponse(MISSING_COLUMN_ERROR.error, 422),
    })

    const error = await analyzeFile(metrajFile()).catch((caught: unknown) => caught)

    expect(isApiError(error)).toBe(true)
    const apiError = error as ApiError
    expect(apiError.status).toBe(422)
    expect(apiError.code).toBe('missing-column')
    expect(apiError.message).toContain('eksik')
    expect(apiError.detail).toContain('Bulunan kolonlar')
    expect(apiError.suggestion).toContain('Şablondaki başlıkları')
  })

  it('issues dizisini olduğu gibi taşır', async () => {
    installFetchMock({
      'POST /api/calculate': () => errorResponse(INVALID_DECISION_ERROR.error, 409),
    })

    const error = await calculate(demoRequest()).catch((caught: unknown) => caught)
    const apiError = error as ApiError

    expect(apiError.issues).toHaveLength(1)
    expect(apiError.issues[0].boq_no).toBe('BOQ-009')
    expect(apiError.issues[0].message.length).toBeGreaterThan(0)
  })

  it('gövdesi JSON olmayan hatada güvenli varsayılan üretir', async () => {
    installFetchMock({
      'GET /api/template': () => new Response('<html>500</html>', { status: 500 }),
    })

    const error = await downloadTemplate().catch((caught: unknown) => caught)
    const apiError = error as ApiError

    expect(apiError.code).toBe('http-500')
    expect(apiError.message).not.toContain('html')
    expect(apiError.issues).toEqual([])
  })

  it('zarfda `error` yoksa yine ApiError olur, stack trace gösterilmez', async () => {
    installFetchMock({
      'POST /api/analyze': () => jsonResponse({ detail: 'Traceback ... secret' }, 500),
    })

    const error = await analyzeFile(metrajFile()).catch((caught: unknown) => caught)
    const apiError = error as ApiError

    expect(apiError).toBeInstanceOf(ApiError)
    expect(apiError.code).toBe('http-500')
    expect(JSON.stringify(describeApiError(apiError))).not.toContain('Traceback')
  })

  it('ağ hatası ApiConnectionError olur', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )

    const error = await fetchHealth().catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiConnectionError)
    expect((error as ApiConnectionError).code).toBe('connection-error')
  })

  it('iptal ApiAbortError olur ve bağlantı hatasıyla karışmaz', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.reject(new DOMException('The operation was aborted.', 'AbortError')),
      ),
    )

    const error = await fetchHealth().catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiAbortError)
    expect(isAbortError(error)).toBe(true)
    expect(isApiError(error)).toBe(false)
  })

  it('describeApiError sunucu ayrıntısını göstermez', () => {
    const described = describeApiError(
      new ApiError(422, REPORT_EMPTY_ERROR.error),
    )
    expect(described.message).toContain('onaylanmış kalem yok')
    expect(described.suggestion).toContain('en az bir satırı onaylayın')
  })

  it('bilinmeyen hata için genel mesaj verir', () => {
    const described = describeApiError(new Error('ENOENT C:\\secret\\path'))
    expect(described.title).toBe('Beklenmeyen bir hata oluştu')
    expect(JSON.stringify(described)).not.toContain('secret')
  })
})

describe('istek kurulumu', () => {
  it('sağlık kontrolü doğru yolu çağırır', async () => {
    const { calls } = installFetchMock()
    await fetchHealth()
    expect(callsTo(calls, 'GET', '/api/health')).toHaveLength(1)
  })

  it('analiz dosyayı multipart `file` alanıyla gönderir', async () => {
    const { calls } = installFetchMock({
      'POST /api/analyze': () => jsonResponse(makeAnalysis()),
    })

    const file = metrajFile('metraj.xlsx')
    await analyzeFile(file)

    const [call] = callsTo(calls, 'POST', '/api/analyze')
    expect(call.form).toBeInstanceOf(FormData)
    const sent = call.form!.get('file') as File
    expect(sent.name).toBe('metraj.xlsx')
    // Tarayıcı multipart sınırını kendisi koyar; elle Content-Type yazılmaz.
    expect(call.headers['Content-Type']).toBeUndefined()
  })

  it('hesaplama JSON gönderir ve yanıtı olduğu gibi döndürür', async () => {
    const calculation = makeCalculation()
    const { calls } = installFetchMock({
      'POST /api/calculate': () => jsonResponse(calculation),
    })

    const result = await calculate(demoRequest())

    expect(result).toEqual(calculation)
    expect(result.summary.total_order_length_m).toBe('966')
    expect(result.summary.known_weight_kg).toBe('18005.820')

    const [call] = callsTo(calls, 'POST', '/api/calculate')
    expect(call.headers['Content-Type']).toBe('application/json')
  })

  it('istek kimlik bilgisi taşımaz', async () => {
    const { calls } = installFetchMock({
      'POST /api/calculate': () => jsonResponse(makeCalculation()),
    })

    await calculate(demoRequest())
    expect(callsTo(calls, 'POST', '/api/calculate')[0].credentials).toBe('omit')
  })

  it('gönderilen gövde istemci tarafından zenginleştirilmez', async () => {
    const { calls } = installFetchMock({
      'POST /api/calculate': () => jsonResponse(makeCalculation()),
    })

    const payload = demoRequest()
    await calculate(payload)

    const sent = callsTo(calls, 'POST', '/api/calculate')[0].json
    expect(sent).toEqual(payload)
    expect(JSON.stringify(sent)).not.toContain('matched_code')
  })
})

describe('indirmeler', () => {
  it('şablonu doğru MIME ve dosya adıyla indirir', async () => {
    installFetchMock({
      'GET /api/template': () =>
        fileResponse('xlsx-bytes', {
          filename: 'buildflow-metraj-sablonu.xlsx',
          contentType: XLSX_MIME,
          disposition: 'plain',
        }),
    })

    const result = await downloadTemplate()
    expect(result.filename).toBe('buildflow-metraj-sablonu.xlsx')
    expect(result.blob.type).toBe(XLSX_MIME)
    expect(await result.blob.text()).toBe('xlsx-bytes')
  })

  it('Excel raporunu sunucunun verdiği adla indirir', async () => {
    const { calls } = installFetchMock({
      'POST /api/report/excel': () =>
        fileResponse('xlsx', {
          filename: 'buildflow-satin-alma-20261113-1042.xlsx',
          contentType: XLSX_MIME,
          disposition: 'extended',
        }),
    })

    const result = await downloadReport('excel', demoRequest())

    expect(result.filename).toBe('buildflow-satin-alma-20261113-1042.xlsx')
    expect(result.blob.type).toBe(XLSX_MIME)
    // Rapor gövdesi hesaplama gövdesiyle aynıdır.
    expect(callsTo(calls, 'POST', '/api/report/excel')[0].json).toEqual(demoRequest())
  })

  it('PDF raporunu doğru MIME ile indirir', async () => {
    installFetchMock({
      'POST /api/report/pdf': () =>
        fileResponse('%PDF-1.4', {
          filename: 'buildflow-satin-alma-20261113-1042.pdf',
          contentType: PDF_MIME,
          disposition: 'extended',
        }),
    })

    const result = await downloadReport('pdf', demoRequest())
    expect(result.blob.type).toBe(PDF_MIME)
    expect(result.filename.endsWith('.pdf')).toBe(true)
  })

  it('başlık yoksa tür bazlı yedek adı kullanır', async () => {
    installFetchMock({
      'POST /api/report/excel': () =>
        fileResponse('x', {
          filename: 'yok.xlsx',
          contentType: XLSX_MIME,
          disposition: 'none',
        }),
    })

    const result = await downloadReport('excel', demoRequest())
    expect(result.filename).toBe(REPORT_FALLBACK_NAMES.excel)
  })

  it('boş sonuçta `report-empty` hatası fırlatır ve dosya üretmez', async () => {
    installFetchMock({
      'POST /api/report/pdf': () => errorResponse(REPORT_EMPTY_ERROR.error, 422),
    })

    const error = await downloadReport('pdf', demoRequest()).catch(
      (caught: unknown) => caught,
    )
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).code).toBe('report-empty')
  })

  it('geçersiz kararda `invalid-decision` hatası fırlatır', async () => {
    installFetchMock({
      'POST /api/report/excel': () =>
        errorResponse(CORRUPT_FILE_ERROR.error, 500),
    })

    const error = await downloadReport('excel', demoRequest()).catch(
      (caught: unknown) => caught,
    )
    expect((error as ApiError).code).toBe('corrupt-file')
  })
})

describe('triggerDownload', () => {
  it('bağlantıyı oluşturur, tıklar ve temizler', () => {
    const createObjectURL = vi.fn(() => 'blob:buildflow-test')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL })

    const click = vi.fn()
    const realCreate = document.createElement.bind(document)
    const createElement = vi
      .spyOn(document, 'createElement')
      .mockImplementation((tag: string) => {
        const element = realCreate(tag)
        if (tag === 'a') element.click = click
        return element
      })

    triggerDownload({ blob: new Blob(['x']), filename: 'rapor.xlsx' })

    expect(createObjectURL).toHaveBeenCalledTimes(1)
    expect(click).toHaveBeenCalledTimes(1)
    expect(document.querySelector('a')).toBeNull()

    createElement.mockRestore()
  })
})
