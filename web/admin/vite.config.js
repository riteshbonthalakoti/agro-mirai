import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const BACKEND = process.env.BACKEND_URL || 'https://agro-mirai.onrender.com'

export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    proxy: {
      '/admin': { target: BACKEND, changeOrigin: true, secure: true },
      '/v2': { target: BACKEND, changeOrigin: true, secure: true },
      '/health': { target: BACKEND, changeOrigin: true, secure: true },
    },
  },
})
