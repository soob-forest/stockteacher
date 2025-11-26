# StockTeacher 로드맵

이 문서는 StockTeacher 프로젝트의 완료된 마일스톤, 진행 중인 작업, 그리고 향후 계획을 정의합니다.

---

## 프로젝트 현황 (2025년 11월 기준)

### 전체 진행률
- **Phase 1**: 데이터 수집 MVP ✅ 완료
- **Phase 2**: LLM 분석 ✅ 완료
- **Phase 3**: 웹 애플리케이션 ✅ 완료 (베타)
- **Phase 4**: Vector DB + 채팅 고도화 🔄 진행 중
- **Phase 5**: Slack 봇 + 다중 소스 📋 계획됨

### 기술 부채 및 보완 필요 항목
- 채팅 에이전트 LLM 통합 (현재 하드코딩)
- WebSocket 실시간 채팅 (현재 폴링)
- OAuth2/SSO 인증 시스템
- E2E 테스트 확장
- 운영 대시보드 (모니터링)

---

## 완료된 마일스톤

### Phase 1: 데이터 수집 MVP ✅

**완료 날짜**: 2025-10

**주요 성과**:
- ✅ Celery Beat + Worker 기반 스케줄러 구축
- ✅ NewsAPI 커넥터 구현
  - HTTP 클라이언트 (httpx)
  - Rate Limit 처리 및 재시도 로직
  - 페이징 지원
- ✅ 텍스트 정규화 및 언어 감지
  - URL/해시태그 정규화
  - fingerprint 기반 중복 제거
- ✅ Redis 기반 중복 검출 KeyStore
  - NX set 활용
  - InMemory 폴백 지원
- ✅ PostgreSQL/SQLite DB 스키마
  - RawArticle 테이블
  - JobRun 추적 테이블
  - Alembic 마이그레이션
- ✅ 구조화 로깅 (structlog)
  - trace_id 전파
  - JSON/텍스트 전환 지원

**관련 문서**: [ingestion/data-collection-plan.md](./ingestion/data-collection-plan.md)

---

### Phase 2: LLM 분석 ✅

**완료 날짜**: 2025-10

**주요 성과**:
- ✅ OpenAI API 통합 (GPT-4o-mini)
  - 구조화 JSON 출력 강제
  - 재시도 로직 (최대 3회)
  - 비용 가드레일 ($0.02/요청 상한)
  - 타임아웃 관리 (15초)
- ✅ 프롬프트 템플릿화
  - 종목/기간/언어/금칙어 매개변수화
  - 단일 프롬프트로 요약/키워드/감성/이상 통합 생성
- ✅ ProcessedInsight 테이블
  - summary_text, keywords, sentiment_score
  - anomalies (이상 징후)
  - LLM 메타데이터 (model, tokens, cost)
- ✅ 비용/토큰 추적
  - `analyze.saved` 로그 이벤트
  - JobRun(stage=analyze) 기록
- ✅ 테스트
  - Fake Provider로 단위 테스트
  - 성공/실패/비용 초과 시나리오
  - 회귀 테스트

**관련 문서**: [analysis/analysis-plan.md](./analysis/analysis-plan.md)

---

### Phase 3: 웹 애플리케이션 (베타) ✅

**완료 날짜**: 2025-11

**주요 성과**:
- ✅ Next.js 14 프론트엔드 (App Router)
  - 구독 관리 페이지 (`/subscriptions`)
  - 리포트 목록 페이지 (`/reports`)
  - 리포트 상세 페이지 (`/reports/:id`)
  - 즐겨찾기 페이지 (`/reports/favorites`)
  - 기본 채팅 UI (폴링 방식)
- ✅ FastAPI 백엔드
  - REST API (구독, 리포트, 채팅)
  - SQLAlchemy ORM
  - CORS 설정
  - 헬스체크 엔드포인트
- ✅ 채팅 기본 기능
  - ChatSession/ChatMessage DB 모델
  - 세션 생성/메시지 전송/조회 API
  - 현재 하드코딩 응답 (LLM 미통합)
- ✅ Publish 계층
  - Materializer (ProcessedInsight → ReportSnapshot)
  - Idempotency 보장
  - JobRun(stage=publish) 추적
- ✅ 서버 실행 스크립트
  - `scripts/run_servers.sh` (통합 기동)
  - `scripts/stop_servers.sh` (종료)

**관련 문서**: [web/web-application-plan.md](./web/web-application-plan.md)

---

## 진행 중 (Phase 4)

### Vector DB 통합 🔄

**예상 완료**: 2025-12

**목표**: RAG 기반 채팅 품질 향상 및 관련 리포트 추천

**작업 항목**:
- [ ] Vector DB 선정 (Qdrant vs Weaviate vs Pinecone)
- [ ] ProcessedInsight 임베딩 생성 파이프라인
  - OpenAI Embeddings API 또는 오픈소스 모델
  - 비동기 업서트 (materializer 완료 후)
- [ ] RAG 검색 API 구현
  - 유사도 검색 (코사인 유사도)
  - 하이브리드 검색 (벡터 + 키워드)
- [ ] 채팅 엔드포인트 통합
  - Vector 검색 결과를 컨텍스트로 주입
  - LLM 프롬프트 확장
- [ ] 웹 추천 UI
  - 리포트 상세에서 "관련 리포트" 섹션
  - 사용자 피드백 (유용함/유용하지 않음)

**성공 기준**:
- 채팅 응답 관련도 >80% (사용자 피드백 기준)
- 추천 정확도 >70%
- 검색 지연 <200ms

**참고**: [DECISIONS.md - ADR-001](./DECISIONS.md#adr-001-vector-db-도입---option-c-선택)

---

### 채팅 에이전트 고도화 🔄

**예상 완료**: 2025-12

**목표**: WebSocket + LLM 통합으로 실시간 대화 경험 개선

**작업 항목**:
- [ ] 공통 llm/ 모듈 리팩터링
  - analysis/client/openai_client.py → llm/client/openai_client.py
  - 스트리밍 메서드 추가 (stream_chat)
- [ ] WebSocket 백엔드 구현
  - FastAPI WebSocket 엔드포인트
  - ConnectionManager (연결 관리)
  - ChatService (비즈니스 로직)
  - RedisSessionCache (세션 캐시)
- [ ] LLM 스트리밍 통합
  - OpenAI Streaming API 호출
  - 청크 단위 응답 (5-10 토큰)
  - 토큰/비용 추적
- [ ] WebSocket 프론트엔드
  - useChatWebSocket 훅
  - 재연결 로직 (지수 백오프)
  - 타이핑 표시
- [ ] 테스트
  - WebSocket 통합 테스트
  - 부하 테스트 (100 동시 연결)
  - E2E 테스트 (Playwright)

**성공 기준**:
- WebSocket 연결 <500ms
- 첫 토큰 도착 <2초
- 스트리밍 속도 10-20 토큰/초
- 50개 동시 연결 지원
- 채팅 전환율 >30%

**참고**: 채팅 에이전트 구현 계획 (Phase B)

---

### E2E 테스트 확장 🔄

**예상 완료**: 2025-12

**작업 항목**:
- [ ] Playwright 테스트 추가
  - 구독 관리 플로우
  - 리포트 필터링
  - 즐겨찾기 토글
  - 채팅 WebSocket 플로우
- [ ] CI/CD 통합
  - GitHub Actions 워크플로우
  - 자동 브라우저 테스트
- [ ] 시각 회귀 테스트
  - 스냅샷 비교
  - 레이아웃 변경 감지

**성공 기준**:
- E2E 커버리지 >80% (주요 사용자 플로우)
- CI에서 안정적 실행 (flakiness <5%)

**참고**: [web/web-e2e-tests-plan.md](./web/web-e2e-tests-plan.md)

---

## 계획됨 (Phase 5 - Q1 2026)

### Slack 봇 연동 📋

**예상 시작**: 2026-01

**목표**: 기존 웹 기반 리포트를 Slack으로 확장

**주요 기능**:
- Slack 봇 등록 및 인증 (OAuth2)
- 구독 관리 (Slash Commands)
  - `/stock subscribe AAPL`
  - `/stock list`
  - `/stock unsubscribe AAPL`
- 리포트 푸시 알림
  - 일일 요약 (스케줄러)
  - 이상 징후 알림 (즉시)
- 대화형 채팅
  - 멘션 기반 질의 (`@StockTeacher AAPL 어떻게 생각해?`)
  - 스레드 기반 대화
- 웹 <-> Slack 연동
  - 동일 사용자 계정 매핑
  - 웹에서 Slack 알림 설정

**기술 스택**:
- Slack Bolt for Python
- Slack Events API (WebSocket 또는 HTTP)
- 기존 FastAPI와 통합

**성공 기준**:
- Slack 사용자 >50% (웹 사용자 대비)
- 알림 오픈율 >60%
- 챗봇 응답 만족도 >4.0/5.0

---

### 다중 데이터 소스 (RSS 재검토) 📋

**예상 시작**: 2026-02

**목표**: NewsAPI 외 추가 소스로 데이터 다양성 확보

**후보 소스**:
- **RSS 피드**
  - 주요 언론사 RSS
  - 포맷 정규화 필요
  - 신뢰성 낮음 (수동 관리 필요)
- **DART 공시**
  - 금융감독원 전자공시 API
  - 기업 공시/재무제표
  - 법적 리스크 낮음
- **Twitter/X API**
  - 주요 계정 모니터링
  - 실시간성 높음
  - 비용/Rate Limit 고려

**우선순위**: DART > RSS > Twitter

**참고**: [ingestion/news-integration-plan.md](./ingestion/news-integration-plan.md)

---

### 추천 검색 (Vector DB Option A) 📋

**예상 시작**: 2026-02

**목표**: 사용자가 직접 검색할 수 있는 UI 제공

**주요 기능**:
- 자연어 검색 ("AAPL 관련 최근 이상 징후")
- 유사 리포트 찾기 ("이런 리포트 더 보기")
- 키워드 기반 필터링
- 검색 히스토리 및 북마크

---

## 백로그 (우선순위 낮음)

### 다국어 지원 (NICE)
- 영어/한국어 UI 전환
- 다국어 분석 모델 선택
- 자동 언어 감지

### 이메일/모바일 푸시 알림 (NICE)
- 이메일 다이제스트 (주간/월간)
- 모바일 푸시 (React Native 앱 필요)
- 알림 채널 커스터마이즈

### 주간/월간 추세 리포트 (NICE)
- 장기 추세 분석
- 종목 간 비교
- 시각화 대시보드

### 급등락 실시간 알림 (NICE)
- 주가 변동 감지 (외부 API 연동)
- Toast/모달 알림
- WebSocket 기반 실시간 푸시

### 음성 인터페이스 (NICE)
- 음성 질의 (STT)
- 음성 응답 (TTS)
- 모바일 앱 연동

---

## 기술 부채 및 개선 항목

### 인증/인가 시스템
- 현재: 없음 (임시 user_id 사용)
- 목표: OAuth2/SSO (Google, GitHub)
- RBAC (일반 사용자/관리자)
- JWT 기반 세션 관리

### 운영 대시보드
- 파이프라인 상태 모니터링
- 실패 로그 조회
- 수동 재처리 트리거
- LLM 비용 추적

### 성능 최적화
- DB 쿼리 최적화 (인덱스, N+1 문제)
- 캐싱 전략 (Redis, CDN)
- 이미지 최적화 (Next.js Image)
- 번들 사이즈 감소

### 보안 강화
- API Rate Limiting
- CSRF 보호
- XSS/SQL Injection 방어
- 정기 보안 감사

---

## 측정 가능한 목표 (KPI)

### 시스템 안정성
- [ ] 일일 리포트 생성 성공률 >98%
- [ ] 수집 → 게시 지연 <10분
- [ ] API 응답 시간 p95 <500ms
- [ ] 시스템 가동률 >99.5%

### 사용자 경험
- [ ] 리포트 열람 후 채팅 전환율 >30%
- [ ] 채팅 응답 만족도 >4.0/5.0
- [ ] 일일 활성 사용자(DAU) >100명
- [ ] 주간 유지율 >70%

### 데이터 품질
- [ ] 자동 분류/요약 오류율 <2%
- [ ] 중복 기사 필터링 정확도 >99%
- [ ] LLM 응답 JSON 파싱 성공률 >95%

### 비용 효율
- [ ] LLM 비용/리포트 <$0.02
- [ ] 인프라 비용/사용자 <$1/월
- [ ] 데이터 전송 비용 최소화

---

## 의사결정 로그 연동

로드맵의 주요 기능/아키텍처 결정은 [DECISIONS.md](./DECISIONS.md)에 ADR로 기록됩니다:
- **ADR-001**: Vector DB Option C 선택
- **ADR-002**: NewsAPI 우선 (RSS 보류)
- **ADR-003**: LLM 단일 프롬프트
- **ADR-004**: Next.js + FastAPI
- **ADR-005**: Bash 서버 스크립트
- **ADR-006**: Playwright E2E 테스트

---

## 관련 문서

- [아키텍처 개요](./ARCHITECTURE.md)
- [의사결정 로그](./DECISIONS.md)
- [운영 가이드](./OPERATIONS.md)
- [테스트 전략](./TESTING.md)
- [모듈별 README](./README.md)
