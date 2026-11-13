import { fireEvent, render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactElement } from 'react'

import { AppRouter } from '../app/router'
import { WorkflowProvider } from '../state/WorkflowContext'

/**
 * Uygulamayı gerçek yönlendirme ve gerçek durum katmanıyla render eder.
 *
 * Sahte durum kurulmaz: testler `analyze`/`calculate` akışını gerçekten
 * çalıştırır. Böylece "ekran doğru veriyi mi gösteriyor" sorusu, "state
 * elimde doğru duruyor mu" sorusundan ayrılmaz.
 */
export function renderApp(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <WorkflowProvider>
        <AppRouter />
      </WorkflowProvider>
    </MemoryRouter>,
  )
}

/** Render edilmiş bir bileşen ağacı için aynı sağlayıcılar. */
export function renderWithProviders(element: ReactElement, initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <WorkflowProvider>{element}</WorkflowProvider>
    </MemoryRouter>,
  )
}

/**
 * Dosya seçimi.
 *
 * `user-event`'in `accept` filtresi bilinçli olarak atlanır: geçersiz uzantı
 * senaryosu da gerçek istemci davranışını (yerel hata) doğrulamalıdır.
 */
export function chooseFile(input: HTMLInputElement, file: File) {
  fireEvent.change(input, { target: { files: [file] } })
}

/** Testlerde kullanılan `.xlsx` MIME tipi — backend ile aynı. */
export const XLSX_MEDIA_TYPE =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

/** Analiz için sahte ama gerçekçi bir dosya. */
export function metrajFile(name = 'metraj.xlsx', size = 2048): File {
  return new File([new Uint8Array(size)], name, { type: XLSX_MEDIA_TYPE })
}
