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

/* --------------------------------------------------------------------------
 * Hızlı başlangıç — kapsamlı proje örneği
 * -------------------------------------------------------------------------- */

/** `.xlsx` medya tipi — yükleme akışıyla aynı. */
const XLSX_MEDIA_TYPE =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

/**
 * 40 satırlık kapsamlı proje metrajı.
 *
 * `EXAMPLE_FILES` listesine **bilinçli olarak** eklenmez: o liste, depoda
 * karşılığı olan rapor çıktılarını gösterir. Bu dosya ise "hızlı başlangıç"
 * panelinin veri kümesidir; tek tıkla analiz edilir.
 *
 * İçerik `templates/proje_ornek_metraj.xlsx` ile birebir aynıdır.
 */
export const SAMPLE_PROJECT_FILE: ExampleFile = {
  name: 'proje-ornek-metraj.xlsx',
  label: 'Örnek proje metrajı',
  format: 'xlsx',
  description:
    '40 satırlık kapsamlı metraj: 14 katalog kalemi, 5 onay bekleyen satır, üç kapsam dışı nedeni ve yüksek fireli pozlar.',
  href: `${EXAMPLES_BASE}/proje-ornek-metraj.xlsx`,
  action: 'download',
  kind: 'metraj',
}

/**
 * Örnek metrajı `File` olarak getirir — dosya indirmeden analiz için.
 *
 * Tek kullanım: "Örnek veri ile hemen dene". Dosya **yine de** sunucuya
 * gönderilir; istemci sahte bir analiz sonucu üretmez. Böylece demo, gerçek
 * yükleme akışıyla birebir aynı yoldan geçer ve örnek veri tek kaynaktan gelir.
 */
export async function fetchSampleProjectFile(): Promise<File> {
  const response = await fetch(SAMPLE_PROJECT_FILE.href)
  if (!response.ok) {
    throw new Error(`Örnek dosya alınamadı (HTTP ${response.status}).`)
  }
  const blob = await response.blob()
  return new File([blob], SAMPLE_PROJECT_FILE.name, {
    type: XLSX_MEDIA_TYPE,
  })
}
