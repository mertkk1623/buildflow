/**
 * Ana sayfada sunulan statik örnek dosyalar.
 *
 * Kaynak dosyalar depoda zaten var; burada **kopya** tutulmaz, yalnızca
 * `public/examples/` altındaki birebir kopyalarına bağlantı verilir
 * (`docs/examples/` ve `templates/` ile aynı baytlar).
 *
 * Boş metraj şablonu burada yer almaz: o dosya sunucuda üretilir ve
 * `GET /api/template` üzerinden indirilir.
 */

export type ExampleFile = {
  /** Dosya adı — kullanıcıya gösterilen tek kimlik. */
  name: string
  /** Kısa etiket ("Örnek metraj" gibi). */
  label: string
  /** Uzantı rozetinde gösterilir. */
  format: 'xlsx' | 'pdf'
  description: string
  href: string
  /** `download`: dosyayı kaydet; `view`: tarayıcıda aç. */
  action: 'download' | 'view'
  /** `metraj`: yüklenebilir girdi. `rapor`: yalnızca çıktı örneği. */
  kind: 'metraj' | 'rapor'
}

const EXAMPLES_BASE = `${import.meta.env.BASE_URL}examples`

/**
 * Üç dosya da gerçek uygulamadan üretilmiştir; elle yazılmış örnek yoktur.
 *
 * **Şablon ile demo ayrıdır** (karıştırılmamalı):
 *
 * * Boş şablon — ``GET /api/template``. Başlangıç noktası; satırları
 *   kasıtlı olarak ya tam nitelikli ya geçersizdir, bu yüzden AI'ya iş
 *   bırakmaz.
 * * Örnek metraj — ``ornek-metraj.xlsx``. Gerçek bir dosyadır ve **4
 *   pending satır** içerir: AI önerisi, onay akışı ve kapsam dışı
 *   davranışı bu dosyada görülür.
 */
export const EXAMPLE_FILES: ExampleFile[] = [
  {
    name: 'ornek-metraj.xlsx',
    label: 'Örnek metraj',
    format: 'xlsx',
    description:
      '18 satırlık demo metraj: 4 onay bekleyen satır (IPE 200, ipe240 s355, hea 200, lama 40×5), eksik açıklama, farklı birim ve kapsam dışı satırlar. AI önerisini denemek için bunu yükleyin.',
    href: `${EXAMPLES_BASE}/ornek-metraj.xlsx`,
    action: 'download',
    kind: 'metraj',
  },
  {
    name: 'ornek-satin-alma-raporu.xlsx',
    label: 'Örnek Excel raporu',
    format: 'xlsx',
    description:
      'Bu metrajdan üretilmiş gerçek rapor: özet, satın alma listesi, kaynak satırlar ve hesaba alınmayanlar.',
    href: `${EXAMPLES_BASE}/ornek-satin-alma-raporu.xlsx`,
    action: 'download',
    kind: 'rapor',
  },
  {
    name: 'ornek-satin-alma-raporu.pdf',
    label: 'Örnek PDF raporu',
    format: 'pdf',
    description:
      'Aynı hesaplamadan üretilmiş iki sayfalık PDF özet. Tarayıcıda görüntüleyin.',
    href: `${EXAMPLES_BASE}/ornek-satin-alma-raporu.pdf`,
    action: 'view',
    kind: 'rapor',
  },
]

/** Yüklenebilir örnek metraj (AI testi için). */
export const DEMO_METRAJ_FILE = EXAMPLE_FILES.find(
  (file) => file.kind === 'metraj',
)
