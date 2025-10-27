StockTeacher — Slack 주식 리포트 봇 (MVP)

- 목표: 구독한 종목의 하루치 텍스트(뉴스/공시/SNS)를 수집·분석해 Slack으로 요약 리포트를 보내는 파이프라인. 이 저장소에는 현재 수집(ingestion) 스켈레톤(Celery), DB 스키마, 기본 테스트가 포함되어 있습니다.

빠른 시작
- 필수: Python 3.13+, Redis(Celery용), SQLite 또는 PostgreSQL
- 패키지 관리자: uv 권장. 설치 가이드: https://docs.astral.sh/uv/

1) 환경 설정
- 프로젝트 루트에 `.env` 파일을 생성하거나 환경 변수를 내보냅니다. 최소 예시는 다음과 같습니다.
  - `INGESTION_REDIS_URL=redis://localhost:6379/0`
  - `NEWS_API_KEY=dev-placeholder`
  - `SNS_FEED_URLS=["https://example.com/rss"]`
  - `POSTGRES_DSN=sqlite:///./var/dev.db`  # 로컬 개발은 SQLite 파일 사용
  - `COLLECTION_SCHEDULES=[{"ticker":"AAPL","source":"news_api","interval_minutes":5,"enabled":true}]`
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

5) 앱 실행
- 간단 동작 확인: `uv run -- python main.py` (인사 문구 출력)
- Celery 워커: `uv run -- celery -A ingestion.celery_app:get_celery_app worker -l info`
- Celery 비트: `uv run -- celery -A ingestion.celery_app:get_celery_app beat -l info`
  - `INGESTION_REDIS_URL`에 Redis가 실행 중이어야 합니다.
 - 비트 스케줄은 `COLLECTION_SCHEDULES`를 기반으로 생성됩니다.

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
