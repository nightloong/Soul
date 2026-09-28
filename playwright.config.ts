import { defineConfig } from '@playwright/test'

const python = process.platform === 'win32' ? '.\\.venv\\Scripts\\python.exe' : 'python'

export default defineConfig({
  testDir: 'apps/web/e2e',
  timeout: 30_000,
  reporter: 'line',
  use: { baseURL: 'http://127.0.0.1:5173', browserName: 'chromium', channel: process.platform === 'win32' ? 'msedge' : undefined },
  webServer: process.env.PERSONAFORGE_E2E_EXTERNAL ? undefined : [
    { command: `${python} -m uvicorn personaforge.main:app --host 127.0.0.1 --port 8000`, url: 'http://127.0.0.1:8000/api/health', reuseExistingServer: false, timeout: 30_000, env: { PERSONAFORGE_DATABASE_URL: 'sqlite:///data/private/playwright-test.db' } },
    { command: 'npm run preview -- --port 5173', url: 'http://127.0.0.1:5173', reuseExistingServer: true, timeout: 30_000 },
  ],
})
