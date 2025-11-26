# Web (웹 애플리케이션) 모듈

## 개요

Next.js 기반 사용자 포털과 FastAPI 백엔드 API를 제공합니다.

## 주요 화면

### 프론트엔드 (Next.js)
- **구독 관리** (`/subscriptions`): 종목 검색, 등록/해지, 알림 설정
- **리포트 목록** (`/reports`): 날짜 필터, 감성 태그, 즐겨찾기
- **리포트 상세** (`/reports/:id`): 요약 블록, 감성 게이지, 핵심 링크, 채팅 UI
- **즐겨찾기** (`/reports/favorites`): 즐겨찾기 리포트 모음

### 백엔드 (FastAPI)
- **구독 API**: GET/POST/DELETE `/api/subscriptions`
- **리포트 API**: GET `/api/reports`, GET `/api/reports/:id`
- **채팅 API**: POST `/api/chat/sessions`, POST/GET `/api/chat/sessions/:id/messages`
- **헬스체크**: GET `/healthz`

## 문서

- [웹 애플리케이션 구현 계획](./web-application-plan.md) - 웹 구현 상세 계획 및 체크리스트
- [E2E 테스트 계획](./web-e2e-tests-plan.md) - Playwright 기반 E2E 테스트 전략
- [서버 실행 스크립트 계획](./server-scripts-plan.md) - 로컬 서버 실행/중지 스크립트

## 주요 디렉토리 및 파일

### 프론트엔드 (web/)
| 파일/디렉토리 | 설명 |
|------------|------|
| `web/app/page.tsx` | 루트 페이지 (→ /subscriptions 리다이렉트) |
| `web/app/subscriptions/page.tsx:21` | 구독 관리 페이지 |
| `web/app/reports/page.tsx` | 리포트 목록 |
| `web/app/reports/favorites/page.tsx` | 즐겨찾기 리포트 |
| `web/app/reports/[insightId]/page.tsx:27` | 리포트 상세 + 채팅 UI |
| `web/components/ReportsBoard.tsx:27` | 리포트 보드 컴포넌트 |
| `web/lib/api.ts` | API 클라이언트 (fetch 래퍼) |

### 백엔드 (api/)
| 파일 | 설명 | 주요 엔드포인트 |
|-----|------|---------------|
| `api/main.py:9` | FastAPI 앱 + CORS 설정 | - |
| `api/routes.py:92` | 라우트 핸들러 | GET/POST /api/subscriptions, /api/reports, /api/chat/* |
| `api/repositories.py:162` | 데이터 액세스 레이어 | CRUD 함수 |
| `api/db_models.py:81` | ORM 모델 | ChatSession, ChatMessage, ReportSnapshot |
| `api/models.py` | Pydantic 모델 | 요청/응답 DTO |

## 기술 스택

### 프론트엔드
- **프레임워크**: Next.js 14.2 (App Router)
- **언어**: TypeScript 5.4
- **UI**: React 18.3
- **스타일**: CSS Modules (기본)

### 백엔드
- **프레임워크**: FastAPI 0.115
- **ORM**: SQLAlchemy 2.0
- **DB**: PostgreSQL (프로덕션), SQLite (로컬)
- **언어**: Python 3.13+

## 실행 방법

### 통합 스크립트 (권장)
```bash
# API + Web 서버 한 번에 기동
./scripts/run_servers.sh

# 서버 중지
./scripts/stop_servers.sh
```

### 개별 실행

#### FastAPI 백엔드
```bash
# 개발 모드 (hot reload)
uv run -- uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 프로덕션
gunicorn api.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

#### Next.js 프론트엔드
```bash
cd web

# 개발 모드
npm run dev

# 프로덕션 빌드
npm run build
npm run start
```

## API 엔드포인트

### 구독 관리
- `GET /api/subscriptions` - 구독 목록 조회
- `POST /api/subscriptions` - 구독 생성
  ```json
  {
    "ticker": "AAPL",
    "user_id": "user-123"
  }
  ```
- `DELETE /api/subscriptions/:id` - 구독 삭제

### 리포트
- `GET /api/reports` - 리포트 목록 (필터링/페이징)
  - Query: `?sentiment=positive&favorite=true&limit=20&offset=0`
- `GET /api/reports/:id` - 리포트 상세

### 채팅
- `POST /api/chat/sessions` - 채팅 세션 생성
  ```json
  {
    "insight_id": "insight-123"
  }
  ```
- `GET /api/chat/sessions/:id/messages` - 메시지 목록
- `POST /api/chat/sessions/:id/messages` - 메시지 전송
  ```json
  {
    "content": "AAPL 전망은 어떤가요?"
  }
  ```

## 테스트

### API 테스트 (pytest)
```bash
# 전체 API 테스트
uv run -- python -m pytest tests/api/

# 특정 테스트
uv run -- python -m pytest tests/api/test_reports_api.py
```

### E2E 테스트 (Playwright)
```bash
# 사전 조건: API + Web 서버 실행
./scripts/run_servers.sh

# E2E 테스트 실행
cd web
npx playwright test

# UI 모드 (디버깅)
npx playwright test --ui
```

## 환경 변수

### API 백엔드
```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/stockteacher
```

### Web 프론트엔드
```bash
# .env.local
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## 주요 기능 상태

### 완료 ✅
- 구독 관리 CRUD
- 리포트 목록/상세 조회
- 필터링 (감성, 즐겨찾기)
- 기본 채팅 UI (폴링 방식)
- ChatSession/ChatMessage DB 모델

### 진행 중 🔄
- WebSocket 실시간 채팅 (계획됨)
- LLM 통합 (현재 하드코딩)
- OAuth2/SSO 인증

### 계획됨 📋
- 관리자 콘솔
- 알림 설정 커스터마이즈
- 차트/지표 시각화
- 다크 모드

## 관련 문서

- [전체 아키텍처](../ARCHITECTURE.md)
- [운영 가이드 - 서비스 기동](../OPERATIONS.md#서비스-기동)
- [테스트 전략 - Web E2E](../TESTING.md#web-e2e-테스트-playwright)
- [의사결정 - 웹 기술 스택](../DECISIONS.md#adr-004-웹-기술-스택---nextjs--fastapi)
- [의사결정 - E2E 테스트](../DECISIONS.md#adr-006-e2e-테스트---playwright)
