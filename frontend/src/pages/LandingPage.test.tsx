import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { callsTo, fileResponse, installFetchMock, jsonResponse } from '../test/server'
import { renderApp } from '../test/harness'
import { SAMPLE_ANALYSIS } from '../test/fixtures/sample'

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
 * 5. "Hemen dene" **indirme yapmaz**: örnek dosyayı alıp gerçek analiz
 *    yoluna verir. Ayrı bir demo hesaplaması yoktur.
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

/** Statik örnek dosya — `fetch` ile alınır (indirme değil). */
function sampleFileHandler() {
  return fileResponse('sample-xlsx-bytes', {
    filename: 'proje-ornek-metraj.xlsx',
    contentType: XLSX_MIME,
    disposition: 'none',
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

  describe('hızlı başlangıç paneli', () => {
    it('üç eylemi ve bilgi notunu bir arada sunar', () => {
      installFetchMock()
      renderApp('/')

      const panel = document.querySelector('#hizli-baslangic') as HTMLElement
      expect(panel).not.toBeNull()

      expect(
        within(panel).getByRole('button', {
          name: /Örnek Veri ile Hemen Dene \(AI Demo\)/,
        }),
      ).toBeInTheDocument()
      expect(
        within(panel).getByRole('button', { name: /Boş Veri Şablonunu İndir/ }),
      ).toBeInTheDocument()

      const download = panel.querySelector<HTMLAnchorElement>(
        'a[href="/examples/proje-ornek-metraj.xlsx"]',
      )
      expect(download).not.toBeNull()
      expect(download).toHaveAttribute('download', 'proje-ornek-metraj.xlsx')

      // Bilgi notu: hangi AI özelliklerinin test edildiği açıkça yazılmalı.
      // Metin vurgu span'larına bölündüğü için tek bir cümle olarak okunur.
      const note = within(panel).getByText((_, element) => {
        if (element?.tagName !== 'P') return false
        const text = element.textContent ?? ''
        return [
          'AI eşleştirme önerisi',
          'onay akışı',
          'kapsam dışı satır raporlaması',
          'gerçekçi senaryolar',
        ].every((part) => text.includes(part))
      })
      expect(note).toBeInTheDocument()
    })

    it('boş şablonu sunucudan indirir', async () => {
      const { calls } = installFetchMock({
        'GET /api/template': templateHandler,
      })
      renderApp('/')

      const panel = document.querySelector('#hizli-baslangic') as HTMLElement
      await userEvent.click(
        within(panel).getByRole('button', { name: /Boş Veri Şablonunu İndir/ }),
      )

      expect(callsTo(calls, 'GET', '/api/template')).toHaveLength(1)
    })

    it('örnek veriyi dosya indirmeden analiz eder', async () => {
      const { calls } = installFetchMock({
        'GET /examples/proje-ornek-metraj.xlsx': sampleFileHandler,
        'POST /api/analyze': () => jsonResponse(SAMPLE_ANALYSIS),
      })
      renderApp('/')

      await userEvent.click(
        screen.getByRole('button', {
          name: /Örnek Veri ile Hemen Dene \(AI Demo\)/,
        }),
      )

      // Dosya **indirilmez**: statik dosya `fetch` ile alınır ve aynı
      // `/api/analyze` yoluna verilir.
      expect(
        callsTo(calls, 'GET', '/examples/proje-ornek-metraj.xlsx'),
      ).toHaveLength(1)
      const analyzeCalls = callsTo(calls, 'POST', '/api/analyze')
      expect(analyzeCalls).toHaveLength(1)

      const uploaded = analyzeCalls[0].form?.get('file')
      expect(uploaded).toBeInstanceOf(File)
      expect((uploaded as File).name).toBe('proje-ornek-metraj.xlsx')

      // Analiz ekranına geçilir ve gerçek sunucu özeti gösterilir.
      expect(
        await screen.findByRole('heading', { name: 'Metraj analizi' }),
      ).toBeInTheDocument()
      expect(screen.getByText('40 satır · sunucu yanıtı')).toBeInTheDocument()
      expect(screen.getByText('proje-ornek-metraj.xlsx')).toBeInTheDocument()
    })

    it('örnek dosya alınamazsa analiz başlatmaz, hata gösterir', async () => {
      const { calls } = installFetchMock({
        'GET /examples/proje-ornek-metraj.xlsx': () =>
          new Response('yok', { status: 404 }),
      })
      renderApp('/')

      await userEvent.click(
        screen.getByRole('button', {
          name: /Örnek Veri ile Hemen Dene \(AI Demo\)/,
        }),
      )

      expect(await screen.findByText(/Örnek proje metrajı alınamadı/)).toBeInTheDocument()
      // Ağ çağrısı yapılmadı: yükleme akışı hiç başlamadı.
      expect(callsTo(calls, 'POST', '/api/analyze')).toHaveLength(0)
      // Ana sayfada kalınır.
      expect(
        screen.getByRole('heading', {
          name: /Metrajı incelenmiş bir satın alma listesine çevirin/,
        }),
      ).toBeInTheDocument()
    })

    it('analiz hata verirse analiz ekranına geçmez', async () => {
      installFetchMock({
        'GET /examples/proje-ornek-metraj.xlsx': sampleFileHandler,
        'POST /api/analyze': () =>
          jsonResponse(
            {
              error: {
                code: 'corrupt-file',
                message: 'Dosya geçerli bir .xlsx paketi değil.',
                detail: '',
                suggestion: '',
                issues: [],
              },
            },
            422,
          ),
      })
      renderApp('/')

      await userEvent.click(
        screen.getByRole('button', {
          name: /Örnek Veri ile Hemen Dene \(AI Demo\)/,
        }),
      )

      // Hata ana sayfada değil, akışta görünür; kullanıcı yükleme adımına gider.
      expect(
        await screen.findByRole('heading', {
          name: /Metrajı incelenmiş bir satın alma listesine çevirin/,
        }),
      ).toBeInTheDocument()
    })
  })
})
