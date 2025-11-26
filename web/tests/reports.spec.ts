import { test, expect } from '@playwright/test';

test.describe('리포트 목록 페이지', () => {
  test('필터와 빈 상태/리스트 컨테이너가 렌더링된다', async ({ page }) => {
    await page.goto('/reports');

    await expect(page.getByRole('heading', { name: '리포트 필터' })).toBeVisible();
    await expect(page.getByRole('heading', { name: '리포트 목록' })).toBeVisible();

    await expect(page.getByLabel('날짜')).toBeVisible();
    await expect(page.getByLabel('감성')).toBeVisible();
    await expect(page.getByLabel('검색')).toBeVisible();
  });
});

