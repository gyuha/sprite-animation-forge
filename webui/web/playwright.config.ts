import { defineConfig, devices } from '@playwright/test'

// Each test starts its own FastAPI server (temp root, fake codex, production build in dist/); see e2e/fixtures.ts.
export default defineConfig({
  testDir: 'e2e',
  globalSetup: './e2e/global-setup.ts',
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: [['list']],
  use: { ...devices['Desktop Chrome'], headless: true, trace: 'retain-on-failure' },
})
