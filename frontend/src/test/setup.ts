import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

/**
 * Test ortamı kurulumu.
 *
 * - Her testten sonra DOM temizlenir.
 * - `fetch` varsayılan olarak **çağrılmaz**: testler kendi yanıtlarını kurar.
 *   Beklenmeyen bir ağ çağrısı testi açıkça düşürür (sessiz sahte başarı yok).
 * - `URL.createObjectURL` jsdom'da yoktur; indirme testleri için taklit edilir.
 */

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

/**
 * `configurable: true` önemli: testler bu iki metodu `vi.spyOn` ile
 * gözlemler. `URL` sınıfının kendisi asla taklit edilmez — `new URL(...)`
 * adres çözümünde kullanıldığı için bozulursa ağ katmanı çalışmaz.
 */
if (!('createObjectURL' in URL)) {
  Object.defineProperty(URL, 'createObjectURL', {
    configurable: true,
    writable: true,
    value: vi.fn(() => 'blob:buildflow-test'),
  })
}

if (!('revokeObjectURL' in URL)) {
  Object.defineProperty(URL, 'revokeObjectURL', {
    configurable: true,
    writable: true,
    value: vi.fn(),
  })
}

/**
 * jsdom gezintiyi uygulamaz; `blob:` bağlantısına tıklamak "Not implemented"
 * uyarısı basar. İndirmede doğrulanan şey bağlantının kurulması ve
 * temizlenmesidir, tarayıcının dosyayı kaydetmesi değil.
 */
const nativeAnchorClick = HTMLAnchorElement.prototype.click
HTMLAnchorElement.prototype.click = function click(this: HTMLAnchorElement) {
  if (this.href.startsWith('blob:')) return
  nativeAnchorClick.call(this)
}
