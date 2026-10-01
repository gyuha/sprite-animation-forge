import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// changeOrigin: the API's Host guard only accepts 127.0.0.1/localhost, so the proxy rewrites Host to the target
const API = { target: 'http://127.0.0.1:8765', changeOrigin: true }

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
  server: { proxy: { '/api': API, '/files': API } },
  test: { include: ['src/**/*.test.{ts,tsx}'], environment: 'jsdom', setupFiles: ['./src/test-setup.ts'], globals: false },
})
