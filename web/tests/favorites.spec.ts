import { test, expect } from '@playwright/test';

test.describe('즐겨찾는 리포트 페이지', () => {
  test('즐겨찾기 전용 보드가 렌더링된다', async ({ page }) => {
    await page.goto('/reports/favorites');

    await expect(page.getByRole('heading', { name: '리포트 필터' })).toBeVisible();
    await expect(page.getByRole('heading', { name: '즐겨찾는 리포트' })).toBeVisible();
  });
});

