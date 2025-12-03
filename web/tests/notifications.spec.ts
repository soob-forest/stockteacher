import { test, expect } from '@playwright/test';

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.API_BASE_URL ||
  'http://127.0.0.1:8000';

test.describe('알림 정책 설정', () => {
  test('시간대/채널/quiet hours 저장이 가능하다', async ({ page, request }) => {
    await request.put(`${API_BASE}/api/notifications/policy`, {
      data: {
        timezone: 'Asia/Seoul',
        window: 'daily_close',
        frequency: 'daily',
        channels: ['email'],
        quiet_hours_start: null,
        quiet_hours_end: null
      }
    });

    await page.goto('/subscriptions');

    await expect(page.getByRole('heading', { name: '알림 정책' })).toBeVisible();
    await expect(page.getByTestId('notification-timezone')).toHaveValue('Asia/Seoul');

    await page.getByTestId('notification-timezone').selectOption('America/New_York');
    await page.getByTestId('notification-window').selectOption('morning_open');
    await page.getByTestId('notification-frequency').selectOption('weekly');
    await page.getByTestId('notification-channel-web-push').check();
    await page.getByTestId('quiet-hours-toggle').check();
    await page.getByTestId('quiet-start').fill('09:00');
    await page.getByTestId('quiet-end').fill('18:00');

    await page.getByRole('button', { name: '알림 정책 저장' }).click();
    await expect(page.getByText('알림 정책을 저장했습니다.')).toBeVisible();
  });
});
