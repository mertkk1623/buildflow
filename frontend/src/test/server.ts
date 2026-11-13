/**
 * Test için ağ taklidi.
 *
 * Amaç, `fetch`'i tek yerden ele almak: her test yalnızca **hangi endpoint'in
 * ne döndüreceğini** söyler, gövde/başlık kurmakla uğraşmaz. Beklenmeyen bir
 * istek 500 + `test-unexpected-request` zarfıyla döner; böylece sessizce
 * yutulan bir çağrı testi yanlışlıkla geçirmez.
 */

import { vi } from 'vitest'

import type { ApiIssue } from '../types/api'

export type RecordedCall = {
  path: string
  method: string
  /** JSON gövde; JSON değilse ham metin. */
  json: unknown
  /** `FormData` gövde (dosya yükleme). */
  form: FormData | null
  headers: Record<string, string>
  credentials: RequestCredentials | undefined
}

export type Handler = (call: RecordedCall) => Response | Promise<Response>

const JSON_HEADERS = { 'Content-Type': 'application/json' }

export function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: JSON_HEADERS,
  })
}

/** Sunucunun hata zarfı — `backend/app/api/errors.py` ile aynı biçim. */
export function errorResponse(
  body: { code: string; message: string; detail?: string; suggestion?: string; issues?: ApiIssue[] },
  status: number,
): Response {
  return jsonResponse(
    {
      error: {
        code: body.code,
        message: body.message,
        detail: body.detail ?? '',
        suggestion: body.suggestion ?? '',
        issues: body.issues ?? [],
      },
    },
    status,
  )
}

/** İkili dosya yanıtı: rapor/şablon indirmeleri. */
export function fileResponse(
  content: string,
  options: {
    filename: string
    contentType: string
    disposition?: 'plain' | 'extended' | 'none'
  },
): Response {
  const headers: Record<string, string> = { 'Content-Type': options.contentType }
  if (options.disposition === 'plain') {
    headers['Content-Disposition'] = `attachment; filename="${options.filename}"`
  } else if (options.disposition !== 'none') {
    headers['Content-Disposition'] =
      `attachment; filename="rapor.xlsx"; filename*=UTF-8''${encodeURIComponent(options.filename)}`
  }

  return new Response(content, { status: 200, headers })
}

function readHeaders(init?: RequestInit): Record<string, string> {
  const raw = init?.headers
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {}
  if (typeof Headers !== 'undefined' && raw instanceof Headers) {
    const result: Record<string, string> = {}
    raw.forEach((value, key) => {
      result[key] = value
    })
    return result
  }
  return { ...(raw as Record<string, string>) }
}

function readBody(init?: RequestInit): { json: unknown; form: FormData | null } {
  const body = init?.body
  if (body instanceof FormData) return { json: null, form: body }
  if (typeof body === 'string') {
    try {
      return { json: JSON.parse(body) as unknown, form: null }
    } catch {
      return { json: body, form: null }
    }
  }
  return { json: null, form: null }
}

/**
 * `fetch`'i taklit eder ve tüm çağrıları kaydeder.
 *
 * `/api/health` varsayılan olarak hazırdır: her sayfa `AppShell` içinde sağlık
 * kontrolü yapar.
 */
export function installFetchMock(
  handlers: Record<string, Handler> = {},
): { calls: RecordedCall[]; fetchMock: ReturnType<typeof vi.fn> } {
  const calls: RecordedCall[] = []
  const routes: Record<string, Handler> = {
    'GET /api/health': () =>
      jsonResponse({ status: 'ok', environment: 'test' }),
    ...handlers,
  }

  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const rawUrl =
        typeof input === 'string'
          ? input
          : input instanceof URL
            ? input.href
            : input.url
      const path = new URL(rawUrl, 'http://buildflow.test').pathname
      const method = (
        init?.method ?? (typeof input === 'object' && 'method' in input ? input.method : 'GET')
      ).toUpperCase()
      const { json, form } = readBody(init)

      const call: RecordedCall = {
        path,
        method,
        json,
        form,
        headers: readHeaders(init),
        credentials: init?.credentials,
      }
      calls.push(call)

      const handler = routes[`${method} ${path}`]
      if (!handler) {
        return errorResponse(
          {
            code: 'test-unexpected-request',
            message: `Test bu isteği beklemiyordu: ${method} ${path}`,
          },
          500,
        )
      }

      return handler(call)
    },
  )

  vi.stubGlobal('fetch', fetchMock)
  return { calls, fetchMock }
}

/** Belirli bir endpoint'e yapılan çağrılar. */
export function callsTo(calls: RecordedCall[], method: string, path: string) {
  return calls.filter(
    (call) => call.method === method.toUpperCase() && call.path === path,
  )
}
