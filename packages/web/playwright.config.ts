import { defineConfig } from 'playwright/test'

export default defineConfig({
  testDir: './src/e2e',
  timeout: 30000,
  use: {
    baseURL: 'http://localhost:4173',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'npm run dev -- --host localhost --port 4173',
    url: 'http://localhost:4173',
    reuseExistingServer: false,
    timeout: 120000,
  },
})
