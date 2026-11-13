import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { callsTo, fileResponse, installFetchMock } from '../test/server'
import { renderApp } from '../test/harness'

/**
 * Ana sayfa (ürün tanıtımı) testleri.
 *
 * Sözleşmeler
 * -----------
 * 1. Şablon **sunucudan** iner (`GET /api/template`); istemci dosya üretmez.
 * 2. Örnek dosya bağlantıları statik yollara gider ve var olan dosyaları
 *    hedefler; uydurma örnek üretilmez.
 * 3. V1 özellikleri "çalışıyor", yol haritası "planlandı" olarak ayrılır —
 *    ikisi karışmaz.
 * 4. AI, sabit bir açık/kapalı iddiası yerine yapılandırmaya bağlı olarak
 *    anlatılır; kapsamı (yalnızca pending, otomatik onay yok) doğru verilir.
 */

const XLSX_MIME =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

function templateHandler() {
  return fileResponse('xlsx-bytes', {
    filename: 'buildflow-metraj-sablonu.xlsx',
    contentType: XLSX_MIME,
    disposition: 'plain',
  })
}

describe('LandingPage', () => {
  it('şablonu sunucudan indirir', async () => {
    const { calls } = installFetchMock({
      'GET /api/template': templateHandler,
    })
    renderApp('/')

    await userEvent.click(
      screen.getByRole('button', { name: 'Örnek Excel Şablonunu İndir' }),
    )

    expect(callsTo(calls, 'GET', '/api/template')).toHaveLength(1)
  })

  it('örnek dosyaları var olan statik yollara bağlar', () => {
    installFetchMock()
    renderApp('/')

    const expected = [
      '/examples/ornek-metraj.xlsx',
      '/examples/ornek-satin-alma-raporu.xlsx',
      '/examples/ornek-satin-alma-raporu.pdf',
    ]

    for (const href of expected) {
      const link = document.querySelector<HTMLAnchorElement>(
        `a[href="${href}"]`,
      )
      expect(link, `${href} bağlantısı yok`).not.toBeNull()
    }
  })

  it('şablonu ve örnek dosyaları ayrı mekanizma olarak sunar', () => {
    installFetchMock()
    renderApp('/')

    // Şablon sunucuda üretilir: bir **buton** ile indirilir, statik dosya
    // değildir ve örnek listesinde yer almaz.
    expect(screen.getByText('Boş metraj şablonu')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Örnek Excel Şablonunu İndir/ }),
    ).toBeInTheDocument()
    expect(
      document.querySelector('a[href="/api/template"]'),
    ).toBeNull()

    // Örnek dosyalar statik: üç bağlantı, yalnızca biri yüklenebilir metraj.
    const exampleSection = document.querySelector('#ornekler') as HTMLElement
    expect(exampleSection).not.toBeNull()

    const exampleCards = Array.from(
      exampleSection.querySelectorAll('ul > li'),
    )
    expect(exampleCards).toHaveLength(3)
    expect(
      within(exampleSection).getAllByText('Yüklenebilir metraj'),
    ).toHaveLength(1)
    expect(
      within(exampleSection).getAllByText('Rapor çıktısı'),
    ).toHaveLength(2)

    // Yüklenebilir metraj gerçek statik dosyaya işaret eder.
    const metrajCard = exampleCards.find((card) =>
      card.textContent?.includes('Yüklenebilir metraj'),
    )
    expect(
      metrajCard?.querySelector('a[href="/examples/ornek-metraj.xlsx"]'),
    ).not.toBeNull()
  })

  it('beş adımlı akışı sırasıyla anlatır', () => {
    installFetchMock()
    renderApp('/')

    const flow = document.querySelector('#akis')
    expect(flow).not.toBeNull()

    const items = within(flow as HTMLElement).getAllByRole('listitem')
    expect(items.map((item) => item.querySelector('h3')?.textContent)).toEqual([
      'Metrajı yükle',
      'Analiz ve eşleştirme',
      'Belirsizleri onayla',
      'Hesapla',
      'Dışa aktar',
    ])
  })

  it('V1 özelliklerini çalışıyor olarak işaretler', () => {
    installFetchMock()
    renderApp('/')

    const section = document.querySelector('#ozellikler') as HTMLElement
    expect(section).not.toBeNull()

    expect(within(section).getByText('Canlı')).toBeInTheDocument()
    expect(
      within(section).getByText('Excel ve PDF satın alma raporu'),
    ).toBeInTheDocument()
    expect(
      within(section).getByText('Kaynak satıra kadar izlenebilirlik'),
    ).toBeInTheDocument()
  })

  it('AI’yı yapılandırmaya bağlı olarak anlatır', () => {
    installFetchMock()
    renderApp('/')

    const section = document.querySelector('#ozellikler') as HTMLElement
    expect(
      within(section).getByText('Yapılandırmaya bağlı'),
    ).toBeInTheDocument()
    // Eski, sabit "üretimde kapalı" iddiası artık geçerli değil.
    expect(screen.queryByText('Üretimde kapalı')).not.toBeInTheDocument()

    // Kapsam doğru anlatılır: yalnızca pending satırlar, otomatik onay yok.
    expect(
      within(section).getByText(
        /yalnızca onay bekleyen satırlar için malzeme eşleştirme önerileri üretir/,
      ),
    ).toBeInTheDocument()
    expect(
      within(section).getByText(/Öneriler otomatik onaylanmaz/),
    ).toBeInTheDocument()

    // Kapalı bir yetenek "çalışıyor" gibi sunulmaz.
    expect(screen.queryByText(/AI destekli eşleştirme/)).not.toBeInTheDocument()
  })

  it('yol haritasını planlandı olarak işaretler', () => {
    installFetchMock()
    renderApp('/')

    const section = document.querySelector('#yol-haritasi') as HTMLElement
    expect(section).not.toBeNull()

    // Başlık rozeti + V2 + V3 kartı.
    expect(within(section).getAllByText('Planlandı')).toHaveLength(3)
    expect(
      within(section).getByText(/henüz geliştirilmedi/),
    ).toBeInTheDocument()

    // V2/V3 kalemleri mevcut özellik gibi gösterilmez: her kalem planlı
    // bölümün içinde durur.
    for (const planned of [
      'Tedarikçi portalı',
      'ERP/SAP entegrasyonları',
      'Genişletilmiş malzeme ve profil kütüphanesi',
    ]) {
      expect(within(section).getByText(planned)).toBeInTheDocument()
    }

    const working = document.querySelector('#ozellikler') as HTMLElement
    expect(within(working).queryByText('Tedarikçi portalı')).toBeNull()
  })

  it('canlı demoya giden birincil eylemi gösterir', () => {
    installFetchMock()
    renderApp('/')

    const cta = screen.getByRole('link', { name: /Canlı demoyu başlat/ })
    expect(cta).toHaveAttribute('href', '/upload')
  })
})
