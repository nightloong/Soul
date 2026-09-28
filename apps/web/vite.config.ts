import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  root: 'apps/web',
  plugins: [react()],
  optimizeDeps: { noDiscovery: true, include: [] },
  build: { outDir: '../../dist', emptyOutDir: true },
  server: {
    host: '127.0.0.1',
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  preview: {
    host: '127.0.0.1',
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
