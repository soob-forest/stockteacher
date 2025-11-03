# 제품 개요

- 문제/목표: 투자자가 구독한 종목에 대한 뉴스·공시·SNS 동향을 수집·분석해 요약 리포트를 제공하고, 사용자가 웹 포털에서 리포트를 열람하며 에이전트와 대화로 후속 질의를 처리할 수 있도록 한다. 수집과 분석은 OpenAI LLM을 활용하며, 결과는 웹 인터페이스를 통해 안정적으로 노출된다.
- 핵심 사용 시나리오:
  1. 사용자가 웹 포털에 로그인해 관심 종목을 등록·관리하고 알림 빈도를 설정한다.
  2. 스케줄러가 주기적으로 종목 관련 데이터를 외부 API·크롤러로부터 수집하고 전처리한다.
  3. Python 분석 파이프라인이 수집된 데이터를 정규화하고 LLM을 호출해 요약·키워드·감성·이상징후를 생성한다.
  4. 리포트 엔진이 분석 결과를 DB와 스토리지에 저장하고, 웹 포털은 리포트 목록/상세/대화 인터페이스로 사용자에게 제공한다.
- 성공 지표(KPI):
  - 일일 리포트 생성 성공률 98% 이상
  - 데이터 수집 완료부터 웹 포털에 리포트 게시까지 10분 이내
  - 리포트 열람 후 에이전트 대화 개시 비율 30% 이상
  - 자동 분류/요약 오류율 2% 이하

# 기능 목록 (MUST / SHOULD / NICE)

- MUST:
  - 종목 구독/해지 및 현재 구독 현황 조회 (웹 포털 UI + 백엔드 API)
  - 뉴스·공시 API 연동 및 SNS(예: Twitter/X) 데이터 수집
  - 텍스트 정규화: 언어 감지, 중복 제거, URL·해시태그 정규화
  - LLM 기반 분석: 토픽/키워드 추출, 요약, 감성/이상 이벤트 탐지
  - 웹 리포트 화면: 일일 요약, 메트릭, 원문 링크, 관련 아티팩트 뷰어(예: PDF/스크린샷)
  - 웹 기반 에이전트 채팅: 리포트 컨텍스트 기반 후속 질의 응답
  - 시스템 상태 모니터링 및 실패 시 Dead-letter 처리
- SHOULD:
  - 종목별 알림 시간대·빈도 커스터마이즈
  - Kotlin + Spring Boot 기반 관리/구독 API 제공
  - 요약 품질 검증 자동화(간단 룰/프롬프트) 및 리뷰 대기함
  - 다국어(영/한) 분석 모델 선택 지원
  - 리포트 상세에서 관련 차트/지표 시각화
- NICE:
  - 개인화된 사용자 관심사 분석 및 이상징후 알림
  - 이메일/모바일 푸시 등 추가 알림 채널 제공
  - 주간/월간 추세 리포트 대시보드
  - 급등락 감지 시 실시간 웹 알림(Toast/모달)
  - 음성 인터페이스나 대화형 에이전트 고도화

# 화면 / 흐름 (간단 시퀀스 & 상태)

- 페이지/컴포넌트:
  - 구독 관리 페이지: 종목 검색, 등록/해지, 알림 설정
  - 리포트 목록 페이지: 날짜 필터, 감성 태그, 즐겨찾기
  - 리포트 상세 페이지: 요약 블록, 감성 ASCII 게이지, 핵심 링크, 아티팩트 뷰어
  - 대화형 에이전트 패널: 리포트 컨텍스트를 유지한 채팅 UI
  - 관리자 콘솔(SHOULD): 파이프라인 상태, 실패 로그, 수동 재처리 트리거
- 주요 상태/흐름:
  - 종목 구독: Pending Verification → Active → Suspended
  - 데이터 수집 파이프라인: Scheduled → Fetching → Normalized → Ready → Failed(Retry)
  - 분석 파이프라인: Queued → Processing → Completed → Failed(Retry)
  - 리포트 전달 파이프라인: Materializing → Published → Read → Archived → Failed(Manual Action)
  - 에이전트 세션: Initiated → Conversing → Handover (필요 시) → Completed
  - 임계치 초과 시: SLA Breach → Ops 채널 알림 → Manual Intervention

# 데이터 스키마 (간단 키 필드 & 보존 정책)

- 테이블(또는 컬렉션):
  - StockSubscription: subscription_id, user_id, ticker, alert_window, status, created_at, updated_at
  - RawArticle: article_id, source_type(press/api/sns), ticker, title, body, url, collected_at, language, sentiment_raw
  - ProcessedInsight: insight_id, ticker, summary_text, sentiment_score, keywords[], anomaly_score, source_refs[], generated_at, llm_model, llm_tokens_prompt, llm_tokens_completion, llm_cost
  - JobRun: job_id, stage(collect/analyze/publish/chat), status, started_at, ended_at, retry_count, error_code, trace_id
  - ChatSession: session_id, user_id, insight_id, started_at, ended_at, status, handoff_required
  - ChatMessage: message_id, session_id, sender(user/agent/system), content, created_at, metadata(json)
- 저장소/보존/비고:
  - PostgreSQL (RDS/Aurora): 주요 메타데이터 저장, RawArticle 7일·ProcessedInsight 90일 보존
  - Local Filesystem Storage: 원문 스냅샷과 모델 출력 캐시 (`./var/storage` 또는 `LOCAL_STORAGE_ROOT`)
    - 디렉터리 구조: `{ticker}/YYYY/MM/DD/{article_id}.*`
    - 장기 보존은 S3 이전 전까지 로컬에 유지, 이후 S3 백엔드로 교체 예정
  - Redis/ElastiCache: 중복 검출(24h TTL), 파이프라인 상태 캐시, 채팅 세션 컨텍스트 임시 저장
  - 외부 API: DART 공시, News API 등 뉴스, SNS 공식 API, OpenAI API(LLM)
  - 민감 데이터 보호: 모든 토큰은 KMS/Secrets Manager 암호화, 로그에서 PII 제거

# 아키텍처 메모

- 데이터 수집 계층:
  - Celery Beat + Worker 기반 스케줄링, 소스 커넥터 모듈화(API 우선, 보조 크롤링/캐시)
  - Rate Limit 감시와 백오프 전략, 실패 이벤트 추적
- 분석 계층:
  - OpenAI 라이브러리로 LLM 호출, 프롬프트는 종목·기간·언어·금칙어 등을 매개변수화
  - `analysis.analyze` 작업은 TransientLLMError 발생 시 지터 백오프와 최대 3회 재시도
  - 기본 모델: GPT-4o-mini, 품질 요구 시 상위 모델 옵션 제공
  - 출력은 구조화(JSON)하고 trace_id·토큰/비용 메트릭을 기록
- 전달(게시) 계층:
  - Report Materializer가 `ProcessedInsight`를 읽어 웹 사용을 위한 뷰 모델과 캐시를 생성
  - Publish 작업은 DB에 `report_snapshot` 테이블(또는 ProcessedInsight 파생 뷰) 업데이트, 정적 자산은 `./var/storage`에 보관
  - 상태는 `JobRun(stage=publish)`에 기록하고, SLA 초과/실패는 Ops 알림으로 승격
- 웹 애플리케이션:
  - 프론트엔드(React 또는 Next.js)에서 구독 관리, 리포트 열람, 채팅 UI 제공
  - 백엔드( Python FastAPI 또는 Kotlin Spring Boot )가 인증, 리포트 조회, 채팅 브로커 역할 수행
  - 채팅은 WebSocket 또는 Server-Sent Events로 스트리밍 응답 지원, 에이전트는 OpenAI Assistants/Responses API를 활용
- 채팅 콘텍스트 관리:
  - 최근 N개 메시지를 Redis에 저장, 장기 대화는 ChatMessage 테이블에 기록
  - 인사이트/문서 링크는 grounding 정보로 제공, 민감 데이터 마스킹
- 파트너 연계:
  - Optional: 향후 Kotlin API 게이트웨이 도입 시 Python 서비스와 gRPC/REST 연동

# 제약 / 비기능 요구사항

- 성능/보안/접근성:
  - 수집 작업은 기본 1일 1회 + 온디맨드 실행 옵션, Rate Limit 준수 및 백오프 적용
  - 인증: Slack 대신 웹 기반 OAuth2/SSO, RBAC(일반 사용자/관리자)
  - 보안: 최소 권한 IAM, 네트워크 아웃바운드 제한, OpenAI 비용/토큰 감시
  - 접근성: WCAG 준수, 다크 모드 SHOULD, 다국어 UI NICE
  - 규제 준수: 데이터 보존 기간 준수, 사용자 데이터 삭제 요청 처리
- 로깅/에러 처리/관찰성:
  - 구조화 로깅(JSON)과 trace_id 전파, OpenTelemetry 기반 추적
  - 메트릭: 파이프라인 단계별 처리 시간, LLM 토큰/비용, 웹 응답 시간, 채팅 전환율
  - 알림: 실패 파이프라인, LLM 비용 초과, SLA 위반을 PagerDuty/Slack Ops 채널로 발송
  - Dead-letter Queue(SQS 등)로 영구 실패 보존 및 관리 콘솔에서 재처리

# 산출물

- 리포지토리 구조:
  - `/ingestion` (Python): 데이터 커넥터, 스케줄러, 전처리 로직
  - `/analysis` (Python): LLM 파이프라인(OpenAI), 프롬프트 템플릿, 모델/비용 관리, 출력 정규화
  - `/publish` (Python): 보고서 물리화 및 게시, 캐시 생성
  - `/web` (React/Next.js): 포털 UI, 채팅 컴포넌트, 인증 흐름
  - `/api` (Kotlin/Spring Boot 또는 Python FastAPI): 구독/리포트/채팅 API
  - `/infra`: IaC(Terraform/CloudFormation), 배포 파이프라인, 옵저버빌리티 구성
  - `/tests`: 단위/통합/계약 테스트
- README: 아키텍처 개요, 개발 환경 세팅(Docker-compose), 파이프라인 & 웹 앱 실행 절차
- `.env.example`: 외부 API 키, DB/Redis 연결, OpenAI 키, OAuth 클라이언트 정보 placeholder
- 시드/샘플 데이터: 티커 목록, 모의 기사 JSON, 예시 리포트 & 채팅 대화 로그
- 배포: GitHub Actions/Jenkins CI, Python 서비스는 Docker + ECS/Fargate(또는 Cloud Run), 웹은 Static hosting + CDN 또는 Next.js SSR 배포
