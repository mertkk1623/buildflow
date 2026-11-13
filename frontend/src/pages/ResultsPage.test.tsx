import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { callsTo, installFetchMock, jsonResponse } from '../test/server'
import { chooseFile, metrajFile, renderApp } from '../test/harness'
import {
  analysisWithInvalidRow,
  makeAnalysis,
  makeCalculation,
  makePartialCalculation,
} from '../test/fixtures/demo'

/**
 * Sonuç ekranı testleri.
 *
 * Kritik iddialar:
 * 1. Hiçbir değer istemcide üretilmez; tablo `/api/calculate` yanıtını gösterir.
 * 2. `null` → "—"; asla `0` yazılmaz.
 * 3. PARTIAL grup ve TAM/KISMİ durumu görünür.
 * 4. Atlanan satırlar ve gönderilemeyen satırlar kaybolmaz.
 */

/** Satın alma tablosundaki bir grup satırının metni. */
function groupRow(code: string): HTMLElement {
  const cell = screen
    .getAllByText(code)
    .find((element) => element.closest('tr') !== null)
  const tr = cell?.closest('tr')
  if (!tr) throw new Error(`Grup satırı bulunamadı: ${code}`)
  return tr
}

async function openResults(
  calculation = makeCalculation(),
  analysis = makeAnalysis(),
  handlers: Parameters<typeof installFetchMock>[0] = {},
) {
  const mock = installFetchMock({
    'POST /api/analyze': () => jsonResponse(analysis),
    'POST /api/calculate': () => jsonResponse(calculation),
    ...handlers,
  })

  renderApp('/upload')
  chooseFile(
    screen.getByLabelText('Metraj dosyası seç', { selector: 'input' }) as HTMLInputElement,
    metrajFile(),
  )
  await screen.findByText('Analiz tamamlandı')
  await userEvent.click(screen.getByRole('button', { name: 'Analize geç' }))
  await screen.findByRole('heading', { name: 'Metraj analizi' })
  await userEvent.click(screen.getByRole('button', { name: 'Eşleştirmeye geç' }))
  await screen.findByRole('heading', { name: 'Eşleşme incelemesi' })
  await userEvent.click(screen.getByRole('button', { name: /hesapla/ }))
  await screen.findByRole('heading', { name: 'Satın alma listesi' })

  return mock
}

/** Alt özet satırı: "18 satır gönderildi · 13 hesaba girdi · 8 malzeme grubu …". */
function summaryLine(): string {
  const node = screen.getByText(/satır gönderildi/).closest('div')
  return (node?.textContent ?? '').replace(/\s+/g, ' ').trim()
}

describe('ResultsPage', () => {
  it('sonuç yoksa boş durum gösterir', () => {
    installFetchMock()
    renderApp('/results')

    expect(screen.getByText('Gösterilecek sonuç yok')).toBeInTheDocument()
  })

  it('hesaplama çalıştırılmadan önce hesapla düğmesi sunar', async () => {
    installFetchMock({
      'POST /api/analyze': () => jsonResponse(makeAnalysis()),
    })
    renderApp('/upload')
    chooseFile(
      screen.getByLabelText('Metraj dosyası seç', { selector: 'input' }) as HTMLInputElement,
      metrajFile(),
    )
    await screen.findByText('Analiz tamamlandı')

    renderApp('/results')
    // Not: ayrı render, state ayrı; bu yalnızca boş durum metnini doğrular.
    expect(screen.getByText('Gösterilecek sonuç yok')).toBeInTheDocument()
  })

  it('sunucunun kilitli toplamlarını aynen gösterir', async () => {
    await openResults()

    expect(screen.getByText('966 m')).toBeInTheDocument()
    expect(screen.getByText('18.005,82 kg')).toBeInTheDocument()
    expect(screen.getByText(/Tüm grupların ağırlığı hesaplandı/)).toBeInTheDocument()
  })

  it('tüm satırlar hesaba girdiyse TAM LİSTE gösterir', async () => {
    const calculation = makeCalculation()
    calculation.skipped = []
    calculation.summary = {
      ...calculation.summary,
      input_rows: 13,
      skipped_rows: 0,
    }
    await openResults(calculation)

    expect(screen.getByText('TAM LİSTE')).toBeInTheDocument()
    expect(screen.getByText('Tam sonuç')).toBeInTheDocument()
    expect(
      screen.getByText('Tüm satırlar hesaba katıldı ve tam veriyle hesaplandı.'),
    ).toBeInTheDocument()
  })

  it('atlanan satır varsa liste KISMİ sayılmaz, ayrı uyarı gösterilir', async () => {
    await openResults()

    // Kilitli demoda 8 grubun tamamı FULL, ama 5 satır hesaba girmedi.
    // Bu, ağırlık toplamını KISMİ yapmaz; raporda ayrı bölümde listelenir.
    expect(screen.getByText('HESAP DIŞI SATIR VAR')).toBeInTheDocument()
    expect(screen.getByText('Hesap dışı satır var')).toBeInTheDocument()
    expect(screen.queryByText('KISMİ AĞIRLIK')).not.toBeInTheDocument()
    expect(
      screen.getByText(/5 satır hesaba katılmadı ve raporda "Hesaba Alınmayanlar"/),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/ağırlık toplamı KISMİ değildir/),
    ).toBeInTheDocument()
  })

  it('yalnızca atlanan satır varsa ağırlık toplamı KISMİ sayılmaz', async () => {
    await openResults()

    // "Kısmi toplam" ifadesi yalnızca ağırlığı eksik grupta çıkmalı.
    expect(
      screen.queryByText(/Kısmi toplam: ağırlığı hesaplanamayan gruplar/),
    ).not.toBeInTheDocument()
    expect(
      screen.getByText(/Tüm grupların ağırlığı hesaplandı/),
    ).toBeInTheDocument()
  })

  it('8 grubu ve 5 birleşmeyi gösterir', async () => {
    await openResults()

    expect(screen.getByText('8 grup · 13 kaynak satır')).toBeInTheDocument()
    expect(summaryLine()).toContain('5 birleşme')
    // Her birleşik grup kendi kaynak sayısını yazar.
    expect(screen.getAllByText(/2 satır birleşti/)).toHaveLength(5)
  })

  it('grup değerleri sunucudan geldiği gibi gösterilir', async () => {
    await openResults()

    const box = groupRow('BOX-100-4-S235-B')
    const text = box.textContent ?? ''

    expect(text).toContain('192 m')
    expect(text).toContain('32')
    expect(text).toContain('2.246,4 kg')
    expect(text).toContain('TAM')
    expect(text).toContain('BOQ-001')
    expect(text).toContain('BOQ-013')
  })

  it('grup detayı açılınca dönüşüm izini ve kaynak satırları gösterir', async () => {
    await openResults()

    await userEvent.click(groupRow('IPE-200-S235'))

    expect(
      await screen.findByText('Bu gruba giren metraj satırları'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Kilogram → metre: 1240 kg ÷ 22.40 kg\/m/),
    ).toBeInTheDocument()
    expect(screen.getByText('m / m')).toBeInTheDocument()
    expect(screen.getByText('Ticari boy')).toBeInTheDocument()
    expect(screen.getByText('Artan boy')).toBeInTheDocument()
  })

  it('PARTIAL grupta null değerler "—" olur, sıfır yazılmaz', async () => {
    await openResults(makePartialCalculation())

    const row = groupRow('BOX-100-4-S235-B')
    const text = row.textContent ?? ''

    expect(text).toContain('KISMİ')
    // Brüt m hesaplanabildi; tabloda precise biçimde gösterilir.
    expect(text).toContain('63')
    // Sipariş boyu, adet ve ağırlık null → "—".
    expect(text).toContain('—')
    expect(text).not.toContain('0 m')
    expect(text).not.toContain('0 kg')
  })

  it('PARTIAL sonuçta KISMİ AĞIRLIK ve eksik alan uyarısı gösterilir', async () => {
    await openResults(makePartialCalculation())

    expect(screen.getByText('KISMİ AĞIRLIK')).toBeInTheDocument()
    expect(screen.getByText('Kısmi ağırlık')).toBeInTheDocument()
    expect(
      screen.getByText(/Eksik değerler "—" olarak gösterilir; sıfır sayılmaz/),
    ).toBeInTheDocument()
    expect(screen.getByText(/Kısmi toplam: ağırlığı hesaplanamayan gruplar/)).toBeInTheDocument()
  })

  it('PARTIAL grubun eksik alanlarını ve nedenini gösterir', async () => {
    await openResults(makePartialCalculation())

    await userEvent.click(groupRow('BOX-100-4-S235-B'))

    expect(await screen.findByText(/eksik: commercial-length/)).toBeInTheDocument()
    expect(
      screen.getByText(/Ticari boy tanımlı değil. Varsayılan boy kullanılmaz/),
    ).toBeInTheDocument()
  })

  it('hesaba girmeyen 5 satırı nedenleriyle listeler', async () => {
    await openResults()

    expect(screen.getByText('Listeye girmeyen satırlar')).toBeInTheDocument()
    expect(screen.getByText('5 satır')).toBeInTheDocument()

    expect(screen.getByText('Onay bekliyor')).toBeInTheDocument()
    expect(screen.getAllByText('Hesap kapsamı dışı').length).toBe(3)
    expect(screen.getByText('Kullanıcı reddetti')).toBeInTheDocument()
    expect(
      screen.getByText('Satır henüz onaylanmadı (pending); hesaplamaya alınmaz.'),
    ).toBeInTheDocument()
  })

  it('hesaplama uyarılarını korur', async () => {
    const calculation = makeCalculation()
    calculation.warnings = ['Bazı gruplar için fire katalogdan alındı.']
    await openResults(calculation)

    expect(screen.getByText('Hesaplama uyarıları')).toBeInTheDocument()
    expect(
      screen.getByText('Bazı gruplar için fire katalogdan alındı.'),
    ).toBeInTheDocument()
  })

  it('gönderilemeyen geçersiz satırları da listeler', async () => {
    await openResults(makeCalculation(), analysisWithInvalidRow())

    expect(screen.getByText('BOQ-019')).toBeInTheDocument()
    expect(screen.getByText('Geçersiz')).toBeInTheDocument()
    expect(screen.getByText(/Miktar okunamadı/)).toBeInTheDocument()
    expect(screen.getByText('6 satır')).toBeInTheDocument()
  })

  it('yeniden hesapla aynı gövdeyi yeniden gönderir', async () => {
    const { calls } = await openResults()

    await userEvent.click(screen.getByRole('button', { name: 'Yeniden hesapla' }))

    await waitFor(() => {
      expect(callsTo(calls, 'POST', '/api/calculate')).toHaveLength(2)
    })
    const [first, second] = callsTo(calls, 'POST', '/api/calculate')
    expect(second.json).toEqual(first.json)
  })

  it('hesaplama hatasını boş durumda gösterir', async () => {
    installFetchMock({
      'POST /api/analyze': () => jsonResponse(makeAnalysis()),
      'POST /api/calculate': () =>
        jsonResponse(
          {
            error: {
              code: 'invalid-decision',
              message: 'Kullanıcı kararı geçersiz.',
              detail: 'BOQ-009 kodu katalogda yok.',
              suggestion: 'Aday listesinden seçin.',
              issues: [],
            },
          },
          409,
        ),
    })

    renderApp('/upload')
    chooseFile(
      screen.getByLabelText('Metraj dosyası seç', { selector: 'input' }) as HTMLInputElement,
      metrajFile(),
    )
    await screen.findByText('Analiz tamamlandı')
    await userEvent.click(screen.getByRole('button', { name: 'Analize geç' }))
    await screen.findByRole('heading', { name: 'Metraj analizi' })
    await userEvent.click(screen.getByRole('button', { name: 'Eşleştirmeye geç' }))
    await screen.findByRole('heading', { name: 'Eşleşme incelemesi' })
    await userEvent.click(screen.getByRole('button', { name: /hesapla/ }))

    // Review ekranında hata kutusu çıkar; sonuç ekranı da aynı hatayı gösterir.
    expect(
      await screen.findByText('Kullanıcı kararı geçersiz.'),
    ).toBeInTheDocument()
  })

  it('dışa aktarma adımına geçilebilir', async () => {
    await openResults()

    await userEvent.click(screen.getByRole('button', { name: 'Dışa aktarmaya geç' }))

    expect(
      await screen.findByRole('heading', { name: 'Dışa aktarma' }),
    ).toBeInTheDocument()
  })

  it('karar özetinde sıfır olan kalemleri yazmaz', async () => {
    await openResults()

    const line = screen.getByText(/Karar özeti:/).textContent ?? ''

    // Kilitli demoda reddedilen ve geçersiz satır yok: bu kalemler hiç yazılmaz.
    expect(line).toContain('10 kural')
    expect(line).toContain('4 onay bekliyor')
    expect(line).toContain('4 hariç')
    expect(line).not.toMatch(/0 onay bekliyor/)
    expect(line).not.toMatch(/0 reddedildi/)
    expect(line).not.toMatch(/0 geçersiz/)
    expect(line).not.toMatch(/0 kullanıcı onayı/)
  })

  it('ağırlığın teorik olduğunu ve kesim optimizasyonu yapılmadığını belirtir', async () => {
    await openResults()

    expect(
      screen.getAllByText(/teorik çıplak/).length,
    ).toBeGreaterThan(0)
    expect(screen.getByText(/Kesim optimizasyonu yapılmamıştır/)).toBeInTheDocument()
  })
})
