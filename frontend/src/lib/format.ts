/**
 * Türkçe biçimlendirme yardımcıları.
 *
 * Kural: sunucudan gelen ondalık değerler **string**'dir. Gösterim için
 * `Number(...)`'a çevrilebilir; ancak bu değer asla hesaplamaya geri
 * gönderilmez (istek gövdesi ham string'i taşır). Böylece `0.1` ikili kesir
 * hatası oluşmaz.
 */

const numberFormatter = new Intl.NumberFormat('tr-TR', {
  maximumFractionDigits: 2,
})

const preciseFormatter = new Intl.NumberFormat('tr-TR', {
  maximumFractionDigits: 4,
})

const percentFormatter = new Intl.NumberFormat('tr-TR', {
  maximumFractionDigits: 2,
})

export function formatNumber(value: number): string {
  return numberFormatter.format(value)
}

/** Uzun ondalıklı fiziksel büyüklükler (m, kg, kg/m). */
export function formatPreciseNumber(value: number): string {
  return preciseFormatter.format(value)
}

/**
 * Sunucudan gelen ondalık metni okunabilir sayıya çevirir.
 *
 * Metin geçersizse `null` döner — `NaN`/`0` uydurulmaz.
 */
export function parseDecimal(value: string | null): number | null {
  if (value === null) return null
  const trimmed = value.trim()
  if (!trimmed) return null
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) ? parsed : null
}

/** Sunucudan gelen ondalık metni Türkçe biçimde gösterir; yoksa "—". */
export function formatDecimal(
  value: string | null,
  options: { precise?: boolean; suffix?: string } = {},
): string {
  const parsed = parseDecimal(value)
  if (parsed === null) return EMPTY_VALUE
  const text = options.precise
    ? preciseFormatter.format(parsed)
    : numberFormatter.format(parsed)
  return options.suffix ? `${text} ${options.suffix}` : text
}

/** Sayı + kaynak birimini birlikte gösterir: "96 m", "0,84 t". */
export function formatQuantity(value: string | null, unit: string | null): string {
  const parsed = parseDecimal(value)
  if (parsed === null) return EMPTY_VALUE
  const suffix = unit && unit.trim() ? ` ${unit.trim()}` : ''
  return `${numberFormatter.format(parsed)}${suffix}`
}

/** Ham sayı + birim (istemci tarafında üretilmiş gösterim değerleri için). */
export function formatNumberWithUnit(value: number, unit: string): string {
  return `${numberFormatter.format(value)} ${unit}`
}

/**
 * Fire yüzdesi: sunucu **yüzde** gönderir (`"5"` → `%5`).
 *
 * Tanımsızsa "—" döner; eksik fire sıfır olarak gösterilmez.
 */
export function formatWaste(percent: string | null): string {
  const parsed = parseDecimal(percent)
  if (parsed === null) return EMPTY_VALUE
  return `%${percentFormatter.format(parsed)}`
}

/** AI güveni: 0–1 arası oran → yüzde. Yoksa "—". */
export function formatConfidence(confidence: string | null): string {
  const parsed = parseDecimal(confidence)
  if (parsed === null) return EMPTY_VALUE
  return `%${percentFormatter.format(parsed * 100)}`
}

/** Dosya boyutu: bayt → "84 KB". */
export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return EMPTY_VALUE
  if (bytes < 1024) return `${bytes} B`
  const kb = bytes / 1024
  if (kb < 1024) return `${numberFormatter.format(kb)} KB`
  return `${numberFormatter.format(kb / 1024)} MB`
}

/** Hesaplanmayan sütunlar için tek tip boş değer. */
export const EMPTY_VALUE = '—'
