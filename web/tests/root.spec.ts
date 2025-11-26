import { test, expect } from '@playwright/test';

test.describe('루트 페이지', () => {
  test('Index에서 구독 페이지로 리다이렉트된다', async ({ page }) => {
    await page.goto('/');
    await page.waitForURL('**/subscriptions');

    await expect(page.getByRole('heading', { name: '구독 종목 등록' })).toBeVisible();
    await expect(page.getByRole('link', { name: '구독 관리' })).toBeVisible();
    await expect(page.getByRole('link', { name: '리포트' })).toBeVisible();
  });
});

