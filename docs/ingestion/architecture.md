# Ingestion 아키텍처 개요

## 목적
- Slack 리포트 봇을 위한 데이터 수집 MVP의 스켈레톤을 문서화해 Step 2 이후 구현 범위와 책임을 명확히 한다.
- Celery Beat/Worker 구성, 커넥터 계층, 정규화/중복 제거, 저장 및 관찰성 요구사항을 선제적으로 정의한다.

## 범위
- Celery 기반 작업 스케줄링과 실행 흐름 설계.
- 공시·뉴스·SNS 커넥터 인터페이스와 공통 DTO 요구사항 정리.
- 정규화, 중복 제거, JobRun 기록을 포함한 파이프라인 단계 정의.
- 구성/환경 변수 체계, 외부 의존성(Redis, PostgreSQL, Local filesystem storage) 연결 전략.
- 테스트 전략 및 운영 가시성 요구사항.

## Celery 진입점 요구사항
- ingestion/celery_app.py는 Beat/Worker가 공유하는 단일 Celery 인스턴스를 노출한다.
  - 브로커/백엔드: Redis(URI는 INGESTION_REDIS_URL 환경 변수).
  - Task 자동 등록: ingestion.tasks 패키지 하위 모듈을 import하여 Discover.
  - Beat 스케줄: settings.COLLECTION_SCHEDULES(ticker, source, interval)로부터 동적 생성.
- 초기화 시 로깅 설정(STRUCTLOG_LEVEL, LOG_JSON)과 Sentry/추후 관찰성 훅을 연결할 수 있는 hook 제공.
- Graceful shutdown을 위해 signal handler에서 현재 진행 중인 작업을 안전히 종료하고 JobRun을 업데이트한다.
- 구성 로드 실패, 브로커 연결 실패 시 구체적인 예외 메시지와 종료 코드를 남긴다.

## 모듈 구성 요약
- ingestion/settings.py: Pydantic BaseSettings 기반 구성. 필수 키: NEWS_API_KEY, SNS_FEED_URLS, POSTGRES_DSN, LOCAL_STORAGE_ROOT, DEFAULT_LOCALE 등.
- ingestion/celery_app.py: Celery 인스턴스 팩토리 + Beat 스케줄 로더.
  - 로깅: `utils/logging.configure_logging(level, json_enabled)` 사용
- ingestion/tasks/collect.py: 주요 Celery 태스크(collect_articles_for_ticker, fanout_collection_jobs).
  - trace_id 생성/전파, 수집/저장 이벤트 구조화 로깅
- ingestion/connectors/base.py: 커넥터 인터페이스(fetch(params) -> list[RawArticleDTO]) 및 오류 계층.
- ingestion/connectors/news_api.py, ingestion/connectors/rss.py: 옵션 A 기반 구현.
- ingestion/services/normalizer.py: 텍스트 정규화, 언어 감지, hash 생성.
- ingestion/services/deduplicator.py: Redis + DB를 사용한 중복 검사.
  - KeyStore 구현: InMemory(기본), RedisKeyStore(redis-py 사용 가능 시 자동 사용)
- ingestion/repositories/articles.py: SQLAlchemy 세션을 이용한 RawArticle/JobRun 저장.
- ingestion/models/domain.py: DTO 및 Enum 정의.
- ingestion/db/models.py: SQLAlchemy ORM 모델 정의.
- ingestion/db/session.py: 세션/엔진 초기화, Alembic 연동 헬퍼.
- tests/ingestion/...: 유닛/통합 테스트 패키지, faker/fixtures 포함.

## 디렉터리 구조 초안
```
ingestion/
  __init__.py
  celery_app.py
  settings.py
  models/
    __init__.py
    domain.py
  db/
    __init__.py
    models.py
    session.py
  connectors/
    __init__.py
    base.py
    news_api.py
    rss.py
  services/
    __init__.py
    normalizer.py
    deduplicator.py
  repositories/
    __init__.py
    articles.py
  tasks/
    __init__.py
    collect.py
  utils/
    __init__.py
    logging.py
```

## 데이터 흐름 요약
1. Celery Beat가 구독된 종목/소스를 기준으로 collect_articles_for_ticker 태스크를 생성한다.
2. 태스크는 JobRun 레코드를 생성하고 커넥터 모듈을 통해 원본 데이터를 수집한다.
3. 정규화/언어 감지 후 Redis 기반 중복 검사 및 DB Unique 제약으로 2중 방어한다.
4. 신규 데이터는 RawArticle 테이블에 저장되고, 원문 전문은 로컬 저장소(`LOCAL_STORAGE_ROOT`, 기본 `./var/storage`)에 기록한다.
5. JobRun 상태와 메트릭(소스별 성공/실패, latency)을 구조화 로그와 함께 기록한다.

## 외부 의존성 & 구성
- Redis: Celery 브로커 + dedup cache(INGESTION_REDIS_URL, DEDUP_REDIS_TTL 기본 24h).
  - redis-py 미설치/연결 실패 시 인메모리 키스토어로 자동 폴백
- PostgreSQL: SQLAlchemy + Alembic(POSTGRES_DSN, DB_POOL_SIZE, DB_MAX_OVERFLOW).
- Local storage: 원문 보관(LOCAL_STORAGE_ROOT; 기본값 `./var/storage`).
- Secrets: 기본은 환경 변수, 로컬 개발은 .env + python-dotenv 로딩, 배포 환경은 Secret Manager 연동 TODO.
- 로깅: STRUCTLOG_LEVEL, LOG_JSON 플래그.
  - LOG_JSON=true 시 JSON 포맷 로그 출력, 기본은 텍스트

## 개발/테스트 체크리스트
- 설정: 필수 환경 변수 미설정 시 의미 있는 ValidationError를 발생시키고 테스트한다.
- 커넥터: 정상/RateLimit/오류 응답에 대한 단위 테스트 및 폭포 리트라이 시나리오 작성.
- DB: Alembic 마이그레이션 생성 후 alembic upgrade head 스모크 테스트.
- 태스크: Fake 커넥터 + In-memory Redis(Mock) 조합으로 end-to-end 수집 테스트 작성.
- 관찰성: 구조화 로그 필수 필드(trace_id, job_id, ticker, source)를 검증하는 테스트.

## 운영 고려사항
- Beat 스케줄 변경 시 재배포 없이도 적용할 수 있도록 DB 기반 스케줄 테이블 옵션을 백로그에 남긴다.
- 실패 재시도는 지수 백오프(초기 30초, 2배 증가, 최대 4회)로 설계하고, 연속 실패 시 Slack 경보 및 DLQ(추후) 항목 기록.
- 커넥터별 타임아웃(기본 5초)과 최대 동시 실행 수(워크커 컨커런시)를 설정하여 API Rate Limit을 준수한다.
- 민감 정보(토큰, 키)는 로그와 예외 메시지에 포함하지 않고, 필드 마스킹 유틸리티를 utils/logging.py에 배치한다.
