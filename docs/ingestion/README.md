# Ingestion (데이터 수집) 모듈

## 개요

Celery 기반 스케줄러와 커넥터를 통해 뉴스/공시/SNS 데이터를 수집하고 정규화합니다.

## 주요 기능

- **스케줄링**: Celery Beat + Worker 기반 주기적 수집
- **데이터 소스**: NewsAPI (RSS는 MVP 범위 외)
- **정규화**: 텍스트 정규화, 언어 감지, fingerprint 생성
- **중복 제거**: Redis 기반 KeyStore (InMemory 폴백)
- **저장**: PostgreSQL/SQLite (RawArticle 테이블)
- **추적**: JobRun 테이블로 성공/실패 기록

## 문서

- [아키텍처 개요](./architecture.md) - Celery 구성, 모듈 구조, 데이터 흐름
- [데이터 수집 구현 계획](./data-collection-plan.md) - MVP 구현 계획 및 체크리스트
- [뉴스 통합 계획](./news-integration-plan.md) - NewsAPI vs RSS 의사결정

## 주요 파일

| 파일 | 설명 | 주요 함수/클래스 |
|-----|------|----------------|
| `ingestion/celery_app.py:17` | Celery 팩토리 + Beat 스케줄 구성 | `get_celery_app()` |
| `ingestion/tasks/collect.py:60` | 수집 핵심 로직 | `collect_core()` |
| `ingestion/connectors/news_api.py` | NewsAPI 커넥터 | `NewsAPIConnector` |
| `ingestion/services/deduplicator.py:31` | 중복 제거 | `RedisKeyStore` |
| `ingestion/services/normalizer.py` | 텍스트 정규화 | `normalize_text()` |
| `ingestion/repositories/articles.py` | DB 저장 | `save_raw_article()` |
| `ingestion/settings.py:78` | 설정 및 검증 | `get_settings()` |
| `ingestion/utils/logging.py:40` | 구조화 로깅 | `configure_logging()` |

## 설정

### 환경 변수

```bash
# Redis (Celery 브로커 + 중복 제거)
INGESTION_REDIS_URL=redis://localhost:6379/0
DEDUP_REDIS_TTL_SECONDS=86400

# 데이터베이스
POSTGRES_DSN=sqlite:///./var/dev.db

# 로컬 저장소
LOCAL_STORAGE_ROOT=./var/storage

# 로깅
STRUCTLOG_LEVEL=INFO
LOG_JSON=0

# NewsAPI
NEWS_API_KEY=your-key-here
NEWS_API_ENDPOINT=https://newsapi.org/v2/everything
NEWS_API_TIMEOUT_SECONDS=5
NEWS_API_MAX_RETRIES=2
NEWS_API_PAGE_SIZE=20
NEWS_API_LANG=ko
NEWS_API_SORT_BY=publishedAt

# 수집 스케줄 (JSON 배열)
COLLECTION_SCHEDULES=[{"ticker":"AAPL","source":"news_api","interval_minutes":5,"enabled":true}]
```

## 실행 방법

### Celery Worker 기동
```bash
uv run -- celery -A ingestion.celery_app:get_celery_app worker -l info
```

### Celery Beat 기동
```bash
uv run -- celery -A ingestion.celery_app:get_celery_app beat -l info
```

### 수동 수집
```bash
uv run -- python -c "from ingestion.tasks.collect import collect_core; print(collect_core('AAPL', 'news_api'))"
```

### 실데이터 스모크 테스트
```bash
uv run -- python -m scripts.test_news_api -t AAPL -n 3 --attempts 2
```

## 데이터 흐름

```
1. Celery Beat → 스케줄 기반 collect_articles_for_ticker 태스크 생성
2. Collector → NewsAPI 커넥터 호출
3. Normalizer → 텍스트 정규화 및 fingerprint 생성
4. Deduplicator → Redis + DB 이중 중복 검사
5. Repository → RawArticle 테이블에 저장
6. JobRun → 성공/실패 기록
```

## 테스트

### 단위 테스트
```bash
uv run -- python -m pytest tests/ingestion/test_collect_task.py
```

### 통합 테스트
```bash
uv run -- python -m pytest tests/ingestion/ -m integration
```

### 커버리지
```bash
uv run -- python -m pytest tests/ingestion/ --cov=ingestion --cov-report=term-missing
```

## 관찰성

### 로그 이벤트
- `collect.start`: 수집 시작
- `collect.fetched`: 수집된 기사 수
- `collect.unique`: 중복 제거 후 고유 기사 수
- `collect.saved`: 저장된 기사 수
- `dedupe.keystore.redis`: Redis KeyStore 사용
- `dedupe.keystore.memory`: InMemory 폴백

### JobRun 추적
```sql
SELECT * FROM job_runs
WHERE stage = 'collect' AND source = 'news_api'
ORDER BY started_at DESC
LIMIT 10;
```

## 관련 문서

- [전체 아키텍처](../ARCHITECTURE.md)
- [운영 가이드 - 데이터 수집](../OPERATIONS.md#데이터-수집-운영)
- [테스트 전략 - Ingestion](../TESTING.md#ingestion-테스트)
- [의사결정 - NewsAPI 선택](../DECISIONS.md#adr-002-데이터-수집-커넥터---newsapi-우선)
