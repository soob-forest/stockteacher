import { test, expect } from '@playwright/test';

test.describe('구독 관리 페이지', () => {
  test('구독 폼과 목록 섹션이 렌더링된다', async ({ page }) => {
    await page.goto('/subscriptions');

    await expect(page.getByRole('heading', { name: '구독 종목 등록' })).toBeVisible();
    await expect(page.getByLabel('종목 티커')).toBeVisible();
    await expect(page.getByPlaceholder('예: AAPL')).toBeVisible();
    await expect(page.getByRole('button', { name: /구독 추가/ })).toBeVisible();

    await expect(page.getByRole('heading', { name: '구독 목록' })).toBeVisible();
    await expect(page.getByText(/활성/)).toBeVisible();
  });
});

