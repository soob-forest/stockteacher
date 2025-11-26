# StockTeacher 테스트 전략

이 문서는 StockTeacher 프로젝트의 테스트 철학, 전략, 실행 방법을 정의합니다.

## 테스트 철학

### 핵심 원칙 (CLAUDE.md 기반)

1. **새 코드에는 새 테스트 추가**: 모든 새 기능에는 테스트가 동반되어야 합니다.
2. **버그 수정에는 회귀 테스트 필수**: 버그 수정 시 먼저 실패하는 테스트를 작성한 후 수정합니다.
3. **결정적 테스트**: 테스트는 항상 동일한 결과를 반환해야 합니다 (시간/랜덤 의존 금지).
4. **독립적 테스트**: 각 테스트는 다른 테스트에 의존하지 않고 독립적으로 실행 가능해야 합니다.
5. **외부 시스템 격리**: 외부 API/DB는 가짜(Fake) 또는 계약(Contract) 테스트로 대체합니다.

### 테스트 피라미드

```
        /\
       /  \
      / E2E \          적음 (느림, 비용 높음)
     /--------\
    /  통합    \       중간 (느림, 의존성 있음)
   /------------\
  /   단위 테스트 \    많음 (빠름, 독립적)
 /----------------\
```

---

## 테스트 레벨

### 단위 테스트 (Unit Tests)
- **목적**: 개별 함수/클래스의 동작 검증
- **특징**: 빠름 (밀리초), 외부 의존성 없음
- **도구**: pytest
- **위치**: `tests/{module}/test_*.py`

### 통합 테스트 (Integration Tests)
- **목적**: 여러 모듈/계층 간 상호작용 검증
- **특징**: 느림 (초 단위), 외부 의존성 있음 (DB, Redis)
- **도구**: pytest + fixtures
- **위치**: `tests/{module}/test_*_integration.py`

### E2E 테스트 (End-to-End Tests)
- **목적**: 사용자 관점의 전체 시나리오 검증
- **특징**: 매우 느림 (분 단위), 전체 스택 필요
- **도구**: Playwright (웹)
- **위치**: `web/tests/*.spec.ts`

---

## Ingestion 테스트

### 테스트 전략

#### 단위 테스트
- **커넥터**: 정상/RateLimit/오류 응답 시나리오
- **Normalizer**: 텍스트 정규화, fingerprint 생성
- **Deduplicator**: Redis/InMemory 키스토어 동작

#### 통합 테스트
- **End-to-End 수집**: Fake 커넥터 + In-memory Redis로 전체 흐름 검증
- **DB 마이그레이션**: Alembic 마이그레이션 스모크 테스트
- **JobRun 추적**: 성공/실패 시나리오별 JobRun 기록 검증

### 핵심 테스트 파일

#### tests/ingestion/test_collect_task.py
```python
def test_collect_core_saves_unique_articles(fake_connector):
    """collect_core가 고유 기사만 저장하는지 검증."""
    # Given: Fake 커넥터가 3개 기사 반환
    # When: collect_core 실행
    # Then: 3개 모두 저장, JobRun SUCCESS 기록

def test_collect_core_handles_duplicate(fake_connector):
    """중복 기사 처리 검증."""
    # Given: 동일 fingerprint 기사 2회 수집
    # When: collect_core 2회 실행
    # Then: 1개만 저장, 2번째는 중복으로 무시

def test_collect_core_records_failure(fake_connector):
    """수집 실패 시 JobRun 기록 검증."""
    # Given: 커넥터가 예외 발생
    # When: collect_core 실행
    # Then: JobRun FAILED 기록, 예외 메시지 포함
```

#### tests/ingestion/test_settings.py
```python
def test_settings_validates_collection_schedules():
    """스케줄 JSON 검증."""
    # 중복 ticker/source 조합 차단
    # interval_minutes 범위 검증 (> 0)
```

#### tests/ingestion/test_deduplicator.py
```python
def test_redis_keystore_nx_set():
    """Redis NX set 동작 검증."""
    # 첫 번째: True (신규)
    # 두 번째: False (중복)

def test_fallback_to_memory():
    """Redis 실패 시 메모리 폴백 검증."""
```

### 실행 방법
```bash
# 전체 Ingestion 테스트
uv run -- python -m pytest tests/ingestion/

# 특정 테스트 파일
uv run -- python -m pytest tests/ingestion/test_collect_task.py

# 커버리지 포함
uv run -- python -m pytest tests/ingestion/ --cov=ingestion --cov-report=term-missing
```

---

## Analysis 테스트

### 테스트 전략

#### 단위 테스트
- **OpenAI 클라이언트**: Fake Provider로 성공/실패 시나리오
- **프롬프트 빌더**: 입력 → 메시지 변환 검증
- **비용 추정**: 토큰 → USD 변환 정확성

#### 통합 테스트
- **End-to-End 분석**: Fake Provider + 실제 DB로 전체 흐름
- **재시도 로직**: TransientLLMError 발생 시 최대 3회 재시도
- **비용 상한**: PermanentLLMError 발생 시 재시도 없음

### 핵심 테스트 파일

#### tests/analysis/test_analyze_task.py
```python
def test_analyze_core_success(fake_provider):
    """분석 성공 시나리오."""
    # Given: raw_articles 5건, Fake Provider 정상 응답
    # When: analyze_core 실행
    # Then: ProcessedInsight 저장, JobRun SUCCESS

def test_analyze_core_no_articles():
    """기사 없을 때 처리."""
    # Given: raw_articles 0건
    # When: analyze_core 실행
    # Then: analyze.no_articles 로그, JobRun SKIPPED

def test_analyze_core_handles_transient_error(fake_provider):
    """일시 오류 재시도 검증."""
    # Given: Fake Provider가 TransientLLMError 2회 발생 후 성공
    # When: analyze_core 실행
    # Then: 최대 3회 재시도, 최종 성공

def test_analyze_core_handles_cost_limit(fake_provider):
    """비용 상한 초과 검증."""
    # Given: Fake Provider가 비용 $0.03 반환 (상한 $0.02)
    # When: analyze_core 실행
    # Then: PermanentLLMError 발생, JobRun FAILED, 재시도 없음
```

#### tests/analysis/test_openai_client.py
```python
def test_openai_client_parses_json(fake_provider):
    """JSON 파싱 검증."""
    # Given: Fake Provider가 구조화 JSON 반환
    # When: analyze() 호출
    # Then: AnalysisResult 객체 생성

def test_openai_client_estimates_cost():
    """비용 추정 검증."""
    # Given: prompt_tokens=100, completion_tokens=50
    # When: _estimate_cost_usd() 호출
    # Then: 정확한 USD 반환 (gpt-4o-mini 가격)
```

### Fake Provider 구현
```python
# tests/analysis/conftest.py
@pytest.fixture
def fake_provider():
    def _provider(payload):
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "summary_text": "Test summary",
                        "keywords": ["test"],
                        "sentiment_score": 0.5,
                        "anomalies": []
                    })
                }
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50
            }
        }
    return _provider
```

### 실행 방법
```bash
# 전체 Analysis 테스트
uv run -- python -m pytest tests/analysis/

# 특정 테스트
uv run -- python -m pytest tests/analysis/test_analyze_task.py::test_analyze_core_success -v
```

---

## Publish 테스트

### 테스트 전략

#### 단위 테스트
- **Materializer**: ProcessedInsight → ReportSnapshot 변환
- **Idempotency**: 중복 게시 방지 검증

#### 통합 테스트
- **End-to-End 게시**: ProcessedInsight 생성 → Materializer → API 조회

### 핵심 테스트 파일

#### tests/publish/test_materializer.py
```python
def test_materialize_reports_creates_snapshot():
    """ReportSnapshot 생성 검증."""
    # Given: ProcessedInsight 1건
    # When: materialize_reports() 실행
    # Then: ReportSnapshot 저장, JobRun SUCCESS

def test_materialize_reports_idempotent():
    """중복 게시 방지 검증."""
    # Given: 동일 ProcessedInsight
    # When: materialize_reports() 2회 실행
    # Then: 1번만 저장, 2번째는 건너뜀

def test_materialize_reports_records_failure():
    """게시 실패 시 JobRun 기록."""
    # Given: DB 연결 실패
    # When: materialize_reports() 실행
    # Then: JobRun FAILED
```

---

## API 테스트

### 테스트 전략

#### 단위 테스트
- **Repository 함수**: CRUD 로직 검증
- **Pydantic 모델**: 직렬화/역직렬화

#### 통합 테스트
- **FastAPI 엔드포인트**: TestClient로 REST API 검증
- **DB 연동**: 실제 DB (테스트용 SQLite)

### 핵심 테스트 파일

#### tests/api/test_reports_api.py
```python
def test_list_reports(client):
    """리포트 목록 조회 검증."""
    # Given: ReportSnapshot 3건
    # When: GET /api/reports
    # Then: 200 OK, 3건 반환

def test_get_report_detail(client):
    """리포트 상세 조회 검증."""
    # Given: ReportSnapshot 1건
    # When: GET /api/reports/:id
    # Then: 200 OK, 상세 정보 반환

def test_get_report_not_found(client):
    """리포트 없을 때 404 검증."""
    # When: GET /api/reports/invalid-id
    # Then: 404 Not Found
```

#### tests/api/test_chat_api.py
```python
def test_create_chat_session(client):
    """채팅 세션 생성 검증."""
    # Given: ReportSnapshot 1건
    # When: POST /api/chat/sessions
    # Then: 201 Created, session_id 반환

def test_post_chat_message(client):
    """메시지 전송 검증."""
    # Given: ChatSession 1건
    # When: POST /api/chat/sessions/:id/messages
    # Then: 201 Created, 사용자 메시지 + 에이전트 응답 반환

def test_list_chat_messages(client):
    """메시지 목록 조회 검증."""
    # Given: ChatMessage 5건
    # When: GET /api/chat/sessions/:id/messages
    # Then: 200 OK, 5건 반환 (시간 순)
```

### Fixtures
```python
# tests/api/conftest.py
@pytest.fixture
def client():
    """FastAPI TestClient."""
    from api.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)

@pytest.fixture
def test_db():
    """테스트용 SQLite DB."""
    # 임시 DB 생성
    # 마이그레이션 적용
    # 테스트 후 삭제
```

### 실행 방법
```bash
# 전체 API 테스트
uv run -- python -m pytest tests/api/

# 통합 테스트만
uv run -- python -m pytest tests/api/ -m integration
```

---

## Web E2E 테스트 (Playwright)

### 테스트 전략

#### 범위
- 루트 (`/`) → 구독 페이지 리다이렉트 검증
- 구독 관리 (`/subscriptions`): 기본 렌더링, 폼 요소 존재
- 리포트 목록 (`/reports`): 필터, 리스트 렌더링
- 즐겨찾기 (`/reports/favorites`): 즐겨찾기 토글
- 리포트 상세 (`/reports/:id`): 상세 정보, 채팅 UI

#### 전제 조건
- API 서버 (FastAPI) 실행 중 (`http://localhost:8000`)
- Web 서버 (Next.js) 실행 중 (`http://localhost:3000`)
- 더미 데이터 존재 (테스트용 ReportSnapshot)

### 핵심 테스트 파일

#### web/tests/navigation.spec.ts
```typescript
import { test, expect } from '@playwright/test';

test('루트에서 구독 페이지로 리다이렉트', async ({ page }) => {
  await page.goto('http://localhost:3000/');
  await expect(page).toHaveURL('http://localhost:3000/subscriptions');
});

test('구독 관리 페이지 렌더링', async ({ page }) => {
  await page.goto('http://localhost:3000/subscriptions');
  await expect(page.locator('h1:has-text("구독 관리")')).toBeVisible();
});
```

#### web/tests/reports.spec.ts
```typescript
test('리포트 목록 렌더링', async ({ page }) => {
  await page.goto('http://localhost:3000/reports');
  await expect(page.locator('h1:has-text("리포트")')).toBeVisible();

  // 최소 1개 리포트 카드 존재
  const cards = page.locator('.report-card');
  await expect(cards).not.toHaveCount(0);
});

test('리포트 필터링', async ({ page }) => {
  await page.goto('http://localhost:3000/reports');

  // 감성 필터 선택
  await page.selectOption('select[name="sentiment"]', 'positive');

  // 필터링된 결과 확인
  // (실제 필터 로직 구현 필요)
});
```

#### web/tests/report-detail.spec.ts
```typescript
test('리포트 상세 + 채팅 UI', async ({ page }) => {
  // Given: 더미 ReportSnapshot (insight-123)
  await page.goto('http://localhost:3000/reports/insight-123');

  // 상세 정보 렌더링 확인
  await expect(page.locator('.report-summary')).toBeVisible();
  await expect(page.locator('.sentiment-score')).toBeVisible();

  // 채팅 패널 확인
  await expect(page.locator('.chat-panel')).toBeVisible();
  await expect(page.locator('textarea[name="message"]')).toBeVisible();
});
```

### Playwright 설정

#### web/playwright.config.ts
```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30000,
  use: {
    baseURL: 'http://localhost:3000',
    headless: true,
  },
  webServer: undefined,  // 서버 이미 실행 중 전제
});
```

### 실행 방법
```bash
# 사전 조건: API + Web 서버 실행
./scripts/run_servers.sh

# E2E 테스트 실행
cd web
npx playwright test

# 특정 테스트 파일
npx playwright test tests/navigation.spec.ts

# UI 모드 (디버깅)
npx playwright test --ui
```

---

## 테스트 실행 방법

### 전체 테스트 스위트
```bash
# Python 테스트 전체
uv run -- python -m pytest

# Web E2E 테스트
cd web && npx playwright test
```

### 모듈별 테스트
```bash
# Ingestion
uv run -- python -m pytest tests/ingestion/

# Analysis
uv run -- python -m pytest tests/analysis/

# Publish
uv run -- python -m pytest tests/publish/

# API
uv run -- python -m pytest tests/api/
```

### 마커 기반 실행
```bash
# 통합 테스트만
uv run -- python -m pytest -m integration

# 빠른 테스트만 (단위 테스트)
uv run -- python -m pytest -m "not integration and not slow"
```

### 커버리지 리포트
```bash
# 전체 커버리지
uv run -- python -m pytest --cov=ingestion --cov=analysis --cov=api --cov=publish --cov-report=term-missing

# HTML 리포트
uv run -- python -m pytest --cov=ingestion --cov-report=html
open htmlcov/index.html
```

---

## 커버리지 목표

| 모듈 | 목표 | 현재 (예시) |
|-----|------|------------|
| Ingestion | >80% | 85% |
| Analysis | >80% | 90% |
| Publish | >75% | 80% |
| API | >70% | 75% |
| 전체 | >75% | 82% |

### 커버리지 제외
- `__init__.py` 파일
- 마이그레이션 스크립트 (`ingestion/db/migrations/`)
- 설정 파일 (`settings.py` 일부)
- 테스트 유틸리티 (`tests/conftest.py`)

---

## CI/CD 통합

### GitHub Actions 예시
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: stockteacher
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync --extra test

      - name: Run tests
        env:
          INGESTION_REDIS_URL: redis://localhost:6379/0
          POSTGRES_DSN: postgresql+psycopg://postgres:postgres@localhost:5432/stockteacher
        run: |
          uv run -- python -m pytest --cov --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

---

## 모범 사례

### 테스트 작성 원칙
1. **Given-When-Then 패턴**: 명확한 3단 구조
2. **한 테스트당 한 가지 검증**: 단일 책임 원칙
3. **의미 있는 테스트 이름**: `test_analyze_core_handles_cost_limit`
4. **Fixture 재사용**: 공통 설정은 `conftest.py`
5. **외부 의존성 격리**: Fake/Mock 사용

### 테스트하지 않아도 되는 것
- 외부 라이브러리 (pytest, SQLAlchemy 등)
- 간단한 getter/setter
- 프레임워크 기본 동작 (FastAPI 라우팅)

### 테스트 반드시 해야 하는 것
- 비즈니스 로직 (collect_core, analyze_core)
- 외부 API 연동 (커넥터, OpenAI 클라이언트)
- 에러 처리 (재시도, 비용 상한)
- 데이터 변환 (normalizer, materializer)

---

## 관련 문서

- [아키텍처 개요](./ARCHITECTURE.md)
- [운영 가이드](./OPERATIONS.md)
- [모듈별 README](./README.md)
- [Web E2E 테스트 계획](./web/web-e2e-tests-plan.md)
- [CLAUDE.md 코딩 규칙](../CLAUDE.md)
