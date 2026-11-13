import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

/**
 * Test yapılandırması — ayrı dosya, üretim derlemesini etkilemez.
 *
 * `jsdom` gerçek tarayıcı DOM'u sağlar; `fetch` testlerde mock'lanır
 * (`src/test/setup.ts`). Kapsam eşikleri bilinçli olarak kapalı: amaç
 * davranışı doğrulamak, yüzde kovalamak değil.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
    restoreMocks: true,
    clearMocks: true,
  },
})
