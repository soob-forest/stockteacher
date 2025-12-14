import { test, expect } from '@playwright/test';

/**
 * E2E 테스트: 벡터 검색 페이지
 *
 * 테스트 시나리오:
 * - TC-1: 기본 검색
 * - TC-2: 티커 필터
 * - TC-3: 날짜 범위 필터
 * - TC-4: 감성 필터
 * - TC-5: 빈 결과
 */

test.describe('벡터 검색 페이지', () => {
  test('TC-1: 기본 검색', async ({ page }) => {
    await page.goto('/search');

    // 페이지 제목 확인
    await expect(page.locator('h2')).toHaveText('벡터 검색 (실험)');

    // 안내 문구 확인
    await expect(page.locator('.label')).toContainText('벡터 유사도 기반');

    // 자연어 질의 입력
    await page.fill('input[placeholder*="자연어 질의"]', '배터리 기술');

    // 검색 버튼 클릭
    await page.click('button:has-text("검색")');

    // 로딩 상태 확인
    await expect(page.locator('button:has-text("검색 중...")')).toBeVisible();

    // 결과 표시 대기 (최대 10초)
    await expect(page.locator('.list-item').first()).toBeVisible({ timeout: 10000 });

    // 순위 배지 확인
    await expect(page.locator('.badge:has-text("1위")')).toBeVisible();
  });

  test('TC-2: 티커 필터', async ({ page }) => {
    await page.goto('/search');

    // 질의 및 티커 입력
    await page.fill('input[placeholder*="자연어"]', '전기차');
    await page.fill('input[placeholder*="티커"]', 'TSLA');

    // 검색
    await page.click('button:has-text("검색")');

    // 결과 대기
    await expect(page.locator('.list-item').first()).toBeVisible({ timeout: 10000 });

    // 모든 결과의 티커가 TSLA인지 확인
    const items = await page.locator('.list-item').all();
    for (const item of items) {
      const ticker = await item.locator('span').first().textContent();
      expect(ticker).toContain('TSLA');
    }
  });

  test('TC-3: 날짜 범위 필터', async ({ page }) => {
    await page.goto('/search');

    // 오늘 날짜 계산
    const today = new Date().toISOString().split('T')[0];
    const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)
      .toISOString()
      .split('T')[0];

    // 질의 및 날짜 범위 입력
    await page.fill('input[placeholder*="자연어"]', '기술');
    await page.fill('input[type="date"]').first().fill(sevenDaysAgo);
    await page.fill('input[type="date"]').last().fill(today);

    // 검색
    await page.click('button:has-text("검색")');

    // 결과가 있거나 빈 상태 메시지 표시
    const hasResults = await page.locator('.list-item').first().isVisible({ timeout: 10000 }).catch(() => false);
    const hasEmptyState = await page.locator('.empty-state').isVisible();

    expect(hasResults || hasEmptyState).toBeTruthy();
  });

  test('TC-4: 감성 필터', async ({ page }) => {
    await page.goto('/search');

    // 질의 및 감성 선택
    await page.fill('input[placeholder*="자연어"]', '뉴스');
    await page.selectOption('select', 'positive');

    // 검색
    await page.click('button:has-text("검색")');

    // 결과 대기
    const hasResults = await page.locator('.list-item').first().isVisible({ timeout: 10000 }).catch(() => false);

    if (hasResults) {
      // 긍정 배지 확인
      const sentimentBadges = await page.locator('.badge:has-text("긍정")').all();
      expect(sentimentBadges.length).toBeGreaterThan(0);
    } else {
      // 빈 상태 확인
      await expect(page.locator('.empty-state')).toBeVisible();
    }
  });

  test('TC-5: 빈 결과', async ({ page }) => {
    await page.goto('/search');

    // 존재하지 않는 검색어 입력
    await page.fill('input[placeholder*="자연어"]', 'asdfqwer1234zzzzz불가능한검색어');

    // 검색
    await page.click('button:has-text("검색")');

    // 빈 상태 메시지 확인
    await expect(page.locator('.empty-state')).toHaveText('검색 결과가 없습니다.', { timeout: 10000 });
  });

  test('TC-6: 초기 상태 - 검색어 없이 진입', async ({ page }) => {
    await page.goto('/search');

    // 검색 버튼이 비활성화되어 있어야 함
    await expect(page.locator('button:has-text("검색")')).toBeDisabled();

    // 빈 상태 메시지
    await expect(page.locator('.empty-state')).toHaveText('검색어를 입력하세요.');
  });

  test('TC-7: 결과 항목 클릭', async ({ page }) => {
    await page.goto('/search');

    // 검색
    await page.fill('input[placeholder*="자연어"]', '기술');
    await page.click('button:has-text("검색")');

    // 결과 대기
    await expect(page.locator('.list-item').first()).toBeVisible({ timeout: 10000 });

    // 첫 번째 결과의 "열기" 버튼 클릭
    await page.locator('.button.secondary').first().click();

    // 리포트 상세 페이지로 이동 확인
    await expect(page).toHaveURL(/\/reports\/[a-zA-Z0-9-]+/);
  });

  test('TC-8: 여러 필터 조합', async ({ page }) => {
    await page.goto('/search');

    // 모든 필터 입력
    await page.fill('input[placeholder*="자연어"]', '배터리');
    await page.fill('input[placeholder*="티커"]', 'AAPL, TSLA');
    await page.fill('input[placeholder*="키워드"]', 'battery, tech');
    await page.selectOption('select', 'positive');

    // 검색
    await page.click('button:has-text("검색")');

    // 결과 또는 빈 상태 확인
    const hasResults = await page.locator('.list-item').first().isVisible({ timeout: 10000 }).catch(() => false);
    const hasEmptyState = await page.locator('.empty-state').isVisible();

    expect(hasResults || hasEmptyState).toBeTruthy();
  });
});
