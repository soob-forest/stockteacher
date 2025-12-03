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
      command: '.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000',
      cwd: '..',
      url: 'http://127.0.0.1:8000/healthz',
      reuseExistingServer: true,
      env: {
        OPENAI_API_KEY: 'sk-test-123',
        UV_CACHE_DIR: './.uv_cache'
      }
    },
    {
      command: 'npm run dev -- --port 3000',
      cwd: '.',
      url: 'http://localhost:3000',
      reuseExistingServer: true,
      env: {
        NEXT_PUBLIC_API_BASE_URL: 'http://127.0.0.1:8000'
      }
    }
  ]
};

export default config;
