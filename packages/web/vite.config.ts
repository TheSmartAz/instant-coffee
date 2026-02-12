import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

const allowedHosts = [
  'web-production-32d6.up.railway.app',
  process.env.RAILWAY_PUBLIC_DOMAIN,
].filter((host): host is string => Boolean(host && host.trim()))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    allowedHosts,
  },
  preview: {
    allowedHosts,
  },
})
