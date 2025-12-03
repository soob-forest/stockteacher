StockTeacher — Slack 주식 리포트 봇 (MVP)

- 목표: 구독한 종목의 하루치 텍스트(뉴스/공시/SNS)를 수집·분석해 Slack으로 요약 리포트를 보내는 파이프라인. 이 저장소에는 현재 수집(ingestion) 스켈레톤(Celery), DB 스키마, 기본 테스트가 포함되어 있습니다.

빠른 시작
- 필수: Python 3.13+, Redis(Celery용), SQLite 또는 PostgreSQL
- 패키지 관리자: uv 권장. 설치 가이드: https://docs.astral.sh/uv/

1) 환경 설정
- 프로젝트 루트에 `.env` 파일을 생성하거나 환경 변수를 내보냅니다. 최소 예시는 다음과 같습니다.
  - `INGESTION_REDIS_URL=redis://localhost:6379/0`
  - `NEWS_API_KEY=dev-placeholder`
  - `POSTGRES_DSN=sqlite:///./var/dev.db`  # 로컬 개발은 SQLite 파일 사용
  - `COLLECTION_SCHEDULES=[{"ticker":"AAPL","source":"news_api","interval_minutes":5,"enabled":true}]`
  - 참고: RSS 기반 수집은 MVP 범위에서 제외되어 현재는 NewsAPI만 지원합니다.
  - 선택: `STRUCTLOG_LEVEL=INFO`
- 로컬 저장 디렉토리 준비: `mkdir -p var/storage`
  - 문서 상 요구사항은 S3 대신 로컬 디렉토리(기본 `./var/storage`, 환경변수 `LOCAL_STORAGE_ROOT` 고려) 사용으로 변경되었습니다.

2) 의존성 설치
- uv 사용: `uv sync --extra test --group dev`
  - 기본 런타임 + 테스트(pytest) + 개발 도구(alembic/sqlalchemy) + Redis 클라이언트(redis)가 설치됩니다.
  - pip 사용 시: `python -m pip install -e .[test] alembic sqlalchemy psycopg[binary] redis`

3) 테스트 실행
- `uv run -- python -m pytest`

4) DB 마이그레이션 적용(SQLite 기본)
- `uv run -- alembic upgrade head`
- Alembic 설정은 `alembic.ini:1`에 있으며, `script_location = ingestion/db/migrations`, 기본 URL은 `sqlite:///./var/dev.db` 입니다.

5) 앱 실행 (로컬 개발용 API + Web)
- 간단 동작 확인: `uv run -- python main.py` (인사 문구 출력)
- Celery 워커: `uv run -- celery -A ingestion.celery_app:get_celery_app worker -l info`
- Celery 비트: `uv run -- celery -A ingestion.celery_app:get_celery_app beat -l info`
  - `INGESTION_REDIS_URL`에 Redis가 실행 중이어야 합니다.
 - 비트 스케줄은 `COLLECTION_SCHEDULES`를 기반으로 생성됩니다.

로컬 전체 서버 실행 스크립트
- docker / docker-compose가 설치되어 있다면, 아래 스크립트로 Redis/Postgres 컨테이너와 API/Web 서버를 한 번에 올릴 수 있습니다.
  - Redis/Postgres 기동 + API/웹 서버 시작: `./scripts/run_servers.sh`
  - 실행 중인 API/웹 서버 및 Redis/Postgres 컨테이너 중지: `./scripts/stop_servers.sh`
- Postgres 컨테이너를 사용할 때 ingestion용 DB 마이그레이션과 더미 데이터는 Alembic으로 적용합니다.
  - 예시: `POSTGRES_DSN=postgresql+psycopg://postgres:postgres@localhost:5432/stockteacher uv run -- alembic upgrade head`
  - 위 명령을 한 번 실행하면 `raw_articles`, `job_runs`, `processed_insights` 스키마와 AAPL 더미 데이터가 생성됩니다.

## 문서

자세한 문서는 [docs/](./docs/README.md)를 참조하세요.

**주요 문서**:
- [아키텍처 개요](./docs/ARCHITECTURE.md) - 시스템 전체 구조
- [운영 가이드](./docs/OPERATIONS.md) - 배포 및 운영 절차
- [테스트 전략](./docs/TESTING.md) - 테스트 방법 및 가이드
- [의사결정 로그](./docs/DECISIONS.md) - 주요 기술 결정 기록
- [로드맵](./docs/ROADMAP.md) - 프로젝트 계획

**모듈별 문서**:
- [Ingestion](./docs/ingestion/README.md) - 데이터 수집
- [Analysis](./docs/analysis/README.md) - LLM 분석
- [Publish](./docs/publish/README.md) - 리포트 게시
- [API](./docs/api/README.md) - REST API
- [Web](./docs/web/README.md) - 웹 애플리케이션

프로젝트 구조 참조
- `ingestion/celery_app.py:17` Celery 팩토리 + Beat 스케줄 구성
- `ingestion/settings.py:38` Pydantic Settings, 환경 검증, 스케줄 파싱
- `ingestion/db/models.py:34` ORM 모델(`RawArticle`, `JobRun`)
- `ingestion/db/migrations/versions/20250118_0001_create_raw_articles_job_runs.py:15` Alembic 베이스라인
- `tests/ingestion/` 단위 테스트(설정, Celery 앱, 마이그레이션)

메모
- 저장소: 코드와 문서 모두 S3 대신 로컬 파일 시스템(`LOCAL_STORAGE_ROOT`, 기본 `./var/storage`)을 사용하도록 정리되었습니다.
- 시크릿: 실제 토큰/키는 커밋하지 마세요. Settings는 `.env`를 자동으로 읽습니다.

운영/관찰성
- 로깅 설정: 환경변수로 제어
  - `STRUCTLOG_LEVEL=INFO|DEBUG|...`
  - `LOG_JSON=1` 설정 시 JSON 로그 출력(기본은 텍스트)
- Redis 준비: `docker-compose up -d redis`
- 중복 제거 저장소: redis-py가 설치되어 있으면 RedisKeyStore 사용(INGESTION_REDIS_URL 기반), 없으면 인메모리 사용으로 자동 폴백
- 수집 태스크 수동 실행 예시(개발용):
  - `uv run -- python -c "from ingestion.tasks.collect import collect_core; print(collect_core('AAPL','news_api'))"`
- 로그 필드: trace_id, ticker, source, fetched, unique, saved 등

분석(LLM) 운영 가이드
- 환경 변수(필수/권장)
  - `OPENAI_API_KEY`(필수), `ANALYSIS_MODEL`(기본 gpt-4o-mini), `ANALYSIS_MAX_TOKENS`(기본 512)
  - `ANALYSIS_TEMPERATURE`(기본 0.2), `DEFAULT_LOCALE`(기본 ko_KR)
  - 비용/안전: `ANALYSIS_COST_LIMIT_USD`(요청당 상한, 기본 0.02), `ANALYSIS_REQUEST_TIMEOUT_SECONDS`(기본 15), `ANALYSIS_RETRY_MAX_ATTEMPTS`(기본 2)
  - 웹/채팅: `NEXT_PUBLIC_API_BASE_URL`(기본 `http://localhost:8000`), `NEXT_PUBLIC_WS_BASE_URL`(기본은 API_BASE를 ws/wss로 치환), `NEXT_PUBLIC_ENABLE_SSE_FALLBACK`(WebSocket 실패 안내 플래그; 기본 false, SSE 미구현)
- 실행 예시(개발용)
  - `uv run -- python -c "from analysis.tasks.analyze import analyze_core; print(analyze_core('AAPL'))"`
- 워커 운영
  - 분석 Celery 태스크는 ingestion Celery 앱과 동일 워커에서 소비된다. 대규모 트래픽 시 `uv run -- celery -A ingestion.celery_app:get_celery_app worker -Q analysis.analyze -l info` 형태의 전용 워커를 추가하는 것을 권장한다.
- 레이트 제한/동시성
  - Celery 워커 동시성(`CELERY_WORKER_CONCURRENCY`)을 보수적으로 설정하고, Beat 스케줄 간격을 충분히 둡니다.
  - 모델/요청당 토큰 상한을 낮춰 비용/지연을 제어합니다.
- 관찰성
  - 로그 이벤트: `analyze.start`(기사 건수), `analyze.saved`(model/tokens/cost), `analyze.transient_error`/`analyze.permanent_error`/`analyze.unexpected_error`로 유형별 실패를 추적합니다.
  - 비용 상한 초과 시 `PermanentLLMError`로 처리되어 재시도하지 않으며, JobRun(stage=analyze, source=openai)이 FAILED로 기록됩니다.
  - 자동 재시도: `TransientLLMError`는 Celery의 backoff+jitter로 최대 3회 재시도합니다.
  - JSON 파싱 실패/타임아웃은 재시도 후 실패 처리하며, 원인 이벤트로 구분됩니다.

실데이터 수집 스모크 테스트(NewsAPI)
- 사전 준비: `.env`에 `NEWS_API_KEY` 설정(그 외 기본값 사용 가능).
- 실행: `uv run -- python -m scripts.test_news_api -t AAPL -n 3  --attempts 2`
  - 출력: 설정 요약 + 수집 개수 + 상위 N건 제목/URL
  - 오류: 401/403(키 문제), 429(레이트리밋), 타임아웃 시 `NEWS_API_TIMEOUT_SECONDS` 상향 및 `NEWS_API_PAGE_SIZE` 축소 권장

Redis 사용 가이드(중복 제거 저장소)
- 목적: 수집 단계에서 기사 fingerprint 기반의 중복 저장을 방지합니다.
- 활성화 조건: `redis` 파이썬 패키지가 설치되어 있고 `INGESTION_REDIS_URL`이 설정되어 있으면 RedisKeyStore를 자동 사용합니다. 그렇지 않으면 인메모리로 폴백합니다.
- 환경 변수 예시:
  - `INGESTION_REDIS_URL=redis://localhost:6379/0`
  - `DEDUP_REDIS_TTL_SECONDS=86400`  # 중복 키 TTL(초), 기본 24h
- 로컬 Redis 실행: `docker-compose up -d redis`
- 연결 확인(선택):
  - `uv run -- python - <<'PY'
import os, redis
url = os.getenv('INGESTION_REDIS_URL','redis://localhost:6379/0')
r = redis.Redis.from_url(url)
print('PING:', r.ping())
PY`
- 동작 확인: 수집 실행 시 로그에 `dedupe.keystore.redis` 이벤트가 출력되면 RedisKeyStore가 사용 중입니다. `dedupe.keystore.memory`면 인메모리 폴백입니다.
