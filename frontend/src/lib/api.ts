/**
 * Backend ile konuşan tek nokta.
 *
 * Tasarım kuralları
 * -----------------
 * 1. **Tek hata tipi.** Sunucunun hata zarfı (`{error: {...}}`), ağ hatası ve
 *    beklenmeyen gövde aynı `ApiError` sınıfına dönüşür. Ekranlar tek yerden
 *    kullanıcıya gösterilebilir mesaj alır.
 * 2. **Ham ayrıntı gösterilmez.** Sunucu yolu, stack trace veya sağlayıcı
 *    anahtarı istemciye taşınmaz; zarf zaten güvenli alanlardan oluşur.
 * 3. **Kimlik başlığı yok.** Oturum/çerez kullanılmaz (`credentials` yok).
 * 4. **Hesaplama istemcide yapılmaz.** `calculate` yalnızca ham satır ve
 *    kullanıcı kararlarını gönderir; dönen değerler olduğu gibi gösterilir.
 *
 * Adres çözümü
 * ------------
 * `VITE_API_BASE_URL` boşsa görece `/api/...` kullanılır ve Vite proxy'si
 * devreye girer. Doluysa (ör. `http://127.0.0.1:8000`) doğrudan o adrese
 * gidilir ve backend CORS izin listesi devreye girer.
 */

import type {
  AnalyzeResponse,
  ApiErrorBody,
  ApiIssue,
  CalculateRequest,
  CalculateResponse,
  HealthResponse,
} from '../types/api'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')

/** Şablon ve rapor indirmelerinde beklenen dosya adı yedeği. */
const TEMPLATE_FALLBACK_NAME = 'buildflow-metraj-sablonu.xlsx'

export const REPORT_FALLBACK_NAMES = {
  excel: 'buildflow-satin-alma.xlsx',
  pdf: 'buildflow-satin-alma.pdf',
} as const

export type ReportKind = keyof typeof REPORT_FALLBACK_NAMES

/* --------------------------------------------------------------------------
 * Hata tipi
 * -------------------------------------------------------------------------- */

/**
 * Kullanıcıya gösterilebilir API hatası.
 *
 * `code` sunucunun makine tarafından okunabilir kodudur (ör. `missing-column`,
 * `invalid-decision`, `report-empty`); `message`, `detail`, `suggestion` ve
 * `issues` doğrudan kullanıcıya gösterilebilir metinlerdir.
 */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly detail: string
  readonly suggestion: string
  readonly issues: ApiIssue[]

  constructor(
    status: number,
    body: ApiErrorBody,
  ) {
    super(body.message)
    this.name = 'ApiError'
    this.status = status
    this.code = body.code
    this.detail = body.detail
    this.suggestion = body.suggestion
    this.issues = body.issues
  }
}

/** Ağ/sunucuya ulaşılamama hatası — `status` yoktur. */
export class ApiConnectionError extends Error {
  readonly code = 'connection-error'

  constructor() {
    super(
      'Sunucuya ulaşılamadı. Backend çalışıyor mu ve API adresi doğru mu?',
    )
    this.name = 'ApiConnectionError'
  }
}

/** İstek kullanıcı tarafından iptal edildi (AbortSignal). */
export class ApiAbortError extends Error {
  readonly code = 'aborted'

  constructor() {
    super('İstek iptal edildi.')
    this.name = 'ApiAbortError'
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

export function isAbortError(error: unknown): error is ApiAbortError {
  return error instanceof ApiAbortError
}

/** Herhangi bir hatayı kullanıcıya gösterilecek tek bir metne çevirir. */
export function describeApiError(error: unknown): {
  title: string
  message: string
  detail: string
  suggestion: string
  issues: ApiIssue[]
} {
  if (error instanceof ApiError) {
    return {
      title: error.message,
      message: error.message,
      detail: error.detail,
      suggestion: error.suggestion,
      issues: error.issues,
    }
  }
  if (error instanceof ApiConnectionError) {
    return {
      title: 'Bağlantı kurulamadı',
      message: error.message,
      detail: '',
      suggestion:
        'Backend servisinin çalıştığını ve VITE_API_BASE_URL ayarını kontrol edin.',
      issues: [],
    }
  }
  if (error instanceof ApiAbortError) {
    return {
      title: 'İstek iptal edildi',
      message: error.message,
      detail: '',
      suggestion: 'İşlemi yeniden başlatabilirsiniz.',
      issues: [],
    }
  }
  return {
    title: 'Beklenmeyen bir hata oluştu',
    message: 'İşlem tamamlanamadı.',
    detail: '',
    suggestion: 'Lütfen tekrar deneyin.',
    issues: [],
  }
}

/* --------------------------------------------------------------------------
 * Ortak yardımcılar
 * -------------------------------------------------------------------------- */

function url(path: string): string {
  return `${API_BASE_URL}${path}`
}

/** Boş `issues` üreten güvenli varsayılan. */
const EMPTY_BODY: ApiErrorBody = {
  code: 'unknown-error',
  message: 'Beklenmeyen bir hata oluştu.',
  detail: '',
  suggestion: 'Lütfen tekrar deneyin.',
  issues: [],
}

function toIssue(value: unknown): ApiIssue {
  const item = (value ?? {}) as Record<string, unknown>
  const asText = (key: string): string =>
    typeof item[key] === 'string' ? (item[key] as string) : ''
  const asNumber = (key: string): number | null =>
    typeof item[key] === 'number' ? (item[key] as number) : null

  return {
    source_row: asNumber('source_row'),
    boq_no: typeof item.boq_no === 'string' ? item.boq_no : null,
    column: typeof item.column === 'string' ? item.column : null,
    code: typeof item.code === 'string' ? item.code : null,
    message: asText('message'),
    suggestion: asText('suggestion'),
  }
}

/** Sunucunun hata zarfını güvenli biçimde okur. */
async function readErrorBody(response: Response): Promise<ApiErrorBody> {
  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    return {
      ...EMPTY_BODY,
      code: `http-${response.status}`,
    }
  }

  const envelope = (payload ?? {}) as Record<string, unknown>
  const raw = envelope.error

  if (typeof raw !== 'object' || raw === null) {
    return { ...EMPTY_BODY, code: `http-${response.status}` }
  }

  const body = raw as Record<string, unknown>
  const issues = Array.isArray(body.issues) ? body.issues.map(toIssue) : []

  return {
    code: typeof body.code === 'string' ? body.code : `http-${response.status}`,
    message:
      typeof body.message === 'string' && body.message.trim()
        ? body.message
        : EMPTY_BODY.message,
    detail: typeof body.detail === 'string' ? body.detail : '',
    suggestion:
      typeof body.suggestion === 'string' ? body.suggestion : '',
    issues,
  }
}

async function ensureOk(response: Response): Promise<Response> {
  if (response.ok) return response
  throw new ApiError(response.status, await readErrorBody(response))
}

/** `fetch`'i tek yerden sarar: ağ hatası `ApiConnectionError` olur. */
async function request(
  path: string,
  init: RequestInit,
): Promise<Response> {
  const { signal, ...rest } = init

  try {
    return await fetch(url(path), {
      ...rest,
      signal,
      // Kimlik bilgisi taşınmaz: ürün oturum/çerez kullanmaz.
      credentials: 'omit',
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiAbortError()
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiAbortError()
    }
    throw new ApiConnectionError()
  }
}

/**
 * `Content-Disposition` başlığından dosya adını çıkarır.
 *
 * Sunucu adı üretir (`buildflow-satin-alma-20261113-1042.xlsx`); istemci
 * girdisi içermez. Başlık yoksa çağıranın verdiği yedek ad kullanılır.
 */
export function filenameFromDisposition(
  header: string | null,
  fallback: string,
): string {
  if (!header) return fallback

  // RFC 5987: filename*=UTF-8''...
  const extended = /filename\*=UTF-8''([^;]+)/i.exec(header)
  if (extended?.[1]) {
    try {
      return decodeURIComponent(extended[1])
    } catch {
      /* bozuk kodlama: aşağıdaki düz biçime düş */
    }
  }

  const plain = /filename="?([^";]+)"?/i.exec(header)
  if (plain?.[1]) {
    // Yol ayırıcıları atılır: yanıt bozulsa bile dosya adı yol taşımaz.
    const name = plain[1].split(/[\\/]/).pop()?.trim()
    if (name) return name
  }

  return fallback
}

/* --------------------------------------------------------------------------
 * Endpoint'ler
 * -------------------------------------------------------------------------- */

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await request('/api/health', { method: 'GET', signal })
  const ok = await ensureOk(response)
  return (await ok.json()) as HealthResponse
}

export type DownloadResult = {
  blob: Blob
  filename: string
}

/** Metraj şablonunu indirir (`GET /api/template`). */
export async function downloadTemplate(
  signal?: AbortSignal,
): Promise<DownloadResult> {
  const response = await request('/api/template', { method: 'GET', signal })
  const ok = await ensureOk(response)

  return {
    blob: await ok.blob(),
    filename: filenameFromDisposition(
      ok.headers.get('Content-Disposition'),
      TEMPLATE_FALLBACK_NAME,
    ),
  }
}

/** Excel metraj dosyasını analiz eder (`POST /api/analyze`). */
export async function analyzeFile(
  file: File,
  signal?: AbortSignal,
): Promise<AnalyzeResponse> {
  const form = new FormData()
  // Alan adı sunucu sözleşmesidir: `file`.
  form.append('file', file)

  const response = await request('/api/analyze', {
    method: 'POST',
    body: form,
    signal,
  })
  const ok = await ensureOk(response)
  return (await ok.json()) as AnalyzeResponse
}

/** Ham satırlar + kullanıcı kararları (`POST /api/calculate`). */
export async function calculate(
  payload: CalculateRequest,
  signal?: AbortSignal,
): Promise<CalculateResponse> {
  const response = await request('/api/calculate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
  const ok = await ensureOk(response)
  return (await ok.json()) as CalculateResponse
}

/**
 * Excel/PDF satın alma raporunu indirir (`POST /api/report/{kind}`).
 *
 * Gövde `/api/calculate` ile **aynıdır**: sunucu raporu aynı çekirdekten
 * üretir. Boş sonuç `report-empty` hatası döner.
 */
export async function downloadReport(
  kind: ReportKind,
  payload: CalculateRequest,
  signal?: AbortSignal,
): Promise<DownloadResult> {
  const response = await request(`/api/report/${kind}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
  const ok = await ensureOk(response)

  return {
    blob: await ok.blob(),
    filename: filenameFromDisposition(
      ok.headers.get('Content-Disposition'),
      REPORT_FALLBACK_NAMES[kind],
    ),
  }
}

/* --------------------------------------------------------------------------
 * Tarayıcı yardımcıları
 * -------------------------------------------------------------------------- */

/** Blob'u indirme olarak tetikler. Geçici URL her durumda serbest bırakılır. */
export function triggerDownload({ blob, filename }: DownloadResult): void {
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = filename
  anchor.rel = 'noopener'
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  // Bazı tarayıcılarda indirme başlamadan URL iptal edilirse dosya bozulur.
  setTimeout(() => URL.revokeObjectURL(href), 10_000)
}
