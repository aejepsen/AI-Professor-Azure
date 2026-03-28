// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir:    './frontend/tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env['CI'],
  retries:    process.env['CI'] ? 2 : 0,
  workers:    process.env['CI'] ? 1 : undefined,
  reporter:   [['html', { outputFolder: 'playwright-report' }], ['list']],
  use: {
    baseURL:      process.env['BASE_URL'] || 'http://localhost:4200',
    trace:        'on-first-retry',
    screenshot:   'only-on-failure',
    video:        'retain-on-failure',
    locale:       'pt-BR',
    timezoneId:   'America/Sao_Paulo',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'Mobile Chrome', use: { ...devices['Pixel 5'] } },
  ],
  webServer: process.env['CI'] ? undefined : {
    command: 'ng serve --configuration development',
    url:     'http://localhost:4200',
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
