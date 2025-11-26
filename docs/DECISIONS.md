# 아키텍처 의사결정 로그 (Architecture Decision Records)

이 문서는 StockTeacher 프로젝트의 주요 기술적/아키텍처적 결정을 기록합니다. 각 ADR은 컨텍스트, 결정, 근거, 고려된 대안, 영향을 포함합니다.

## ADR 인덱스

- [ADR-001](#adr-001-vector-db-도입---option-c-선택): Vector DB 도입 - Option C 선택
- [ADR-002](#adr-002-데이터-수집-커넥터---newsapi-우선): 데이터 수집 커넥터 - NewsAPI 우선
- [ADR-003](#adr-003-llm-분석-전략---단일-프롬프트): LLM 분석 전략 - 단일 프롬프트
- [ADR-004](#adr-004-웹-기술-스택---nextjs--fastapi): 웹 기술 스택 - Next.js + FastAPI
- [ADR-005](#adr-005-서버-실행-스크립트---bash-래퍼): 서버 실행 스크립트 - Bash 래퍼
- [ADR-006](#adr-006-e2e-테스트---playwright): E2E 테스트 - Playwright

---

## ADR-001: Vector DB 도입 - Option C 선택

**날짜**: 2025-11 (계획 단계)
**상태**: Accepted
**관련 문서**: [ROADMAP.md - Vector DB 통합](./ROADMAP.md#vector-db-통합-)

### 컨텍스트
StockTeacher는 뉴스 요약 파이프라인과 웹/챗 인터페이스를 제공하지만, 사용자의 후속 질문은 단순 규칙 기반 응답만 지원합니다. 관련 리포트 탐색·설명 능력이 떨어져 챗 경험이 제한적이며, 비슷한 이슈 추천 같은 재사용 가치도 낮습니다.

### 결정
**Option C를 채택합니다**: 챗봇/웹에서 질문 임베딩 → Vector 검색 → 답변 생성

API 레이어에서 Vector 검색을 통합하고, 채팅 엔드포인트에서 RAG(Retrieval-Augmented Generation) 컨텍스트를 LLM 응답/템플릿에 주입합니다.

### 근거
- **사용자 즉시 체감**: 대화 품질 개선 효과가 크고, 사용자가 직접 경험 가능
- **API 레이어만 수정**: Celery 분석 파이프라인을 건드리지 않아 리스크 낮음
- **확장 용이**: 구축한 인덱스는 이후 Slack 봇 및 추천 기능에 재활용 가능

### 고려된 대안

#### Option A: 웹 검색 추천 기능
- 장점: 사용자 직접 체감, UI 개선 중심
- 단점: 챗봇 품질 개선 없음, 기능 범위 좁음

#### Option B: 분석 단계에서 RAG로 대체 기사 검색 후 요약 프롬프트 보강
- 장점: 토큰 효율↑, insight 품질 향상
- 단점: Celery 파이프라인 복잡도 증가, 실패 시 재시도 경로 위험

### 영향
- `api/routes.py`: 채팅 엔드포인트에 Vector 검색 호출 추가
- `web/`: 관련 보고서 추천 UI 컴포넌트 추가
- **인프라**: Qdrant/Weaviate 등 Vector DB 추가 필요
- **파이프라인**: materializer 완료 이후 임베딩 생성 및 업서트 단계 추가

### 후속 작업
- [ ] Vector DB 선정 (Qdrant vs Weaviate)
- [ ] ProcessedInsight 임베딩 생성 파이프라인 구현
- [ ] RAG 검색 API 구현
- [ ] 웹 추천 UI 구현
- [ ] Slack 봇 연동 (향후)

---

## ADR-002: 데이터 수집 커넥터 - NewsAPI 우선

**날짜**: 2025-10 (MVP 단계)
**상태**: Accepted
**관련 문서**: [docs/ingestion/data-collection-plan.md](./ingestion/data-collection-plan.md), [docs/ingestion/news-integration-plan.md](./ingestion/news-integration-plan.md)

### 컨텍스트
MVP 데이터 소스를 선택해야 하는 상황에서, NewsAPI, RSS 피드, 웹 스크래핑 등 여러 옵션을 고려했습니다.

### 결정
**NewsAPI 공식 API를 주요 소스로 사용**합니다. RSS 커넥터는 MVP 범위에서 제외하고, 필요 시 향후 재검토합니다.

### 근거
- **안정적 포맷**: JSON 응답, 일관된 스키마
- **빠른 MVP**: 인증/페이징/필터링 기본 제공
- **Rate Limit 관리**: 공식 API 쿼터 명확
- **신뢰성**: 크롤링 대비 차단 위험 낮음

### 고려된 대안

#### Option A: RSS 피드 수집
- 장점: 무료, 다양한 출처
- 단점: 포맷 불일치, 파싱 복잡, 신뢰성 낮음

#### Option B: 웹 스크래핑
- 장점: 원문 전체 수집 가능
- 단점: 법적 리스크, 차단 가능성, 유지보수 부담

### 영향
- `ingestion/connectors/news_api.py`: NewsAPI 커넥터 구현
- `.env.example`: `NEWS_API_KEY`, `NEWS_API_ENDPOINT` 필수
- **비용**: 무료 계층 제한 (일일 100건), 유료 전환 고려 필요

### 위험 및 완화
- **Rate Limit**: 수집 스케줄 간격 조정 (`COLLECTION_SCHEDULES`)
- **유료 전환**: 비용 발생 시 RSS 보조 소스로 전환 검토
- **데이터 품질**: NewsAPI 필터링 옵션 활용 (language, sortBy)

---

## ADR-003: LLM 분석 전략 - 단일 프롬프트

**날짜**: 2025-10 (MVP 단계)
**상태**: Accepted
**관련 문서**: [docs/analysis/analysis-plan.md](./analysis/analysis-plan.md)

### 컨텍스트
LLM을 활용한 기사 분석 시, 요약/키워드/감성/이상징후를 별도 호출로 생성할지, 단일 프롬프트로 통합 생성할지 결정이 필요했습니다.

### 결정
**단일 프롬프트로 모든 분석 항목을 한 번에 생성**합니다. JSON 스키마를 강제하여 구조화된 출력을 받습니다.

### 근거
- **비용/지연 최소화**: LLM 호출 1회로 완료
- **일관성**: 모든 분석이 동일한 컨텍스트 기반
- **단순성**: 파이프라인 로직 간소화

### 고려된 대안

#### Option A: 모듈별 분리 호출
- 장점: 각 분석의 품질 개별 최적화 가능
- 단점: 비용/지연 증가 (4배), 복잡도 상승

#### Option B: 2단계 호출 (요약 → 분석)
- 장점: 품질 향상 가능성
- 단점: 비용 증가, 실패 지점 2배

### 영향
- `analysis/prompts/templates.py`: 통합 프롬프트 템플릿
- `analysis/client/openai_client.py`: JSON 모드 활성화
- **비용**: 요청당 약 $0.01-0.02 (gpt-4o-mini 기준)

### JSON 출력 스키마
```json
{
  "summary_text": "요약 (<=1200 chars)",
  "keywords": ["키워드1", "키워드2"],
  "sentiment_score": 0.5,
  "anomalies": [
    {"label": "이벤트명", "description": "설명", "score": 0.8}
  ]
}
```

### 모니터링
- `analysis.saved` 로그 이벤트로 토큰/비용 추적
- 품질 이슈 발생 시 Option A로 전환 검토

---

## ADR-004: 웹 기술 스택 - Next.js + FastAPI

**날짜**: 2025-11 (웹 MVP 단계)
**상태**: Accepted
**관련 문서**: [docs/web/web-application-plan.md](./web/web-application-plan.md)

### 컨텍스트
Slack 중심 전달 단계를 웹 포털로 전환하면서, 프론트엔드와 백엔드 기술 스택을 결정해야 했습니다.

### 결정
- **프론트엔드**: Next.js 14 (App Router) + TypeScript
- **백엔드**: Python FastAPI + SQLAlchemy

### 근거
- **Next.js**:
  - SSR 지원으로 SEO 최적화
  - App Router로 최신 패턴 활용
  - React 생태계 호환
- **FastAPI**:
  - Python 백엔드와 자연스러운 통합 (ingestion, analysis와 같은 언어)
  - 비동기 지원 (WebSocket/SSE)
  - 자동 OpenAPI 문서 생성

### 고려된 대안

#### Option A: 풀스택 Next.js (API Routes)
- 장점: 단일 코드베이스, 배포 단순
- 단점: Python 파이프라인과 분리, 타입 안전성 낮음

#### Option B: Kotlin + Spring Boot 백엔드
- 장점: 엔터프라이즈급 안정성
- 단점: Python과 언어 분리, 학습 곡선

### 영향
- `web/`: Next.js 프로젝트 (TypeScript)
- `api/`: FastAPI 프로젝트 (Python)
- **배포**: 웹은 Vercel/Static Hosting, API는 Docker + ECS/Fargate
- **개발**: 별도 포트 (3000, 8000) 로컬 개발 환경

### 후속 작업
- [ ] OAuth2/SSO 인증 구현
- [ ] RBAC (일반 사용자/관리자)
- [ ] WebSocket 채팅 통합
- [ ] 프로덕션 배포 파이프라인

---

## ADR-005: 서버 실행 스크립트 - Bash 래퍼

**날짜**: 2025-11
**상태**: Accepted
**관련 문서**: [docs/web/server-scripts-plan.md](./web/server-scripts-plan.md)

### 컨텍스트
개발자가 FastAPI 서버와 Next.js 웹 앱을 매번 수동으로 실행해야 하는 불편함이 있었습니다. 통합 실행 스크립트가 필요했습니다.

### 결정
**Bash 스크립트로 간단한 래퍼를 제공**합니다. PID 파일 기반으로 프로세스를 관리합니다.

### 근거
- **의존성 최소**: bash만 필요, 추가 도구 불필요
- **기존 명령 래핑**: README의 수동 명령을 그대로 사용
- **단순성**: 100줄 이하 스크립트로 구현 가능

### 고려된 대안

#### Option A: Python 관리 스크립트
- 장점: 에러 처리, 로그 출력 정교
- 단점: Python 모듈 경로/venv 복잡도, 설정 오버헤드

#### Option B: Docker Compose 전체 스택
- 장점: 완전한 격리, 재현 가능
- 단점: 로컬 개발 속도 저하, 디버깅 어려움

### 구현
- `scripts/run_servers.sh`: API + Web 서버 백그라운드 실행
- `scripts/stop_servers.sh`: PID 파일 기반 종료
- `var/pids/`: PID 파일 저장 디렉토리

### 영향
- 로컬 개발 편의성 향상
- README "빠른 시작" 섹션 단순화
- CI/CD에서는 별도 명령 사용 (스크립트 미사용)

---

## ADR-006: E2E 테스트 - Playwright

**날짜**: 2025-11
**상태**: Accepted
**관련 문서**: [docs/web/web-e2e-tests-plan.md](./web/web-e2e-tests-plan.md)

### 컨텍스트
웹 애플리케이션의 브라우저 관점 테스트 자동화가 필요했습니다. Playwright, Cypress, Selenium 등을 고려했습니다.

### 결정
**Playwright를 E2E 테스트 프레임워크로 사용**합니다. `web/tests/` 디렉토리에 테스트 구성, 이미 실행 중인 dev 서버에 연결하는 방식(Option A)을 채택합니다.

### 근거
- **Next.js 통합**: Next.js 프로젝트 구조와 자연스러움
- **멀티 브라우저**: Chromium, Firefox, WebKit 지원
- **현대적 API**: async/await, 강력한 선택자
- **빠른 실행**: 병렬 실행, 효율적인 대기 메커니즘

### 고려된 대안

#### Option A: 이미 실행 중인 서버 연결 (선택)
- 장점: 빠른 실행, 단순한 설정
- 단점: 개발자가 서버를 먼저 올려야 함

#### Option B: webServer 옵션으로 서버 자동 기동
- 장점: self-contained 실행
- 단점: 기동 시간 증가, 포트 충돌 가능성

#### Option C: Cypress
- 장점: 풍부한 생태계, 디버깅 UI 우수
- 단점: 브라우저 지원 제한, Next.js 통합 복잡

### 구현
- `web/package.json`: `@playwright/test` devDependency
- `web/playwright.config.ts`: baseURL `http://localhost:3000`
- `web/tests/*.spec.ts`: 페이지별 E2E 테스트

### 테스트 범위
- 루트(`/`) → 구독 페이지 리다이렉트
- 구독 관리 (`/subscriptions`)
- 리포트 목록 (`/reports`)
- 즐겨찾기 (`/reports/favorites`)
- 리포트 상세 + 채팅 (`/reports/:id`)

### 실행 명령
```bash
# 사전 조건: API + Web 서버 실행
./scripts/run_servers.sh

# E2E 테스트 실행
cd web && npm run test:e2e
```

---

## 의사결정 프로세스

새로운 아키텍처 결정이 필요한 경우:
1. 배경 및 문제 정의
2. 최소 2가지 대안 비교 (장점/단점/위험)
3. 가장 단순한 해법 선택 (CLAUDE.md 원칙)
4. 이 문서에 ADR-XXX 추가
5. 관련 모듈 README에서 링크

## 관련 문서

- [아키텍처 개요](./ARCHITECTURE.md)
- [운영 가이드](./OPERATIONS.md)
- [테스트 전략](./TESTING.md)
- [로드맵](./ROADMAP.md)
