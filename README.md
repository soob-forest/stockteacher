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
