# 뉴스/RSS 실데이터 수집 통합 계획 (다음 세션 TODO)

## 작업 진행 상황 요약
- 완료:
  - httpx/pytest-httpx 의존성 추가, Settings 확장(NEWS_API_*), .env.example 반영
  - NewsAPI HTTP 경로 구현 + 단위 테스트(성공/페이지네이션/429)
  - 스모크 스크립트(scripts/test_news_api.py) 추가 및 README 사용법 반영
- 진행 중:
  - 추가 테스트 커버리지(5xx/언어필터), Runbook 실모드 확장
- 대기:
  - HTTP 유틸(timeout/retry 래퍼)
  - RSS 커넥터 HTTP 경로 구현(옵션, feedparser 추가)
  - 계약 테스트(샘플 응답 기반 정규화 검증)

## Problem 1-Pager
- 배경: 수집/분석 파이프라인의 스켈레톤과 테스트가 완료됨. 이제 실제 뉴스 소스(NewsAPI, RSS)를 연결해 실데이터 기반 스모크/E2E 검증이 필요.
- 문제: 현재 커넥터는 provider 주입형(오프라인)만 존재. 실제 HTTP 호출, 페이지네이션, 레이트 리밋/오류 처리, 언어/필터 지원이 없다.
- 목표: NewsAPI.org(또는 동급 API)와 RSS를 실제 호출할 수 있는 커넥터 구현 + 설정/문서/테스트(모킹) 정비. 로컬/스테이징에서 키만 설정하면 스모크 가능하도록 만든다.
- 비목표: 유료 상용화 최적화(대규모 커버리지/비용 최적화), 복잡한 중복 방지 전략(현행 Redis+DB로 충분), 다수 공급자 멀티링크 로드밸런싱.
- 제약: 파일 ≤ 300 LOC, 함수 ≤ 50 LOC, 파라미터 ≤ 5, 순환 복잡도 ≤ 10. 외부 I/O는 유틸/커넥터 경계층으로 격리. 키/비밀은 .env로만 관리.

## 산출물(범위)
- 실제 NewsAPI 커넥터(HTTP 경로) + 모킹 테스트
- RSS 커넥터(HTTP+파서) + 모킹 테스트(옵션)
- 설정 확장(.env.example/README/Runbook): 엔드포인트/타임아웃/재시도/언어/페이지 사이즈
- 간단 스모크 스크립트/명령 예시(로컬 키 주입 시 동작)

## 대안 비교
- HTTP 클라이언트
  - Option A: httpx — 장점: 타임아웃/비동기/테스트 생태계(pytest-httpx), 단점: 추가 의존성; 위험: 설정 미스 시 타임아웃.
  - Option B: requests — 장점: 친숙; 단점: 타임아웃/재시도 수동 구현; 위험: 동시성/백오프 직접 관리 필요.
  - 선택: Option A(httpx).
- RSS 파서
  - Option A: feedparser — 장점: 안정, 다양한 RSS 지원; 단점: 의존성 추가.
  - Option B: 경량 파싱(BeautifulSoup/정규식) — 장점: 의존성 최소; 단점: 포맷 취약/유지보수 부담.
  - 선택: Option A(feedparser).
- 테스트 모킹
  - Option A: pytest-httpx — 장점: httpx와 자연스러운 통합; 단점: 사용법 학습.
  - Option B: responses — 장점: requests 친화; 단점: httpx 지원 제한.
  - 선택: Option A(pytest-httpx).

## 환경 변수 설계(초안)
- NEWS_API_ENDPOINT (기본: https://newsapi.org/v2/everything)
- NEWS_API_KEY (필수)
- NEWS_API_TIMEOUT_SECONDS (기본: 5)
- NEWS_API_MAX_RETRIES (기본: 2)
- NEWS_API_PAGE_SIZE (기본: 20, 최대 100)
- NEWS_API_LANG (기본: ko, 옵션: en 등)
- NEWS_API_SORT_BY (기본: publishedAt)

## 설계 개요
- 커넥터: `ingestion/connectors/news_api.py`
  - provider가 주입되지 않은 경우 → httpx로 호출
  - 쿼리: q=<TICKER>, language, pageSize, sortBy, page(1..N)
  - 응답 상태
    - 200: articles 리스트 정규화 → RawArticleDTO
    - 429/5xx: TransientError(백오프 후 재시도)
    - 4xx(기타): PermanentError
  - 페이지네이션: 최대 1~2페이지(설정값)로 제한, 누적 건수 caps
  - 정규화 매핑: title, description/body, url, publishedAt → DTO 필드
- RSS: `ingestion/connectors/rss.py`
  - fetcher 미주입 시 httpx+feedparser로 GET → entries → DTO 매핑(title/summary/link/published)
  - 타임아웃/재시도/언어 필터 옵션
- 재시도/백오프: 지수 백오프(예: 0.5s, 1s) 간단 구현 또는 httpx 내 재시도 유틸(직접 구현)
- 중복 방지: 현 구조(keystore+DB unique) 준수

## 구현 단계(체크리스트)
- [x] 의존성 추가: httpx, pytest-httpx (feedparser는 RSS 단계에서 추가 예정)
- [x] Settings 확장: NEWS_API_* 항목 추가, 기본값/검증, .env.example 반영
- [ ] HTTP 유틸(선택): timeout/retry 래퍼 함수 추가(`ingestion/utils/http.py`)
- [x] NewsAPI 커넥터 HTTP 경로 구현: 성공/빈결과/페이지네이션/에러 매핑(429 포함)
- [ ] RSS 커넥터 HTTP 경로 구현(옵션): feedparser 통합
- [x] 단위 테스트: pytest-httpx로 성공/페이지네이션/429 커버(5xx/언어필터 추가 예정)
- [ ] 계약 테스트: fixtures에 실제 샘플 응답(JSON/RSS) 일부 저장 → 정규화 검증
- [x] 문서 업데이트: README에 스모크 테스트 섹션 추가(Runbook 확장 예정)
- [x] 스모크 가이드: scripts/test_news_api.py 추가 및 README 사용법 반영

## 테스트 전략
- 결정적 단위 테스트: 네트워크 모킹으로 커버, 외부 호출 없음
- 경계/실패: 429 레이트리밋, 5xx, 타임아웃, 빈 articles, 페이지네이션 중단 조건 검증
- E2E(선택): 로컬에서 `.env`에 NEWS_API_KEY 설정 후 수동 실행 커맨드 제공

## 보안/규정
- API 키는 `.env`로만 주입(커밋 금지), 로그에 키/민감 정보 노출 금지
- 레이트 리밋 준수(재시도 상한, 쿨다운), 상업적 이용/출처 정책 확인

## 운영 가이드(추가 예정)
- 환경 변수/의존성 설치 절차, 실패 시 공통 오류/대응(429/401/TimeOut)
- Beat 스케줄 조정 팁(간격/키워드/언어)

## 수용 기준(Acceptance Criteria)
- 설정만 추가하면 로컬에서 `collect_core('AAPL','news_api')`가 최소 1건 이상 수집(성공 케이스)
- 429/5xx 시 TransientError 재시도 후 포기 동작 확인(테스트)
- 페이지네이션 1~2페이지 제한 동작과 정규화 스키마 유효성 보장

## 롤백 계획
- 의존성 추가로 문제가 생길 경우: 커넥터의 HTTP 경로 비활성화(Provider 주입형만 사용), 의존성 제거 PR 분리
