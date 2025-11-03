# 제품 개요

- 문제/목표: 투자자가 구독한 종목의 하루치 언론·미디어·SNS 텍스트를 자동으로 수집·분석해 핵심 요약과 인사이트 리포트를 Slack으로 전달한다. 데이터 수집(완료) 이후 분석 단계는 OpenAI LLM을 활용해 요약·키워드·감성·이상 징후를 생성하며, 전체 파이프라인을 신뢰성 있게 자동화하는 것이 목표다.
- 핵심 사용 시나리오:
  1. 사용자가 Slack Slash Command 또는 모달에서 관심 종목을 구독·해지하거나 알림 빈도를 조정한다.
  2. 스케줄러가 1일 주기로 각 종목 관련 텍스트를 수집 API/크롤러를 통해 가져와 정제 큐에 적재한다.
 3. Python 분석 파이프라인이 텍스트를 정제한 뒤 OpenAI LLM을 호출하여 요약·키워드·감성·이상 징후를 생성한다.
  4. Slack 봇이 종목별 리포트를 채널/DM에 게시하고, 실패 시 관리자에게 알림을 전송한다.
- 성공 기준(KPI):
  - 일일 리포트 생성 성공률 ≥ 98%
  - 데이터 수집 완료 후 Slack 게시까지 지연 시간 ≤ 10분
  - 리포트 클릭률 또는 후속 질의 응답 비율 ≥ 30%
  - 파이프라인 오류/재시도율 ≤ 2%

# 기능 목록(MUST/SHOULD/NICE)

- MUST:
  - 종목 구독/해지 및 구독 현황 조회(Slack Slash Command·모달)
  - 언론/공시 API 연동과 SNS(예: Twitter/X) 데이터 수집
  - 텍스트 정제: 언어 감지, 중복 제거, URL·해시태그 정규화
  - LLM 기반 분석(OpenAI): 토픽/키워드 추출, 요약, 감성/이상 이벤트 감지
  - 요약 리포트 생성(핵심 요약, 메트릭, 원문 링크)
  - Slack 메시지/블록 키트 기반 리포트 게시 및 실패 알림
  - 파이프라인 상태 모니터링, 재시도, Dead-letter 처리
- SHOULD:
  - 종목별 알림 시간대·빈도 커스터마이즈
  - Kotlin + Spring Boot 기반 관리/설정 API 및 대시보드
  - 요약품질 검증(샘플링, 휴리스틱/간단 평가 프롬프트)과 수동 승인 플로우
  - 다국어(한국어/영어) 분석 및 언어별 모델 선택
  - Slack 내 후속 질의(예: “원문 링크 보여줘”)에 대한 간단한 Q&A
- NICE:
  - 개인화된 투자 성향 분석 및 리스크 경보
  - Email/Teams 등 추가 알림 채널 연동
  - 주간/월간 추세 리포트 자동화
  - 실시간 급등락 감지 후 즉시 알림
  - 심화 LLM 기반 자연어 질의응답(비용·규제 검토 필요)

# 화면/흐름(간단 시퀀스/상태)

- 페이지/컴포넌트:
  - Slack Slash Command 모달: 종목 검색, 구독/해지, 알림 설정
  - Slack 리포트 메시지: 요약 블록, 감성 그래프(이미지 혹은 ASCII), 주요 링크 버튼
  - 관리자 대시보드(웹, SHOULD): 파이프라인 상태, 큐 처리량, 실패 로그, 재처리 트리거
- 주요 상태/흐름:
  - 종목 구독: Pending Verification → Active → Suspended
  - 데이터 수집 단계: Scheduled → Fetching → Normalized → Ready → Failed(Retry)
  - 분석 단계: Queued → Processing → Completed → Failed(Retry)
  - 봇 전송 단계: Posting → Posted → Acknowledged → Failed(Manual Action)
  - 재시도/에스컬레이션: 재시도 한도 초과 시 관리자 Slack 채널/온콜 알림

# 데이터(간단 스키마 & 보존 정책)

- 엔티티/필드:
  - StockSubscription: subscription_id, user_id, ticker, alert_window, status, created_at, updated_at
  - RawArticle: article_id, source_type(press/api/sns), ticker, title, body, url, collected_at, language, sentiment_raw
  - ProcessedInsight: insight_id, ticker, summary_text, sentiment_score, keywords[], anomaly_score, source_refs[], generated_at, llm_model, llm_tokens_prompt, llm_tokens_completion, llm_cost
  - JobRun: job_id, stage(collect/analyze/deliver), status, started_at, ended_at, retry_count, error_code, trace_id
- 저장소/연동/비고:
  - PostgreSQL (RDS/Aurora): 정형 메타데이터와 구독 정보 저장, RawArticle 7일, ProcessedInsight 90일 보존
  - Local Filesystem Storage: 원문 스냅샷과 모델 피처를 프로젝트 디렉토리 내에 저장
    - 기본 경로: `./var/storage` (환경변수 `LOCAL_STORAGE_ROOT`로 변경 가능)
    - 디렉토리 구조 예: `{ticker}/YYYY/MM/DD/{article_id}.*` (원문/스냅샷/메타데이터)
    - S3 도입 전까지 로컬 보관을 기준으로 설계하며, 추후 S3 전환 시 경로 어댑터로 대체
  - Redis/ElastiCache: 중복 검출 키(24h TTL), 파이프라인 큐 관리
  - 외부 API: 공시/뉴스 제공자(DART, News API 등), SNS 공식 API 혹은 합법적 RSS, OpenAI API(LLM)
  - 민감 데이터 보호: 사용자 토큰은 KMS/Secrets Manager로 암호화, 로그 내 PII 제거

# 아키텍처 메모

- 데이터 수집 단계:
  - Python 워커(Celery Beat + Worker)로 스케줄링, 소스별 커넥터 모듈화(API 우선, 보조 스크래핑 시 백오프·캐시 적용)
  - 로그/메트릭: 소스별 처리량, 실패율, Rate Limit 이벤트 추적
  - 대안 비교
    1. API 우선 접근: 안정적이고 저작권 준수, 비용·커버리지 제약
    2. 웹 스크래핑 병행: 다양한 소스 커버, 차단·유지보수 리스크
  - 결론: 핵심 언론/공시는 API 사용, SNS는 공식 API 또는 RSS, 스크래핑은 보조 채널로 제한
- 분석 단계:
  - OpenAI 라이브러리를 활용한 LLM 호출 기반 파이프라인: 텍스트 정제 → 프롬프트 구성 → OpenAI Chat Completions 호출 → 요약/키워드/감성/이상 이벤트 추출 → 결과 정규화/저장

  - 쿠/재시도: Celery 공유 태스크를 `analysis.analyze` 큐에 배치하고 `TransientLLMError`는 backoff+jitter 기반으로 최대 3회 자동 재시도, 비용 한도 초과 등 영구 오류는 즉시 실패 처리.
  - 모델 전략 대안
    1. GPT-4o-mini(또는 동급): 비용 효율적, 속도 우수, 복잡 과제 한계 가능
    2. GPT-4.1 계열: 품질 우수, 비용↑, 지연시간↑
  - 결론: 초기엔 비용 대비 품질이 우수한 소형 모델(예: gpt-4o-mini) 우선 적용, 품질 요구가 높은 섹션에 한해 상위 모델을 선택적으로 사용(스위치/플래그)하고 토큰/비용 상한선을 강제한다.
  - 프롬프트 설계: 종목·기간·언어·톤을 매개변수화하고, 안전 가이드라인 및 금칙어(PII/과도한 확신 등) 포함. 시스템/유저 메시지 분리, 함수호출/구조화 출력(JSON) 우선.
  - 관찰성: trace_id 전파, 모델/토큰/비용 지표 기록, 로그 이벤트(`analyze.start`, `analyze.saved`, `analyze.transient_error`, `analyze.permanent_error`, `analyze.unexpected_error`) 및 JobRun(stage=analyze, source=openai) 상태로 흐름을 추적하고 프롬프트/응답 샘플은 PII 제거 후 제한적으로 보관(옵션).
- 봇 시스템 단계:
  - Python Slack Bolt 앱으로 MVP 구성, Celery 결과를 Slack 메시지로 변환
  - 확장 대안
    1. Python 단일 앱: 구현이 단순, 대시보드/API 기능 확장성 제한
    2. Kotlin Spring Boot API 게이트웨이 추가: 타입 안정성·관리 UI 제공, 복잡도·운영비 증가
  - 결론: 초기엔 Python 중심으로 구축, 관리/대시보드 필요 시 Spring Boot API 모듈 추가하여 Slack → Kotlin → Python REST/gRPC 호출 구조 확장
- 오케스트레이션 대안:
  1. Airflow DAG: 스케줄·모니터링 내장, 인프라 무겁고 운영 비용 높음
  2. Celery Beat/Worker: 경량, Python 생태계 친화, 복잡한 DAG 표현 한계
  - 결론: 현재 요구(일일 파이프라인, 재시도 중심)에 맞춰 Celery 채택, 확장 시 Airflow 전환 검토

# 제약/비기능 요구사항

- 성능/보안/접근성:
  - 수집 작업은 기본 1일 1회, 시장 이벤트 대응을 위한 온디맨드 실행 옵션 고려
  - API Rate Limit 준수: 지수 백오프, 캐시, 장애 시 최대 3회 재시도
  - 보안: OAuth/토큰 KMS 보관, 네트워크 아웃바운드 제한, 최소 권한 IAM, OpenAI API 키 비밀 관리 및 권한 최소화
  - 접근 제어: Slack 워크스페이스 화이트리스트, 관리자 역할 기반 설정, 웹 대시보드는 OAuth2/SSO 적용
  - 규정 준수: 뉴스 라이선스, SNS 이용 약관 준수, 저작권 고려해 Raw 데이터 보존 기간 제한
- 로깅/에러 처리/관찰성:
  - 구조화 로깅(JSON) + trace_id 전파, CloudWatch/ELK와 연동
  - 메트릭: 파이프라인 단계별 처리량, 실패율, 지연시간 + LLM 호출 횟수/토큰/비용(CloudWatch/Prometheus)
  - 알림: 실패율 임계치, Slack 전송 실패, LLM 비용·토큰 임계 초과 시 PagerDuty/Slack Alert
  - Dead-letter Queue(SQS DLQ 예상)로 실패 이벤트 보존, 관리 UI/CLI로 재처리 지원

# 산출물

- repo 구조:
  - `/ingestion` (Python): 소스 커넥터, 스케줄러, 정제 로직
  - `/analysis` (Python): LLM 파이프라인(OpenAI), 프롬프트 템플릿, 모델/비용 관리, 출력 정규화
  - `/bot` (Python): Slack Bolt 앱, 메시지 템플릿, 에러 핸들러
  - `/api` (Kotlin/Spring Boot, 선택): 구독/알림 설정 API, 관리자 대시보드 백엔드
  - `/infra`: IaC(Terraform/CloudFormation), 배포 스크립트, Observability 구성
  - `/tests`: 단위/통합/계약 테스트, 샘플 데이터
- README: 아키텍처 개요, 개발 환경 셋업(Docker-compose), 파이프라인 구동/테스트/배포 절차
- `.env.example`: Slack 토큰, 외부 API 키, DB/Redis 접속 정보, OpenAI 키(OPENAI_API_KEY) placeholder 및 설명
- Seed/샘플 데이터: 테스트용 티커 목록, 모의 기사 JSON, 예시 Slack 리포트 템플릿
- 배포: GitHub Actions/Jenkins 파이프라인, Python 서비스는 Docker + ECS/Fargate(또는 Cloud Run), Spring Boot는 Jar/Docker 배포. Slack App 매니페스트 및 설정 문서 포함.
