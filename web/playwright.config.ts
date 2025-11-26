import type { PlaywrightTestConfig } from '@playwright/test';

const config: PlaywrightTestConfig = {
  testDir: 'tests',
  use: {
    baseURL: process.env.WEB_BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry'
  },
  timeout: 30000,
  webServer: [
    {
      command: 'uv run -- uvicorn api.main:app --reload --port 8000',
      cwd: '..',
      url: 'http://127.0.0.1:8000/healthz',
      reuseExistingServer: true
    },
    {
      command: 'npm run dev -- --port 3000',
      cwd: '.',
      url: 'http://localhost:3000',
      reuseExistingServer: true
    }
  ]
};

export default config;
