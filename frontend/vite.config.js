import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In Docker set VITE_PROXY_TARGET=http://backend:8000; locally defaults to localhost:8000
const proxyTarget = process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
})
