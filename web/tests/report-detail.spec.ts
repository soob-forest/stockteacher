import { test, expect } from '@playwright/test';

// 참고: API 서버가 기본 seed_reports를 통해 insight_a 레코드를 생성한다고 가정한다.
const KNOWN_INSIGHT_ID = process.env.KNOWN_INSIGHT_ID || 'insight_a';

test.describe('리포트 상세 페이지', () => {
  test('요약/키워드/에이전트 패널이 렌더링된다', async ({ page }) => {
    await page.goto(`/reports/${KNOWN_INSIGHT_ID}`);

    await expect(
      page.getByRole('heading', { name: /TSLA|AAPL|MSFT|NVDA/ })
    ).toBeVisible();

    await expect(page.getByRole('heading', { name: '에이전트 대화' })).toBeVisible();
    await expect(page.getByText('리포트 내용을 바탕으로 후속 질문을 입력하면 에이전트가 답변합니다.')).toBeVisible();
    await expect(page.getByPlaceholder('질문을 입력하세요...')).toBeVisible();
  });
});
