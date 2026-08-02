import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// Flask, build çıktısını `/static/dist/` altından servis eder; bu yüzden
// ÜRETİM varlık yolları o önekle üretilir. Rota tabanı ise her zaman `/`
// (bkz. src/router) — sayfa adresleri `/` ve `/secrets` olarak kalır.
//
// Geliştirmede `base` `/` olur: aksi halde `npm run dev` uygulamayı
// `/static/dist/` altında servis eder ve `/secrets` rotası 404 verir.
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/static/dist/' : '/',
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
    // Fontlar her zaman ayrı dosya olarak yazılsın (base64 gömme yok).
    assetsInlineLimit: 0,
  },
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      // Geliştirme sırasında API çağrıları Flask'a gider.
      '/api': {
        target: 'http://localhost:5050',
        changeOrigin: true,
      },
      '/static/audio': {
        target: 'http://localhost:5050',
        changeOrigin: true,
      },
    },
  },
}))
