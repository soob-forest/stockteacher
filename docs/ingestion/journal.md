# 2025-10-18 작업 메모

## Step 1 — 데이터 수집 스켈레톤 설계
- `DATA_COLLECTION_PLAN.md`에 Problem 1-Pager와 6단계 실행 계획을 정의하고, `docs/ingestion/architecture.md`로 Celery 기반 수집 파이프라인 구조/의존성/운영 포인트를 정리했다.
- 주요 산출물:
  - Celery 진입점 요구사항(Beat 스케줄, 로깅 훅, Graceful shutdown).
  - 모듈 디렉터리 초안 및 데이터 흐름 요약.

## Step 2 — 설정 및 Celery 부트스트랩
- `ingestion/settings.py`에 Pydantic Settings를 구현해 환경 변수 파싱, 스케줄 중복 검증, 캐시 리셋을 지원.
- `ingestion/celery_app.py`에서 Celery 인스턴스 팩토리, Beat 스케줄 로더, 신호 훅을 정의.
- 테스트 (`tests/ingestion/test_settings.py`, `tests/ingestion/test_celery_app.py`)를 통해 환경 파싱과 스케줄 생성 로직을 검증.
- uv 기반 의존성 관리로 `pyproject.toml`에 핵심 런타임 및 테스트 패키지를 명시하고, `uv sync`로 `.venv`를 재구성.

## Step 3 — ORM 및 마이그레이션 베이스라인
- `ingestion/db/models.py`에 `RawArticle`, `JobRun` 모델과 타임스탬프 믹스인을 추가하고 `JobStage`, `JobStatus` Enum을 정의.
- `ingestion/db/session.py`에서 엔진/세션 팩토리와 트랜잭션 스코프 헬퍼를 제공.
- Alembic 설정(`alembic.ini`, `ingestion/db/migrations/env.py`)과 베이스라인 마이그레이션(`20250118_0001_create_raw_articles_job_runs.py`)을 작성.
- `tests/ingestion/test_migrations.py`로 SQLite 환경에서 스키마 생성과 ORM round-trip을 스모크 테스트.
- 작업 완료 후 `DATA_COLLECTION_PLAN.md` Step 3 체크 완료.

## 실행 & 확인 커맨드
- 의존성 설치: `uv sync --extra test --group dev`
- 테스트: `uv run -- python -m pytest`

