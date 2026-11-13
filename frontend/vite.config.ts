import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Env dosyası proje kökünden okunur; `process` tipi gerekmez.
  const env = loadEnv(mode, '.', 'VITE_')

  // Geliştirme proxy hedefi ortamdan gelir; varsayılan yerel FastAPI.
  const proxyTarget = env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: {
        // Geliştirme sırasında `/api` istekleri FastAPI'ye yönlendirilir.
        // Böylece tarayıcıda CORS sorunu oluşmaz ve `VITE_API_BASE_URL` boş
        // bırakılabilir.
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
