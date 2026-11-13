import type { ReviewStatus } from '../types/workflow'

/**
 * Sınıf birleştirme ve durum eşlemeleri.
 *
 * `clsx` bağımlılığı yerine bilinçli olarak bu küçük yardımcı kullanılır.
 * Durum eşlemeleri de burada tutulur: Analysis, Review ve Results aynı
 * etiketleri ve renkleri kullanır, aksi halde ekranlar arası tutarsızlık doğar.
 */

type ClassValue = string | false | null | undefined

export function cn(...values: ClassValue[]): string {
  return values.filter(Boolean).join(' ')
}

/** Status.tsx içindeki `Tone` ile aynı küme — yapısal olarak uyumludur. */
export type StatusTone =
  | 'neutral'
  | 'copper'
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'

type StatusMeta = {
  /** Uzun etiket: tablo dışı yerlerde. */
  label: string
  /** Kısa etiket: filtre ve rozetlerde. */
  short: string
  tone: StatusTone
  /** Satır solundaki şerit rengi. */
  bar: string
  /** Kullanıcıya "bu satıra ne oldu" açıklaması. */
  hint: string
}

export const STATUS_META: Record<ReviewStatus, StatusMeta> = {
  rule: {
    label: 'Kural ile eşleşti',
    short: 'Kural',
    tone: 'success',
    bar: 'bg-success-fg',
    hint: 'Dört özellik eksiksiz ve katalogda tek kalem eşleşti; kullanıcı onayı gerekmedi.',
  },
  'ai-approved': {
    label: 'Kullanıcı onayladı',
    short: 'Onaylı',
    tone: 'copper',
    bar: 'bg-copper-500',
    hint: 'Kullanıcı bir katalog kodu seçip onayladı. Yalnızca onaydan sonra listeye girer.',
  },
  pending: {
    label: 'Onay bekliyor',
    short: 'Onay bekliyor',
    tone: 'warning',
    bar: 'bg-warning-fg',
    hint: 'Açıklama tek bir kaleme yetmiyor; kullanıcı seçmeden listeye girmez.',
  },
  rejected: {
    label: 'Reddedildi',
    short: 'Reddedildi',
    tone: 'danger',
    bar: 'bg-danger-fg',
    hint: 'Kullanıcı satırı reddetti; satır hesaba katılmaz.',
  },
  excluded: {
    label: 'Hariç tutuldu',
    short: 'Hariç',
    tone: 'neutral',
    bar: 'bg-steel-300',
    hint: 'Satır hesaba uygun değil; nedeni satır detayında belirtilir.',
  },
  invalid: {
    label: 'Geçersiz satır',
    short: 'Geçersiz',
    tone: 'danger',
    bar: 'bg-danger-fg',
    hint: 'Satır veri olarak okunamadı; düzeltilmeden hesaba giremez.',
  },
}

/** Hesaba girmeyen satırlar: karar bekleyen + reddedilen + hariç + geçersiz. */
export const HELD_STATUSES: ReviewStatus[] = [
  'pending',
  'rejected',
  'excluded',
  'invalid',
]

/** Hesaplamada atlanan satırın nedeni — `SkippedRowOut.status` ile eşleşir. */
export const SKIP_LABEL: Record<string, string> = {
  pending: 'Onay bekliyor',
  rejected: 'Kullanıcı reddetti',
  excluded: 'Hesap kapsamı dışı',
  invalid: 'Veri geçersiz',
  'unknown-code': 'Kod katalogda yok',
}
