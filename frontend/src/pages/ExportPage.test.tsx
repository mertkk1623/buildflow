import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { callsTo, fileResponse, installFetchMock, jsonResponse } from '../test/server'
import { chooseFile, metrajFile, renderApp } from '../test/harness'
import {
  INVALID_DECISION_ERROR,
  REPORT_EMPTY_ERROR,
  makeAnalysis,
  makeCalculation,
  makePartialCalculation,
} from '../test/fixtures/demo'

/**
 * Dışa aktarma ekranı testleri.
 *
 * Rapor gövdesi `/api/calculate` gövdesiyle aynıdır; istemci dosya üretmez.
 * Bu yüzden testler (a) doğru endpoint'e (b) aynı gövdenin gittiğini ve
 * (c) sunucunun verdiği dosya adının kullanıldığını doğrular.
 */

const XLSX_MIME =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
const PDF_MIME = 'application/pdf'

async function openExport(
  calculation = makeCalculation(),
  handlers: Parameters<typeof installFetchMock>[0] = {},
  approvals: [boqNo: string, code: string][] = [],
) {
  const mock = installFetchMock({
    'POST /api/analyze': () => jsonResponse(makeAnalysis()),
    'POST /api/calculate': () => jsonResponse(calculation),
    'POST /api/report/excel': () =>
      fileResponse('xlsx-bytes', {
        filename: 'buildflow-satin-alma-20261113-1042.xlsx',
        contentType: XLSX_MIME,
        disposition: 'extended',
      }),
    'POST /api/report/pdf': () =>
      fileResponse('%PDF-1.4', {
        filename: 'buildflow-satin-alma-20261113-1042.pdf',
        contentType: PDF_MIME,
        disposition: 'extended',
      }),
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

  for (const [boqNo, code] of approvals) {
    const cell = screen
      .getAllByText(boqNo)
      .find((element) => element.closest('tr') !== null)
    await userEvent.click(cell!.closest('tr')!)
    const dialog = screen.getByRole('dialog')
    const custom = within(dialog).getByLabelText('Katalogdan başka bir kod')
    await userEvent.type(custom, code)
    await userEvent.click(within(dialog).getByRole('button', { name: 'Onayla' }))
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
    )
  }

  await userEvent.click(screen.getByRole('button', { name: /hesapla/ }))
  await screen.findByRole('heading', { name: 'Satın alma listesi' })
  await userEvent.click(screen.getByRole('button', { name: 'Dışa aktarmaya geç' }))
  await screen.findByRole('heading', { name: 'Dışa aktarma' })

  return mock
}

describe('ExportPage', () => {
  it('hesaplama yoksa indirilecek rapor olmadığını söyler', () => {
    installFetchMock()
    renderApp('/export')

    expect(screen.getByText('İndirilecek rapor yok')).toBeInTheDocument()
  })

  it('raporda yer alacak malzemeleri sunucu verisinden önizler', async () => {
    await openExport()

    expect(screen.getByText('Rapora girecek malzemeler')).toBeInTheDocument()
    expect(screen.getByText('8 kalem')).toBeInTheDocument()
    expect(
      screen.getAllByText('Kutu profil 100×100×4 · S235 · siyah').length,
    ).toBeGreaterThan(0)

    // Önizleme satırı tek bir metin düğümü değil: "63 m brüt · 1.207,8 kg".
    const previewRow = screen
      .getAllByText('BOX-150-100-5-S235-B')
      .find((element) => element.closest('li') !== null)
      ?.closest('li')
    const text = previewRow?.textContent ?? ''
    expect(text).toContain('63 m brüt')
    expect(text).toContain('1.207,8 kg')
    expect(text).toContain('TAM')
  })

  it('Excel indirir: doğru endpoint, aynı gövde, sunucunun dosya adı', async () => {
    const { calls } = await openExport(makeCalculation(), {}, [
      ['BOQ-003', 'IPE-200-S235'],
      ['BOQ-004', 'IPE-240-S355'],
    ])

    await userEvent.click(screen.getByRole('button', { name: 'Excel indir' }))

    expect(
      await screen.findByText(/buildflow-satin-alma-20261113-1042\.xlsx/),
    ).toBeInTheDocument()

    const [call] = callsTo(calls, 'POST', '/api/report/excel')
    const body = call.json as {
      rows: unknown[]
      decisions: { boq_no: string; action: string; code: string | null }[]
    }

    expect(body.rows).toHaveLength(18)
    expect(body.decisions).toHaveLength(2)
    expect(body.decisions.every((item) => item.action === 'approve')).toBe(true)
    expect(call.headers['Content-Type']).toBe('application/json')
    expect(screen.getByText('İndirildi')).toBeInTheDocument()
  })

  it('PDF indirir ve dosya adını gösterir', async () => {
    await openExport()

    await userEvent.click(screen.getByRole('button', { name: 'PDF indir' }))

    expect(
      await screen.findByText(/buildflow-satin-alma-20261113-1042\.pdf/),
    ).toBeInTheDocument()
  })

  it('indirme blob’unu tarayıcıya verir (URL oluşturulur)', async () => {
    await openExport()

    // `URL` sınıfı bozulmaz: yalnızca indirme metodu gözlemlenir. Aksi halde
    // `new URL(...)` ile adres çözen ağ katmanı da kırılırdı.
    const createObjectURL = vi.spyOn(URL, 'createObjectURL')
    const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL')

    await userEvent.click(screen.getByRole('button', { name: 'Excel indir' }))

    await waitFor(() => expect(createObjectURL).toHaveBeenCalledTimes(1))
    const blob = createObjectURL.mock.calls[0][0] as Blob
    expect(blob.type).toBe(XLSX_MIME)
    expect(await blob.text()).toBe('xlsx-bytes')

    createObjectURL.mockRestore()
    revokeObjectURL.mockRestore()
  })

  it('boş sonuçta `report-empty` hatasını gösterir, dosya adı yazmaz', async () => {
    await openExport(makeCalculation(), {
      'POST /api/report/excel': () =>
        jsonResponse(REPORT_EMPTY_ERROR, 422),
    })

    await userEvent.click(screen.getByRole('button', { name: 'Excel indir' }))

    expect(
      await screen.findByText('Rapor üretilecek onaylanmış kalem yok.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Eşleştirme ekranında en az bir satırı onaylayın/),
    ).toBeInTheDocument()
    expect(screen.queryByText(/^İndirildi:/)).not.toBeInTheDocument()
  })

  it('geçersiz kararda `invalid-decision` hatasını gösterir', async () => {
    await openExport(makeCalculation(), {
      'POST /api/report/pdf': () => jsonResponse(INVALID_DECISION_ERROR, 409),
    })

    await userEvent.click(screen.getByRole('button', { name: 'PDF indir' }))

    expect(
      await screen.findByText('Kullanıcı kararı geçersiz.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Sunucunun döndürdüğü aday kodlar/),
    ).toBeInTheDocument()
  })

  it('PDF ve Excel hatalarını birbirinden bağımsız gösterir', async () => {
    await openExport(makeCalculation(), {
      'POST /api/report/pdf': () => jsonResponse(REPORT_EMPTY_ERROR, 422),
    })

    await userEvent.click(screen.getByRole('button', { name: 'PDF indir' }))
    expect(
      await screen.findByText('Rapor üretilecek onaylanmış kalem yok.'),
    ).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Excel indir' }))
    expect(
      await screen.findByText(/buildflow-satin-alma-20261113-1042\.xlsx/),
    ).toBeInTheDocument()
    // PDF hatası hâlâ görünür.
    expect(
      screen.getByText('Rapor üretilecek onaylanmış kalem yok.'),
    ).toBeInTheDocument()
  })

  it('rapor oluşturma hatasında ham ayrıntı göstermez', async () => {
    await openExport(makeCalculation(), {
      'POST /api/report/excel': () =>
        jsonResponse(
          {
            error: {
              code: 'report-error',
              message: 'Rapor oluşturulamadı.',
              detail: '',
              suggestion: 'Tekrar deneyin.',
              issues: [],
            },
            traceback: 'Traceback (most recent call last): secret path',
          },
          500,
        ),
    })

    await userEvent.click(screen.getByRole('button', { name: 'Excel indir' }))
    await screen.findByText('Rapor oluşturulamadı.')

    expect(screen.queryByText(/Traceback/)).not.toBeInTheDocument()
    expect(screen.queryByText(/secret path/)).not.toBeInTheDocument()
  })

  it('KISMİ ağırlıkta uyarır ve raporun KISMİ işaretleneceğini söyler', async () => {
    await openExport(makePartialCalculation())

    expect(
      screen.getByText('Rapor KISMİ ağırlık toplamı içerecek'),
    ).toBeInTheDocument()
    expect(screen.getByText('Kısmi ağırlık')).toBeInTheDocument()
    expect(
      screen.getByText(/ağırlığı\s+hesaplanamayan gruplar toplama dahil edilmez/),
    ).toBeInTheDocument()
  })

  it('yalnızca atlanan satır varsa raporu KISMİ diye sunmaz', async () => {
    await openExport()

    // Kilitli demoda ağırlık tamdır; yalnızca 5 satır hesap dışıdır.
    expect(
      screen.getByText('Raporda hesaba katılmayan satırlar var'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Kısmi ağırlık')).not.toBeInTheDocument()
    expect(
      screen.getByText(
        /Hesaba Alınmayanlar" bölümünde nedenleriyle listelenir/,
      ),
    ).toBeInTheDocument()
  })

  it('rapor gövdesinin hesaplama gövdesiyle aynı olduğunu doğrular', async () => {
    const { calls } = await openExport(makeCalculation(), {}, [
      ['BOQ-003', 'IPE-200-S235'],
    ])

    await userEvent.click(screen.getByRole('button', { name: 'Excel indir' }))
    await screen.findByText(/buildflow-satin-alma/)

    const calculateBody = callsTo(calls, 'POST', '/api/calculate')[0].json
    const reportBody = callsTo(calls, 'POST', '/api/report/excel')[0].json
    expect(reportBody).toEqual(calculateBody)
  })

  it('rapor gövdesi eşleşme/hesap alanı içermez', async () => {
    const { calls } = await openExport()

    await userEvent.click(screen.getByRole('button', { name: 'Excel indir' }))
    await screen.findByText(/buildflow-satin-alma/)

    const serialized = JSON.stringify(callsTo(calls, 'POST', '/api/report/excel')[0].json)
    expect(serialized).not.toContain('matched_code')
    expect(serialized).not.toContain('weight_kg')
  })
})
