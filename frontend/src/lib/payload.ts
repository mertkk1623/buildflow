/**
 * `/api/calculate` istek gövdesinin kurulması — saf fonksiyonlar.
 *
 * Güvenlik sınırı
 * ---------------
 * İstemci **yalnızca** ham metraj verisini ve kullanıcının onay/red kararını
 * gönderir. Eşleşme durumu, katalog kodu, miktar dönüşümü, fire uygulaması
 * veya ağırlık gibi hiçbir hesaplanmış alan gövdede yer almaz. Sunucu
 * `ClientRow`/`ClientDecision` şemalarında `extra="forbid"` uygular.
 *
 * Gönderilemeyen satırlar
 * -----------------------
 * `invalid` satırlar (boş BOQ No, okunamayan miktar, yinelenen BOQ No vb.)
 * `ClientRow` şemasına **uyamaz** (`boq_no` boş olamaz, `quantity > 0`).
 * Bunlar isteğe konmaz; sonuç ekranında "hesaba girmedi" olarak
 * listelenmek üzere ayrıca döndürülür — hiçbir satır sessizce kaybolmaz.
 */

import type {
  AnalyzeRow,
  CalculateRequest,
  ClientDecision,
  ClientRow,
  SkippedStatus,
} from '../types/api'
import { parseDecimal } from './format'
import type { RowDecision } from '../types/workflow'

/** Sunucuya gönderilemeyen satır ve nedeni. */
export type UnsendableRow = {
  source_row: number | null
  boq_no: string
  status: SkippedStatus
  message: string
}

export type BuiltRequest = {
  request: CalculateRequest
  /** İsteğe giremeyen satırlar — sonuç ekranında gösterilir. */
  unsendable: UnsendableRow[]
}

/** `ClientRow` şemasının kabul ettiği satır mı? */
export function isSendableRow(row: AnalyzeRow): boolean {
  if (row.status === 'invalid') return false
  if (!row.boq_no || !row.boq_no.trim()) return false
  if (!row.description || !row.description.trim()) return false
  if (!row.unit || !row.unit.trim()) return false
  if (row.source_row < 2) return false

  const quantity = parseDecimal(row.quantity)
  return quantity !== null && quantity > 0
}

/** Sunucuya gönderilen karar nedeni — kullanıcıya gösterilebilir metin. */
const APPROVE_REASON = 'Kullanıcı katalog eşleşmesini onayladı.'
const REJECT_REASON = 'Kullanıcı satırı reddetti.'

function unsendableReason(row: AnalyzeRow): string {
  if (row.status === 'invalid') {
    const issue = row.issues[0]
    return issue
      ? `Satır geçersiz: ${issue.message}`
      : (row.match.message || 'Satır veri olarak okunamadı.')
  }
  if (!row.boq_no || !row.boq_no.trim()) return 'BOQ No boş.'
  if (!row.description || !row.description.trim()) return 'Açıklama boş.'
  if (!row.unit || !row.unit.trim()) return 'Birim boş.'
  if (row.source_row < 2) return 'Excel satır numarası geçersiz.'
  const quantity = parseDecimal(row.quantity)
  if (quantity === null) return 'Miktar okunamadı.'
  if (quantity <= 0) return 'Miktar sıfırdan büyük olmalı.'
  return 'Satır isteğe alınamadı.'
}

/**
 * Analiz satırları + kullanıcı kararları → hesaplama isteği.
 *
 * Aynı BOQ No iki kez gönderilmez (sunucu bunu 422 ile reddeder). İlk
 * görülen satır gönderilir; sonrakiler "gönderilemedi" olarak işaretlenir.
 */
export function buildCalculateRequest(
  rows: AnalyzeRow[],
  decisions: Record<string, RowDecision>,
): BuiltRequest {
  const requestRows: ClientRow[] = []
  const unsendable: UnsendableRow[] = []
  const seen = new Set<string>()

  for (const row of rows) {
    if (!isSendableRow(row)) {
      unsendable.push({
        source_row: row.source_row,
        boq_no: row.boq_no ?? `(satır ${row.source_row})`,
        status: row.status === 'invalid' ? 'invalid' : 'excluded',
        message: unsendableReason(row),
      })
      continue
    }

    // `isSendableRow` sonrası bu alanlar kesindir.
    const boqNo = row.boq_no as string
    if (seen.has(boqNo)) {
      unsendable.push({
        source_row: row.source_row,
        boq_no: boqNo,
        status: 'invalid',
        message: 'Aynı BOQ No birden fazla satırda kullanılmış.',
      })
      continue
    }
    seen.add(boqNo)

    requestRows.push({
      source_row: row.source_row,
      boq_no: boqNo,
      description: row.description as string,
      // Ham metin aynen taşınır: yuvarlama veya float dönüşümü yok.
      quantity: row.quantity as string,
      unit: row.unit as string,
      waste_percent: row.waste_percent,
    })
  }

  const requestDecisions: ClientDecision[] = []
  for (const [boqNo, decision] of Object.entries(decisions)) {
    if (!seen.has(boqNo)) continue

    requestDecisions.push(
      decision.action === 'approve'
        ? {
            boq_no: boqNo,
            action: 'approve',
            code: decision.code,
            reason: decision.reason || APPROVE_REASON,
          }
        : {
            boq_no: boqNo,
            action: 'reject',
            code: null,
            reason: decision.reason || REJECT_REASON,
          },
    )
  }

  return {
    request: { rows: requestRows, decisions: requestDecisions },
    unsendable,
  }
}

/** Kullanıcı onayı; sunucu kodu katalogla yeniden doğrular. */
export function approveDecision(code: string): RowDecision {
  return { action: 'approve', code, reason: APPROVE_REASON }
}

export function rejectDecision(): RowDecision {
  return { action: 'reject', reason: REJECT_REASON }
}
