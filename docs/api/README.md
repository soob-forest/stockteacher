# API 모듈

## 개요

FastAPI 기반 REST API와 WebSocket/SSE 채팅 인터페이스를 제공합니다.

## 주요 기능

- **구독 관리 API**: 종목 구독/해지 CRUD
- **리포트 조회 API**: 리포트 목록/상세 조회, 필터링
- **채팅 API**: 세션 생성, 메시지 전송/조회
- **인증/인가**: OAuth2/SSO (향후)
- **CORS**: 웹 프론트엔드와 통신
- **헬스체크**: 시스템 상태 확인

## 주요 파일

| 파일 | 설명 | 주요 엔드포인트/함수 |
|-----|------|-------------------|
| `api/main.py:9` | FastAPI 앱 + CORS 설정 | - |
| `api/routes.py:92` | 라우트 핸들러 | `/api/subscriptions`, `/api/reports`, `/api/chat/*` |
| `api/repositories.py:162` | 데이터 액세스 레이어 | `create_chat_session()`, `add_chat_message()` |
| `api/db_models.py:81` | SQLAlchemy ORM 모델 | `ChatSession`, `ChatMessage`, `ReportSnapshot` |
| `api/models.py` | Pydantic 요청/응답 모델 | `ChatCreateRequest`, `ChatMessage` |
| `api/database.py` | DB 세션 관리 | `get_db()`, `init_db()` |

## 기술 스택

- **프레임워크**: FastAPI 0.115
- **ORM**: SQLAlchemy 2.0
- **DB**: PostgreSQL (프로덕션), SQLite (로컬)
- **검증**: Pydantic 2.12
- **비동기**: asyncio (향후 WebSocket)

## API 엔드포인트

### 시스템
- `GET /healthz` - 헬스체크
  ```json
  {"status": "ok"}
  ```

### 구독 관리
- `GET /api/subscriptions` - 구독 목록 조회
- `POST /api/subscriptions` - 구독 생성
- `DELETE /api/subscriptions/:id` - 구독 삭제

### 리포트
- `GET /api/reports` - 리포트 목록
  - Query params: `sentiment`, `favorite`, `limit`, `offset`
- `GET /api/reports/:id` - 리포트 상세

### 채팅
- `POST /api/chat/sessions` - 채팅 세션 생성
- `GET /api/chat/sessions/:id/messages` - 메시지 목록
- `POST /api/chat/sessions/:id/messages` - 메시지 전송

## 데이터베이스 모델

### ReportSnapshot
리포트 게시 정보 (publish 모듈에서 생성)
- `insight_id` (PK)
- `ticker`, `headline`, `summary_text`
- `sentiment_score`, `anomaly_score`
- `tags`, `keywords`
- `source_refs`, `attachments`
- `published_at`

### ChatSession
채팅 세션 정보
- `session_id` (PK)
- `user_id`, `insight_id`
- `status` (Initiated/Conversing/Completed)
- `started_at`, `updated_at`

### ChatMessage
채팅 메시지
- `message_id` (PK)
- `session_id` (FK)
- `sender` (user/agent/system)
- `content`
- `created_at`

## 실행 방법

### 개발 모드
```bash
uv run -- uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 프로덕션
```bash
gunicorn api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### 헬스체크
```bash
curl http://localhost:8000/healthz
# {"status":"ok"}
```

## 환경 변수

```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/stockteacher
# 또는 SQLite (로컬)
DATABASE_URL=sqlite:///./var/dev.db
```

## 테스트

### 단위 테스트
```bash
uv run -- python -m pytest tests/api/test_repositories.py
```

### 통합 테스트 (FastAPI TestClient)
```bash
uv run -- python -m pytest tests/api/test_reports_api.py
uv run -- python -m pytest tests/api/test_chat_api.py
```

### 테스트 Fixtures
```python
# tests/api/conftest.py
@pytest.fixture
def client():
    from api.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)
```

## 현재 구현 상태

### 완료 ✅
- REST API (구독, 리포트, 채팅)
- ChatSession/ChatMessage CRUD
- CORS 설정
- 헬스체크 엔드포인트
- 기본 채팅 로직 (하드코딩 응답)

### 진행 중 🔄
- WebSocket 엔드포인트 (계획됨)
- LLM 통합 (현재 하드코딩)
- OAuth2/SSO 인증 (계획됨)

### 계획됨 📋
- Rate Limiting
- API 문서 자동 생성 (OpenAPI)
- 관리자 API (재처리, DLQ 조회)
- Vector DB 검색 API (RAG)

## 채팅 현재 동작

### 세션 생성 시
1. ChatSession 생성
2. 시스템 메시지 자동 추가 (리포트 요약)

### 메시지 전송 시
1. 사용자 메시지 저장
2. **에이전트 응답 자동 생성** (하드코딩)
   - 현재: 리포트 요약의 일부만 반환
   - 향후: OpenAI LLM 통합 예정

## 향후 개선 사항

### WebSocket 채팅
- `GET /api/chat/ws/:session_id` - WebSocket 엔드포인트
- ConnectionManager (연결 관리)
- ChatService (비즈니스 로직)
- LLM 스트리밍 통합

### 인증/인가
- OAuth2/SSO (Google, GitHub)
- JWT 기반 세션
- RBAC (일반 사용자/관리자)

### Vector DB 통합
- `/api/search` - 자연어 검색
- `/api/recommendations` - 관련 리포트 추천
- RAG 컨텍스트 주입

## 관련 문서

- [전체 아키텍처](../ARCHITECTURE.md)
- [웹 애플리케이션](../web/README.md)
- [운영 가이드 - 웹 API](../OPERATIONS.md#웹-api-운영)
- [테스트 전략 - API](../TESTING.md#api-테스트)
- [의사결정 - 웹 기술 스택](../DECISIONS.md#adr-004-웹-기술-스택---nextjs--fastapi)
