import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { installFetchMock, jsonResponse } from '../test/server'
import { chooseFile, metrajFile, renderApp } from '../test/harness'
import {
  CORRUPT_FILE_ERROR,
  MISSING_COLUMN_ERROR,
  analysisWithInvalidRow,
  makeAnalysis,
} from '../test/fixtures/demo'

/**
 * Upload ekranı testleri.
 *
 * İki katmanlı doğrulama: yerel ön kontrol (uzantı/boyut) hızlı geri bildirim
 * verir, gerçek doğrulama sunucudadır. Hata mesajı kullanıcıya **tek** yerde
 * ve ham ayrıntı olmadan gösterilir.
 */

const fileInput = () =>
  screen.getByLabelText('Metraj dosyası seç', { selector: 'input' }) as HTMLInputElement

describe('UploadPage', () => {
  it('dosya seçilince analiz eder ve özeti gösterir', async () => {
    installFetchMock({ 'POST /api/analyze': () => jsonResponse(makeAnalysis()) })
    renderApp('/upload')

    chooseFile(fileInput(), metrajFile('metraj.xlsx'))

    expect(await screen.findByText('Analiz tamamlandı')).toBeInTheDocument()
    expect(screen.getAllByText('metraj.xlsx').length).toBeGreaterThan(0)

    const summary = screen.getByText('Analiz tamamlandı').parentElement?.textContent ?? ''
    expect(summary).toContain('18')
    expect(summary).toContain('10 kural')
    expect(summary).toContain('4 onay bekliyor')
    expect(summary).toContain('4 hariç')
  })

  it('analiz sonrası bir sonraki adıma geçilebilir', async () => {
    installFetchMock({ 'POST /api/analyze': () => jsonResponse(makeAnalysis()) })
    renderApp('/upload')

    chooseFile(fileInput(), metrajFile())
    await screen.findByText('Analiz tamamlandı')

    const next = screen.getByRole('button', { name: 'Analize geç' })
    expect(next).toBeEnabled()
    await userEvent.click(next)

    expect(await screen.findByRole('heading', { name: 'Metraj analizi' })).toBeInTheDocument()
  })

  it('.xlsx olmayan dosyayı sunucuya göndermeden reddeder', async () => {
    const { calls } = installFetchMock()
    renderApp('/upload')

    chooseFile(fileInput(), metrajFile('metraj.csv'))

    expect(await screen.findByText('Dosya seçilemedi')).toBeInTheDocument()
    expect(screen.getByText(/Desteklenmeyen dosya biçimi/)).toBeInTheDocument()
    expect(calls.filter((call) => call.path === '/api/analyze')).toHaveLength(0)
  })

  it('boş dosyayı reddeder', async () => {
    installFetchMock()
    renderApp('/upload')

    chooseFile(fileInput(), metrajFile('bos.xlsx', 0))

    expect(await screen.findByText('Dosya seçilemedi')).toBeInTheDocument()
    expect(screen.getByText(/dosya boş/i)).toBeInTheDocument()
  })

  it('10 MB üzeri dosyayı yerelde reddeder', async () => {
    installFetchMock()
    renderApp('/upload')

    chooseFile(fileInput(), metrajFile('buyuk.xlsx', 11 * 1024 * 1024))

    expect(await screen.findByText('Dosya seçilemedi')).toBeInTheDocument()
    expect(screen.getByText(/Dosya çok büyük/)).toBeInTheDocument()
  })

  it('eksik kolon hatasını kullanıcıya anlaşılır gösterir', async () => {
    installFetchMock({
      'POST /api/analyze': () => jsonResponse(MISSING_COLUMN_ERROR, 422),
    })
    renderApp('/upload')

    chooseFile(fileInput(), metrajFile())

    expect(await screen.findByText(/Zorunlu kolon\(lar\) eksik/)).toBeInTheDocument()
    expect(screen.getByText(/Bulunan kolonlar/)).toBeInTheDocument()
    expect(screen.getByText(/Şablondaki başlıkları kullanın/)).toBeInTheDocument()
    // Ham ayrıntı gösterilmez.
    expect(screen.queryByText(/Traceback/)).not.toBeInTheDocument()
  })

  it('bozuk dosya hatasını gösterir', async () => {
    installFetchMock({
      'POST /api/analyze': () => jsonResponse(CORRUPT_FILE_ERROR, 400),
    })
    renderApp('/upload')

    chooseFile(fileInput(), metrajFile())

    expect(await screen.findByText(/geçerli bir \.xlsx paketi değil/)).toBeInTheDocument()
    expect(screen.getByText(/Excel ile yeniden kaydedip/)).toBeInTheDocument()
  })

  it('analiz uyarılarını ve yok sayılan sütunları gösterir', async () => {
    installFetchMock({
      'POST /api/analyze': () =>
        jsonResponse(
          makeAnalysis({
            warnings: ['2 satır veri olarak okunamadı; hesaba katılmaz.'],
            ignoredColumns: ['Tedarikçi', 'Not'],
          }),
        ),
    })
    renderApp('/upload')

    chooseFile(fileInput(), metrajFile())

    expect(await screen.findByText('Analiz uyarıları')).toBeInTheDocument()
    expect(
      screen.getByText('2 satır veri olarak okunamadı; hesaba katılmaz.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Yok sayılan sütunlar')).toBeInTheDocument()
    expect(screen.getByText('Tedarikçi, Not')).toBeInTheDocument()
  })

  it('şablon indirme hatasını ayrı gösterir', async () => {
    installFetchMock({
      'GET /api/template': () =>
        jsonResponse(
          {
            error: {
              code: 'server-error',
              message: 'Şablon dosyası üretilemedi.',
              detail: '',
              suggestion: 'Daha sonra tekrar deneyin.',
              issues: [],
            },
          },
          500,
        ),
    })
    renderApp('/upload')

    await userEvent.click(screen.getByRole('button', { name: 'Şablonu indir' }))

    expect(await screen.findByText('Şablon dosyası üretilemedi.')).toBeInTheDocument()
  })

  it('bağlantı hatasında backend’i kontrol etmeyi önerir', async () => {
    installFetchMock({
      'POST /api/analyze': () => {
        throw new TypeError('Failed to fetch')
      },
    })
    renderApp('/upload')

    chooseFile(fileInput(), metrajFile())

    expect(await screen.findByText('Bağlantı kurulamadı')).toBeInTheDocument()
    expect(screen.getByText(/Backend servisinin çalıştığını/)).toBeInTheDocument()
  })

  it('analiz sürerken dosya seçimi kilitlenir', async () => {
    let release: (response: Response) => void = () => {}
    const pending = new Promise<Response>((resolve) => {
      release = resolve
    })
    installFetchMock({ 'POST /api/analyze': () => pending })
    renderApp('/upload')

    chooseFile(fileInput(), metrajFile())
    await waitFor(() =>
      expect(screen.getByText(/Dosya sunucuda analiz ediliyor/)).toBeInTheDocument(),
    )

    expect(screen.getByRole('button', { name: 'Analiz sürüyor…' })).toBeDisabled()

    release(jsonResponse(makeAnalysis()))
    expect(await screen.findByText('Analiz tamamlandı')).toBeInTheDocument()
  })

  it('geçersiz satır varsa özet bunu belirtir', async () => {
    installFetchMock({
      'POST /api/analyze': () => jsonResponse(analysisWithInvalidRow()),
    })
    renderApp('/upload')

    chooseFile(fileInput(), metrajFile())

    expect(await screen.findByText(/1 geçersiz/)).toBeInTheDocument()
  })

  it('Fire sütununu "isteğe bağlı" diye tanıtmaz', () => {
    installFetchMock()
    renderApp('/upload')

    // Boş fire satırı hesaba girmez; "isteğe bağlı" yanlış beklenti üretir.
    expect(screen.getByText('Fire (%)')).toBeInTheDocument()
    expect(screen.getByText(/boşsa satır hesaba girmez/)).toBeInTheDocument()
    expect(screen.queryByText(/İsteğe bağlı/)).not.toBeInTheDocument()
  })
})
