# Python 라이브러리 요약 노트

Python 초보자의 시각에서 이번 프로젝트에 등장하는 주요 라이브러리를 간단히 정리했다.

## uv
- **용도**: 빠른 패키지 관리 및 가상환경 생성기(astral-sh 제작).
- `uv sync` 명령으로 `pyproject.toml`을 읽어 `.venv`를 생성하고 필요한 패키지를 설치한다.
- `uv run -- python -m pytest`처럼 실행 명령 앞에 `uv run --`를 붙이면 `.venv`를 자동 활성화한 뒤 프로그램을 실행한다.
- 장점: Poetry/Pip 대비 설치가 빠르고, 락 파일(`uv.lock`)을 자동 관리하여 재현 가능한 환경을 보장.

## Pydantic & Pydantic Settings
- **용도**: 데이터 검증 및 환경 변수 설정 로더.
- `BaseModel`을 상속해 타입 힌트 기반으로 데이터를 검증하고, 변환 및 사용자 정의 검증기를 제공한다.
- `pydantic-settings`의 `BaseSettings`를 사용하면 OS 환경 변수, .env 파일 등을 자동으로 읽어 들여 설정 객체를 생성.
- 이번 프로젝트에서 `CollectionSchedule`, `Settings` 클래스가 각종 파싱(예: JSON 문자열 → 리스트)과 필수 값 검증을 담당.

## Celery
- **용도**: 분산 작업 큐/스케줄러.
- `Celery("ingestion", broker=config.redis_url)`처럼 앱을 생성하고, Beat(스케줄러) + Worker(작업 실행) 조합으로 태스크를 처리.
- Beat 스케줄은 `app.conf.beat_schedule`에 등록하며, 일정 주기로 지정된 태스크(`collect_articles_for_ticker`)를 큐에 넣는다.
- 구조화 로그, 재시도, 신호 훅(예: worker_shutdown) 등 운영 편의 기능을 제공.

## SQLAlchemy
- **용도**: Python ORM 및 SQL 툴킷.
- `DeclarativeBase`를 상속해 ORM 모델을 정의하고, `mapped_column`으로 컬럼 타입과 제약을 지정.
- 이번 프로젝트에서는 `RawArticle`, `JobRun` 테이블을 모델링하고, `sessionmaker` + `session_scope` 헬퍼로 트랜잭션을 안전하게 다룬다.
- PostgreSQL, SQLite 등 다양한 DB 엔진을 통일된 인터페이스로 사용할 수 있다.

## Alembic
- **용도**: SQLAlchemy를 위한 DB 마이그레이션 도구.
- `alembic.ini`와 `ingestion/db/migrations/env.py`를 통해 프로젝트 구조와 메타데이터를 연결.
- 마이그레이션 파일(예: `20250118_0001_create_raw_articles_job_runs.py`)에 `upgrade`/`downgrade` 함수를 작성해 스키마를 버전 관리.
- `alembic upgrade head`로 최신 스키마 적용, `alembic downgrade -1`로 이전 버전으로 롤백 가능.

## pytest
- **용도**: Python 테스트 프레임워크.
- `test_*.py` 파일과 `assert` 문만으로도 간단히 테스트 작성 가능.
- fixture(`@pytest.fixture`)를 통해 반복되는 준비 작업(예: 임시 SQLite URL 생성)을 재사용.
- `uv run -- python -m pytest`로 실행하면 모든 테스트를 자동 발견하고 실행 결과를 요약해 준다.

---

### 참고 링크
- uv: https://docs.astral.sh/uv/
- Pydantic: https://docs.pydantic.dev/
- Celery: https://docs.celeryq.dev/
- SQLAlchemy: https://docs.sqlalchemy.org/
- Alembic: https://alembic.sqlalchemy.org/
- pytest: https://docs.pytest.org/
