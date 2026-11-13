import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { installFetchMock, jsonResponse, callsTo } from '../test/server'
import { chooseFile, metrajFile, renderApp } from '../test/harness'
import {
  INVALID_DECISION_ERROR,
  analysisWithAi,
  makeAnalysis,
  makeCalculation,
} from '../test/fixtures/demo'

/**
 * Review ekranı testleri.
 *
 * Buradaki iddialar ürünün güvenlik çekirdeği:
 * 1. AI önerisi olan satır, kullanıcı onaylamadan hesaba giremez.
 * 2. AI önerisi "öneri" olarak etiketlenir, varsayılan seçili gelmez.
 * 3. Alternatif katalog kodu seçilebilir ve gövdeye **kullanıcı seçimi** gider.
 * 4. Red kararı satırı dışarıda bırakır.
 */

async function openReview(
  response: ReturnType<typeof makeAnalysis> = makeAnalysis(),
  handlers: Parameters<typeof installFetchMock>[0] = {},
) {
  installFetchMock({
    'POST /api/analyze': () => jsonResponse(response),
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
}

/** Satırı BOQ No ile açar. */
async function openRow(boqNo: string) {
  const row = rowElement(boqNo)
  await userEvent.click(row)
  return screen.getByRole('dialog')
}

/** BOQ No hücresinden tablo satırına çıkar. */
function rowElement(boqNo: string): HTMLElement {
  const cell = screen
    .getAllByText(boqNo)
    .find((element) => element.closest('tr') !== null)
  const tr = cell?.closest('tr')
  if (!tr) throw new Error(`Satır bulunamadı: ${boqNo}`)
  return tr
}

/** Satır var mı? */
function row(boqNo: string): HTMLElement | null {
  const cell = screen
    .queryAllByText(boqNo)
    .find((element) => element.closest('tr') !== null)
  return cell?.closest('tr') ?? null
}

/** Üstteki özet şeridi: "18 satır · 10 kural · 0 onaylı · 4 onay bekliyor …". */
function summaryStrip(): string {
  const label = screen.getAllByText('satır', { selector: 'span' })[0]
  const strip = label?.closest('div.rounded-lg')
  return (strip?.textContent ?? '').replace(/\s+/g, ' ').trim()
}

/** Drawer içindeki düğme. */
function drawerButton(dialog: HTMLElement, name: string) {
  return within(dialog).getByRole('button', { name })
}

describe('ReviewPage', () => {
  it('analiz yoksa boş durum gösterir', () => {
    installFetchMock()
    renderApp('/review')

    expect(screen.getByText('İncelenecek satır yok')).toBeInTheDocument()
  })

  it('tüm satırları sunucu sayılarıyla listeler', async () => {
    await openReview()

    expect(screen.getAllByText('18', { selector: 'span' }).length).toBeGreaterThan(0)
    expect(row('BOQ-001')).toBeInTheDocument()
    expect(row('BOQ-018')).toBeInTheDocument()
    expect(screen.getByText('4 satır onayınızı bekliyor')).toBeInTheDocument()
  })

  it('durum filtresi yalnızca ilgili satırları bırakır', async () => {
    await openReview()

    await userEvent.click(screen.getByRole('tab', { name: /Onay bekliyor/ }))

    expect(row('BOQ-003')).toBeInTheDocument()
    expect(row('BOQ-009')).toBeInTheDocument()
    expect(row('BOQ-001')).not.toBeInTheDocument()
    expect(row('BOQ-012')).not.toBeInTheDocument()
  })

  it('arama BOQ no ve açıklamada çalışır', async () => {
    await openReview()

    const search = screen.getByPlaceholderText('BOQ no veya açıklama ara…')
    await userEvent.type(search, 'lama')

    await waitFor(() => {
      expect(row('BOQ-008')).toBeInTheDocument()
    })
    expect(row('BOQ-001')).not.toBeInTheDocument()
  })

  it('eşleşen satır karar verilemez; yalnızca pending satır onaylanabilir', async () => {
    await openReview()

    const ruleDialog = await openRow('BOQ-001')
    expect(drawerButton(ruleDialog, 'Onayla')).toBeDisabled()
    expect(within(ruleDialog).getByText('Kural ile eşleşti')).toBeInTheDocument()
    await userEvent.click(drawerButton(ruleDialog, 'Paneli kapat'))

    const pendingDialog = await openRow('BOQ-003')
    expect(drawerButton(pendingDialog, 'Reddet')).toBeEnabled()
  })

  it('AI önerisi varsayılan seçili gelmez, onay düğmesi kilitlidir', async () => {
    await openReview(analysisWithAi())

    const dialog = await openRow('BOQ-003')

    expect(within(dialog).getByText('AI önerisi · onay gerekir')).toBeInTheDocument()
    expect(
      within(dialog).getByText(/Öneri otomatik onaylanmaz/),
    ).toBeInTheDocument()

    // Hiçbir aday seçili değil → onay pasif.
    expect(within(dialog).getByText('Önce bir aday seçin')).toBeInTheDocument()
    expect(drawerButton(dialog, 'Onayla')).toBeDisabled()

    const radios = within(dialog).getAllByRole('radio') as HTMLInputElement[]
    expect(radios.length).toBeGreaterThan(0)
    expect(radios.every((radio) => !radio.checked)).toBe(true)
  })

  it('AI önerisini seçip onaylamak gövdeye kullanıcı kararı olarak gider', async () => {
    const { calls } = installFetchMock({
      'POST /api/analyze': () => jsonResponse(analysisWithAi()),
      'POST /api/calculate': () => jsonResponse(makeCalculation()),
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

    const dialog = await openRow('BOQ-003')
    const radios = within(dialog).getAllByRole('radio')
    await userEvent.click(radios[0])
    expect(drawerButton(dialog, 'Onayla')).toBeEnabled()
    await userEvent.click(drawerButton(dialog, 'Onayla'))

    // Satır onaylı duruma geçti.
    await waitFor(() => {
      expect(summaryStrip()).toContain('3 onay bekliyor')
    })

    await userEvent.click(screen.getByRole('button', { name: 'Kısmi listeyle hesapla' }))
    await screen.findByRole('heading', { name: 'Satın alma listesi' })

    const [call] = callsTo(calls, 'POST', '/api/calculate')
    const body = call.json as {
      decisions: { boq_no: string; action: string; code: string | null }[]
    }
    const decision = body.decisions.find((item) => item.boq_no === 'BOQ-003')
    expect(decision).toBeDefined()
    expect(decision?.action).toBe('approve')
    expect(decision?.code).toBe('IPE-200-S235')
  })

  it('alternatif katalog kodu elle girilip onaylanabilir', async () => {
    await openReview()

    const dialog = await openRow('BOQ-009')
    const custom = within(dialog).getByLabelText('Katalogdan başka bir kod')
    await userEvent.type(custom, 'FLAT-40x5-S235-G')

    expect(drawerButton(dialog, 'Onayla')).toBeEnabled()
    await userEvent.click(drawerButton(dialog, 'Onayla'))

    await waitFor(() => {
      expect(summaryStrip()).toContain('3 onay bekliyor')
    })
  })

  it('red kararı satırı hesap dışı bırakır', async () => {
    await openReview()

    const dialog = await openRow('BOQ-009')
    await userEvent.click(drawerButton(dialog, 'Reddet'))

    await waitFor(() => {
      expect(summaryStrip()).toContain('1 reddedildi')
    })
    expect(summaryStrip()).toContain('3 onay bekliyor')
  })

  it('karar geri alınabilir', async () => {
    await openReview()

    const dialog = await openRow('BOQ-009')
    await userEvent.click(drawerButton(dialog, 'Reddet'))
    await waitFor(() => expect(summaryStrip()).toContain('1 reddedildi'))

    const reopened = await openRow('BOQ-009')
    await userEvent.click(drawerButton(reopened, 'Kararı geri al'))

    await waitFor(() => {
      expect(summaryStrip()).toContain('4 onay bekliyor')
    })
    expect(summaryStrip()).not.toContain('1 reddedildi')
  })

  it('karar verildikten sonra yeniden onay/red verilemez', async () => {
    await openReview()

    const dialog = await openRow('BOQ-009')
    await userEvent.click(drawerButton(dialog, 'Reddet'))
    await waitFor(() => expect(summaryStrip()).toContain('1 reddedildi'))

    const reopened = await openRow('BOQ-009')
    expect(drawerButton(reopened, 'Onayla')).toBeDisabled()
    expect(drawerButton(reopened, 'Reddet')).toBeDisabled()
    expect(within(reopened).getByText('Karar verildi')).toBeInTheDocument()
  })

  it('hesaplama hatası ekranda gösterilir, kararlar korunur', async () => {
    await openReview(makeAnalysis(), {
      'POST /api/calculate': () => jsonResponse(INVALID_DECISION_ERROR, 409),
    })

    const dialog = await openRow('BOQ-009')
    const custom = within(dialog).getByLabelText('Katalogdan başka bir kod')
    await userEvent.type(custom, 'YANLIS-KOD')
    await userEvent.click(drawerButton(dialog, 'Onayla'))

    await userEvent.click(screen.getByRole('button', { name: /hesapla/ }))

    expect(
      await screen.findByText('Kullanıcı kararı geçersiz.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/Sunucunun döndürdüğü aday kodlar/)).toBeInTheDocument()
    // Karar kaybolmadı.
    expect(summaryStrip()).toContain('3 onay bekliyor')
    expect(screen.queryByRole('heading', { name: 'Satın alma listesi' })).not.toBeInTheDocument()
  })

  it('onay bekleyen satır varken uyarı KISMİ rapor vaat etmez', async () => {
    await openReview()

    // Düğme "kısmi listeyle" der: liste eksik satır içeriyor. Bu, raporun
    // ağırlık bakımından KISMİ olacağı anlamına gelmez.
    expect(
      screen.getByRole('button', { name: 'Kısmi listeyle hesapla' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/onaysız satır hesaba girmez/),
    ).toBeInTheDocument()
    // Uyarı doğru bölümü işaret eder; KISMİ yalnızca PARTIAL grup içindir.
    expect(screen.getByText(/Hesaba Alınmayanlar/)).toBeInTheDocument()
    expect(
      screen.queryByText(/sonuç .*KISMİ.* işaretlenir/),
    ).not.toBeInTheDocument()
  })

  it('tüm satırlar karara bağlanınca tam liste düğmesi görünür', async () => {
    await openReview()

    for (const boqNo of ['BOQ-003', 'BOQ-004', 'BOQ-006', 'BOQ-009']) {
      const dialog = await openRow(boqNo)
      await userEvent.click(drawerButton(dialog, 'Reddet'))
      await waitFor(() =>
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
      )
    }

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Hesapla ve sonuçlara geç' })).toBeInTheDocument()
    })
  })
})
