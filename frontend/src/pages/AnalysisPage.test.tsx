import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { installFetchMock, jsonResponse } from '../test/server'
import { chooseFile, metrajFile, renderApp } from '../test/harness'
import {
  analysisWithAi,
  analysisWithInvalidRow,
  makeAnalysis,
} from '../test/fixtures/demo'

/**
 * Analysis ekranı testleri.
 *
 * Ekran hiçbir sayıyı hesaplamaz: tüm değerler `/api/analyze` yanıtından
 * gelir. Testler bu yüzden sunucunun verdiği sayıları **birebir** ararlar.
 */

async function analyzeAndOpen(
  response: ReturnType<typeof makeAnalysis> | ReturnType<typeof analysisWithAi>,
) {
  installFetchMock({ 'POST /api/analyze': () => jsonResponse(response) })
  renderApp('/upload')

  chooseFile(
    screen.getByLabelText('Metraj dosyası seç', { selector: 'input' }) as HTMLInputElement,
    metrajFile(),
  )
  await screen.findByText('Analiz tamamlandı')
  await userEvent.click(screen.getByRole('button', { name: 'Analize geç' }))
  await screen.findByRole('heading', { name: 'Metraj analizi' })
}

/** Başlıktaki "10 / 18 hesaba uygun" metni — parçalara bölünmüş. */
function headerSummary(): string {
  const header = screen.getByRole('heading', { name: 'Metraj analizi' }).closest('header')
  return header?.textContent?.replace(/\s+/g, ' ') ?? ''
}

describe('AnalysisPage', () => {  it('analiz yoksa boş durum gösterir', () => {
    installFetchMock()
    renderApp('/analysis')

    expect(
      screen.getByText('Henüz analiz edilmiş bir dosya yok'),
    ).toBeInTheDocument()
  })

  it('sunucunun satır dağılımını aynen gösterir', async () => {
    await analyzeAndOpen(makeAnalysis())

    const distribution = screen.getByText('Satır dağılımı').closest('div')
    expect(distribution).not.toBeNull()

    expect(screen.getByText('Kural ile eşleşti')).toBeInTheDocument()
    expect(screen.getByText('Onay bekliyor')).toBeInTheDocument()
    expect(screen.getByText('Hariç tutuldu')).toBeInTheDocument()
    expect(screen.getByText('Geçersiz')).toBeInTheDocument()
    expect(headerSummary()).toContain('10')
    expect(headerSummary()).toContain('/ 18 hesaba uygun')
  })

  it('AI kapalıyken deterministik akışın sürdüğünü söyler', async () => {
    await analyzeAndOpen(makeAnalysis())

    expect(screen.getByText('AI sağlayıcısı kapalı')).toBeInTheDocument()
    expect(
      screen.getByText(/Deterministik akış çalışmaya devam ediyor/),
    ).toBeInTheDocument()
    expect(screen.getByText('Kapalı')).toBeInTheDocument()
  })

  it('AI açıkken sayıları ve sağlayıcı adını gösterir', async () => {
    await analyzeAndOpen(analysisWithAi())

    expect(screen.getByText('Açık · scripted')).toBeInTheDocument()
    expect(screen.getByText('Değerlendirilen')).toBeInTheDocument()
    expect(screen.getByText('Öneri üretildi')).toBeInTheDocument()
    expect(screen.getByText('Belirsiz')).toBeInTheDocument()
    expect(screen.getByText('Eşleşme yok')).toBeInTheDocument()
    expect(screen.getByText('Hata')).toBeInTheDocument()
    expect(
      screen.getByText(/AI hatası analizi durdurmadı/),
    ).toBeInTheDocument()
  })

  it('AI önerilerini otomatik onaylamaz: onaylı sayısı sıfır kalır', async () => {
    await analyzeAndOpen(analysisWithAi())

    expect(headerSummary()).toContain('10')
    expect(headerSummary()).not.toContain('13')
  })

  it('uyarıları kaybetmeden listeler', async () => {
    await analyzeAndOpen(
      makeAnalysis({
        warnings: [
          'Bazı satırlar için AI önerisi kullanılamadı.',
          '2 satır veri olarak okunamadı.',
        ],
      }),
    )

    expect(screen.getByText('Analiz uyarıları')).toBeInTheDocument()
    expect(
      screen.getByText('Bazı satırlar için AI önerisi kullanılamadı.'),
    ).toBeInTheDocument()
    expect(screen.getByText('2 satır veri olarak okunamadı.')).toBeInTheDocument()
  })

  it('yok sayılan sütunları gösterir', async () => {
    await analyzeAndOpen(makeAnalysis({ ignoredColumns: ['Tedarikçi', 'Fiyat'] }))

    expect(screen.getByText('Yok sayılan sütunlar')).toBeInTheDocument()
    expect(screen.getByText('Tedarikçi, Fiyat')).toBeInTheDocument()
  })

  it('geçersiz satır varsa hesap dışı uyarısı verir', async () => {
    await analyzeAndOpen(analysisWithInvalidRow())

    expect(screen.getByText('1 geçersiz satır')).toBeInTheDocument()
    expect(
      screen.getByText(/veri olarak okunamadı ve hesaba gönderilemez/),
    ).toBeInTheDocument()
  })

  it('hesap dışı satır varsa KISMİ değil, ayrı bölüm uyarısı verir', async () => {
    await analyzeAndOpen(makeAnalysis())

    // Hesap dışı satır, ağırlık toplamını KISMİ yapmaz; raporda ayrı
    // "Hesaba Alınmayanlar" bölümünde listelenir.
    expect(screen.getByText('Hesap dışı satırlar var')).toBeInTheDocument()
    expect(screen.getByText(/Hesaba Alınmayanlar/)).toBeInTheDocument()
    expect(
      screen.getByText(/ağırlık toplamını etkilemez/),
    ).toBeInTheDocument()
    expect(screen.queryByText(/KISMİ/)).not.toBeInTheDocument()
  })

  it('satır dağılımı sunucu toplamıyla tutarlı', async () => {
    await analyzeAndOpen(makeAnalysis())

    // 10 rule + 0 onaylı + 4 pending + 0 red + 4 excluded + 0 geçersiz = 18
    const eligibleRow = screen.getByText('Hesaba uygun').parentElement
    expect(eligibleRow?.textContent).toContain('10')

    const heldRow = screen.getByText('Hesap dışı').parentElement
    expect(heldRow?.textContent).toContain('8')
  })
})
