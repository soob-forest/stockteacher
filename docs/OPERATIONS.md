# StockTeacher 운영 가이드

이 문서는 StockTeacher 시스템의 로컬 개발 및 프로덕션 운영을 위한 통합 가이드입니다.

## 운영 개요

### 목적
수집·분석·게시·웹 API 파이프라인의 기동, 모니터링, 장애 대응 절차를 문서화합니다.

### 대상 독자
- 로컬 개발자: 개발 환경 구성 및 테스트
- 운영 엔지니어: 프로덕션 배포 및 모니터링
- SRE: 장애 대응 및 성능 최적화

### 주요 구성 요소
- **Ingestion**: Celery Beat + Worker (데이터 수집)
- **Analysis**: Celery Worker (LLM 분석)
- **Publish**: Materializer (게시)
- **API**: FastAPI (백엔드 REST/WebSocket)
- **Web**: Next.js (프론트엔드)
- **Infrastructure**: Redis, PostgreSQL/SQLite, Local Storage

---

## 사전 준비

### 1. 필수 소프트웨어

#### Python 환경
- Python 3.13+
- uv (권장 패키지 관리자): https://docs.astral.sh/uv/
- 또는 pip

#### Redis (Celery 브로커 + 중복 제거)
```bash
# Docker Compose 사용 (권장)
docker-compose up -d redis

# 또는 로컬 설치 (macOS)
brew install redis
brew services start redis
```

#### PostgreSQL (프로덕션) 또는 SQLite (로컬 개발)
```bash
# PostgreSQL - Docker Compose 사용
docker-compose up -d postgres

# 또는 로컬 설치 (macOS)
brew install postgresql@16
brew services start postgresql@16
```

#### Node.js (웹 개발)
- Node.js 20+
- npm 또는 pnpm

### 2. 환경 변수 설정

#### .env 파일 생성
프로젝트 루트에 `.env` 파일을 생성하거나 `.env.example`을 복사합니다:

```bash
cp .env.example .env
```

#### 필수 환경 변수

**Ingestion / Infrastructure**
```bash
INGESTION_REDIS_URL=redis://localhost:6379/0
POSTGRES_DSN=sqlite:///./var/dev.db  # 로컬: SQLite
# POSTGRES_DSN=postgresql+psycopg://postgres:postgres@localhost:5432/stockteacher  # 프로덕션: PostgreSQL
LOCAL_STORAGE_ROOT=./var/storage
STRUCTLOG_LEVEL=INFO
LOG_JSON=0  # 로컬은 텍스트, 프로덕션은 1 (JSON)
DEDUP_REDIS_TTL_SECONDS=86400
```

**Collection Sources**
```bash
NEWS_API_KEY=your-newsapi-key-here
NEWS_API_ENDPOINT=https://newsapi.org/v2/everything
NEWS_API_TIMEOUT_SECONDS=5
NEWS_API_MAX_RETRIES=2
NEWS_API_PAGE_SIZE=20
NEWS_API_LANG=ko
NEWS_API_SORT_BY=publishedAt
COLLECTION_SCHEDULES=[{"ticker":"AAPL","source":"news_api","interval_minutes":5,"enabled":true}]
```

**Analysis (OpenAI)**
```bash
OPENAI_API_KEY=sk-your-openai-key-here
ANALYSIS_MODEL=gpt-4o-mini
ANALYSIS_MAX_TOKENS=512
ANALYSIS_TEMPERATURE=0.2
ANALYSIS_COST_LIMIT_USD=0.02
ANALYSIS_REQUEST_TIMEOUT_SECONDS=15
ANALYSIS_RETRY_MAX_ATTEMPTS=2
DEFAULT_LOCALE=ko_KR
```

**API (Web Backend)**
```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/stockteacher
```

### 3. 의존성 설치

#### Python 의존성
```bash
# uv 사용 (권장)
uv sync --extra test --group dev

# pip 사용
python -m pip install -e .[test] alembic sqlalchemy psycopg[binary] redis
```

#### Web 의존성
```bash
cd web
npm install
cd ..
```

### 4. 로컬 저장 디렉토리 준비
```bash
mkdir -p var/storage var/pids
```

### 5. 데이터베이스 마이그레이션

#### SQLite (로컬 개발)
```bash
uv run -- alembic upgrade head
```

#### PostgreSQL (프로덕션)
```bash
# Docker Compose로 Postgres 기동 후
docker-compose up -d postgres

# 마이그레이션 적용
POSTGRES_DSN=postgresql+psycopg://postgres:postgres@localhost:5432/stockteacher \
  uv run -- alembic upgrade head
```

---

## 서비스 기동

### 로컬 개발 환경

#### 통합 스크립트 사용 (권장)
```bash
# Redis + Postgres + API + Web 한 번에 기동
./scripts/run_servers.sh

# 서버 중지
./scripts/stop_servers.sh
```

#### 개별 서비스 기동

##### 1. Redis + PostgreSQL (백그라운드)
```bash
docker-compose up -d redis postgres
```

##### 2. Celery Worker (데이터 수집)
```bash
uv run -- celery -A ingestion.celery_app:get_celery_app worker -l info
```

##### 3. Celery Beat (스케줄러)
```bash
uv run -- celery -A ingestion.celery_app:get_celery_app beat -l info
```

##### 4. FastAPI 백엔드 (API 서버)
```bash
uv run -- uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

##### 5. Next.js 프론트엔드 (웹 서버)
```bash
cd web
npm run dev
# 기본 포트: 3000
```

### 프로덕션 환경

#### Celery Worker + Beat (systemd 예시)
```ini
# /etc/systemd/system/celery-worker.service
[Unit]
Description=Celery Worker
After=network.target redis.target

[Service]
Type=forking
User=stockteacher
WorkingDirectory=/opt/stockteacher
Environment=PATH=/opt/stockteacher/.venv/bin
ExecStart=/opt/stockteacher/.venv/bin/celery -A ingestion.celery_app:get_celery_app worker -l info --detach
ExecStop=/bin/kill -TERM $MAINPID
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

#### FastAPI (Uvicorn + Gunicorn)
```bash
gunicorn api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

#### Next.js (프로덕션 빌드)
```bash
cd web
npm run build
npm run start  # 또는 정적 배포 (Vercel, Netlify)
```

---

## 모니터링 및 로깅

### 로깅 설정

#### 환경 변수
- `STRUCTLOG_LEVEL=INFO|DEBUG|WARNING|ERROR`
- `LOG_JSON=1` (프로덕션에서 JSON 로그 활성화)

#### 로그 필드
- `trace_id`: 분산 추적 ID (요청/파이프라인 전체 추적)
- `ticker`: 종목 코드
- `source`: 데이터 소스 (news_api, etc.)
- `stage`: 파이프라인 단계 (collect, analyze, publish, chat)
- `status`: 성공/실패 상태
- `saved`: 저장된 레코드 수
- `fetched`: 수집된 레코드 수
- `unique`: 중복 제거 후 고유 레코드 수

#### 로그 조회 예시
```bash
# trace_id로 전체 파이프라인 추적
grep "trace_id=abc123" logs/celery-worker.log

# 실패 이벤트만 조회
grep "status=FAILED" logs/celery-worker.log | jq .

# 비용 상한 초과 이벤트
grep "permanent_error" logs/celery-worker.log | grep "cost"
```

### 메트릭 모니터링

#### Celery 메트릭
- 활성 워커 수: `celery -A ingestion.celery_app:get_celery_app inspect active`
- 큐 길이: `celery -A ingestion.celery_app:get_celery_app inspect reserved`
- 실패 태스크: JobRun 테이블 조회

#### LLM 메트릭
- 토큰 사용량: `analyze.saved` 로그 이벤트
- 비용: `llm_cost` 필드 집계
- 지연 시간: `analyze.start` ~ `analyze.saved` 타임스탬프 차이

#### API 메트릭 (향후 Prometheus)
- 요청 수: `/api/*` 엔드포인트별
- 응답 시간: p50, p95, p99
- 오류율: 4xx, 5xx

---

## 데이터 수집 운영

### 수집 스케줄 관리

#### 스케줄 확인
```bash
# 현재 스케줄 조회
echo $COLLECTION_SCHEDULES | jq .

# 예시 출력:
# [
#   {"ticker": "AAPL", "source": "news_api", "interval_minutes": 5, "enabled": true},
#   {"ticker": "TSLA", "source": "news_api", "interval_minutes": 10, "enabled": true}
# ]
```

#### 스케줄 수정
1. `.env` 파일에서 `COLLECTION_SCHEDULES` 수정
2. Celery Beat 재시작

```bash
# 특정 종목 비활성화
COLLECTION_SCHEDULES='[{"ticker":"AAPL","source":"news_api","interval_minutes":5,"enabled":false}]'
```

### 수동 수집 실행

#### 단일 종목 수집
```bash
uv run -- python -c "from ingestion.tasks.collect import collect_core; print(collect_core('AAPL', 'news_api'))"
```

#### 실데이터 수집 스모크 테스트
```bash
uv run -- python -m scripts.test_news_api -t AAPL -n 3 --attempts 2
```

### 중복 제거 확인

#### Redis 키스토어 확인
```bash
# Redis 연결 확인
docker-compose exec redis redis-cli PING

# 중복 키 조회 (예시)
docker-compose exec redis redis-cli --scan --pattern "dedupe:*"
```

#### 동작 확인
- 로그에서 `dedupe.keystore.redis` 이벤트 확인 (Redis 사용)
- `dedupe.keystore.memory` 이벤트 확인 (인메모리 폴백)

---

## 분석(LLM) 운영

### 사전 준비

#### 환경 변수 확인
```bash
# OpenAI API 키 설정 확인
echo $OPENAI_API_KEY | head -c 10

# 모델 및 비용 설정
echo $ANALYSIS_MODEL  # gpt-4o-mini 권장
echo $ANALYSIS_COST_LIMIT_USD  # 기본 0.02
```

### 수동 분석 실행
```bash
uv run -- python -c "from analysis.tasks.analyze import analyze_core; print(analyze_core('AAPL'))"
```

### 레이트 제한 및 동시성 제어

#### Celery 워커 동시성 조정
```bash
# 동시성 2로 제한
uv run -- celery -A ingestion.celery_app:get_celery_app worker -l info --concurrency=2

# 전용 분석 워커 (분석 큐만 처리)
uv run -- celery -A ingestion.celery_app:get_celery_app worker -Q analysis.analyze -l info
```

#### Beat 스케줄 간격 확대
`.env`에서 `COLLECTION_SCHEDULES`의 `interval_minutes` 증가

#### 토큰 상한 조정
```bash
# 토큰 수 감소
ANALYSIS_MAX_TOKENS=256  # 기본 512
```

### 관찰 포인트

#### 로그 이벤트
- `analyze.start`: 분석 시작 (기사 수 포함)
- `analyze.saved`: 분석 완료 (model, tokens, cost 포함)
- `analyze.no_articles`: 분석할 기사 없음
- `analyze.transient_error`: 일시 오류 (재시도 가능)
- `analyze.permanent_error`: 영구 오류 (재시도 불가)
- `analyze.unexpected_error`: 예상치 못한 오류

#### JobRun 테이블 조회
```sql
SELECT * FROM job_runs
WHERE stage = 'analyze' AND source = 'openai'
ORDER BY started_at DESC
LIMIT 10;
```

### 플레이북

#### 문제: 기사 없음 (`analyze.no_articles`)
**원인**: 수집 파이프라인 실패 또는 스케줄 미설정
**대응**:
1. 수집 상태 확인: `grep "collect.core" logs/celery-worker.log`
2. 스케줄 확인: `echo $COLLECTION_SCHEDULES`
3. 수동 수집 실행: `collect_core('AAPL', 'news_api')`

#### 문제: JSON 파싱 실패
**원인**: LLM 응답 형식 오류
**대응**:
1. 프롬프트 템플릿 확인: `analysis/prompts/templates.py`
2. 로케일 확인: `echo $DEFAULT_LOCALE`
3. 재시도 횟수 조정: `ANALYSIS_RETRY_MAX_ATTEMPTS=3`
4. TransientLLMError는 최대 3회 자동 재시도

#### 문제: 비용 상한 초과 (`PermanentLLMError`)
**원인**: 토큰 사용량 과다
**대응**:
1. 모델 변경: `ANALYSIS_MODEL=gpt-4o-mini` (더 저렴한 모델)
2. 토큰 상한 하향: `ANALYSIS_MAX_TOKENS=256`
3. Beat 간격 조정: 수집 빈도 감소
4. 비용 상한 상향 (임시): `ANALYSIS_COST_LIMIT_USD=0.05`

#### 문제: 타임아웃
**원인**: 네트워크 지연 또는 입력 크기 과다
**대응**:
1. 타임아웃 상향: `ANALYSIS_REQUEST_TIMEOUT_SECONDS=30`
2. 입력 청크 축소: 기사 수 제한 (`analyze_core` 파라미터)
3. 동시성 하향: `--concurrency=1`

---

## 웹 API 운영

### API 서버 기동
```bash
# 개발 (hot reload)
uv run -- uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 프로덕션
gunicorn api.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 헬스체크
```bash
curl http://localhost:8000/healthz
# 출력: {"status":"ok"}
```

### 주요 엔드포인트
- `GET /api/subscriptions`: 구독 목록
- `POST /api/subscriptions`: 구독 생성
- `GET /api/reports`: 리포트 목록
- `GET /api/reports/:id`: 리포트 상세
- `POST /api/chat/sessions`: 채팅 세션 생성
- `GET /api/chat/sessions/:id/messages`: 메시지 조회

### 웹 서버 기동 (Next.js)
```bash
cd web
npm run dev  # 개발
npm run build && npm run start  # 프로덕션
```

---

## 장애 대응 체크리스트

### 수집 파이프라인 실패
- [ ] Redis 연결 확인: `docker-compose ps redis`, `INGESTION_REDIS_URL` 설정
- [ ] DB 연결 확인: `POSTGRES_DSN` 접속, 마이그레이션 적용 여부
- [ ] NewsAPI 키 확인: `NEWS_API_KEY` 유효성
- [ ] Rate Limit 확인: `news_api.rate_limit` 로그 이벤트
- [ ] 중복 적재 급증: fingerprint/키스토어 설정 점검

### 분석 파이프라인 실패
- [ ] OpenAI API 키 확인: `OPENAI_API_KEY` 유효성
- [ ] 비용 상한 확인: `ANALYSIS_COST_LIMIT_USD` vs 실제 사용량
- [ ] 네트워크 확인: OpenAI API 연결 (curl 테스트)
- [ ] 로그 조회: `analyze.permanent_error`, `analyze.transient_error`

### 웹 API 응답 없음
- [ ] FastAPI 프로세스 확인: `ps aux | grep uvicorn`
- [ ] 포트 확인: `lsof -i :8000`
- [ ] DB 연결 확인: `DATABASE_URL` 설정
- [ ] 로그 조회: `logs/api.log` 또는 stdout

### Celery Beat/Worker 미동작
- [ ] Redis 브로커 확인: `docker-compose ps redis`
- [ ] 프로세스 확인: `ps aux | grep celery`
- [ ] 스케줄 확인: `COLLECTION_SCHEDULES` 파싱 오류
- [ ] 워커 등록 확인: `celery -A ingestion.celery_app:get_celery_app inspect active`

### 연속 실패 시 긴급 조치
1. Beat 스케줄 비활성화: `COLLECTION_SCHEDULES` 모두 `"enabled":false`
2. Celery Worker 중지: `pkill -f celery`
3. 원인 분석: 로그, JobRun 테이블 조회
4. 수정 후 재기동

---

## 보안 운영

### 비밀값 관리
- **로컬 개발**: `.env` 파일 (`.gitignore`에 포함)
- **프로덕션**: KMS, Secrets Manager, Vault 등 사용
- **원칙**: 코드/로그/티켓에 비밀값 절대 포함 금지

### 환경 변수 검증
```bash
# 필수 환경 변수 누락 확인
uv run -- python -c "from ingestion.settings import get_settings; print(get_settings())"

# ValidationError 발생 시 누락/잘못된 값 확인
```

### 로그 PII 제거
- 사용자 이메일, 전화번호 등 민감 정보 마스킹
- `ingestion/utils/logging.py`에 마스킹 유틸리티 배치

### 최소 권한 원칙
- Celery Worker: DB 읽기/쓰기, Redis 접근
- FastAPI: DB 읽기/쓰기, OpenAI API 호출
- Web: API 호출만 (DB 직접 접근 금지)

---

## 운영 팁

### 로컬 vs 프로덕션
- **로컬 개발**: SQLite, 텍스트 로그, DEBUG 레벨
- **프로덕션**: PostgreSQL, JSON 로그, INFO 레벨

### trace_id 활용
- 분산 추적: 수집 → 분석 → 게시 전 단계 추적
- 로그 조회: `grep "trace_id=abc123" logs/*.log`
- JobRun 테이블 조회: `WHERE trace_id = 'abc123'`

### 민감 정보 관리
- 로그에 API 키, 토큰 포함 금지
- 환경 변수로만 관리
- `.env` 파일은 절대 커밋하지 않음

### 개발 환경 빠른 확인
```bash
# 전체 환경 확인
./scripts/run_servers.sh
curl http://localhost:8000/healthz
curl http://localhost:3000

# 수집 + 분석 테스트
uv run -- python -c "from ingestion.tasks.collect import collect_core; collect_core('AAPL', 'news_api')"
uv run -- python -c "from analysis.tasks.analyze import analyze_core; analyze_core('AAPL')"
```

---

## 관련 문서

- [아키텍처 개요](./ARCHITECTURE.md)
- [모듈별 README](./README.md)
- [테스트 전략](./TESTING.md)
- [의사결정 로그](./DECISIONS.md)
- [Ingestion 아키텍처](./ingestion/architecture.md)
