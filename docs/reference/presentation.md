# StockTeacher 5분 발표 자료

## 1. 한눈에 보는 프로젝트

| 항목        | 내용                                                                                      |
| ----------- | ----------------------------------------------------------------------------------------- |
| 미션        | 분 단위로 유통되는 주식/공시/SNS 뉴스를 모아 Slack 리포트로 요약 전달                     |
| 형태        | Python 기반 3단계 파이프라인(Ingestion → Analysis → Publish) + FastAPI + Next.js 대시보드 |
| 주요 데이터 | raw_articles(수집), processed_insights(LLM 요약), report_snapshot(Web/API 노출)           |
| 운영 환경   | Python 3.13+, Celery+Redis, PostgreSQL/SQLite, OpenAI API, Next.js 14                     |
| 현재 범위   | 뉴스 수집(NewsAPI), LLM 요약, 웹 포털 베타 UI / Slack 봇은 차후 확장                      |

## 2. 전체 아키텍처 개요

```mermaid
flowchart LR
    subgraph Sources
        NewsAPI[(NewsAPI)]
    end
    NewsAPI --> CollectTask
    subgraph Ingestion
        CollectTask[Collect Celery\ningestion/tasks/collect.py]
        Dedup[Redis/InMemory KeyStore]
        RawDB[(Postgres\nraw_articles)]
    end
    CollectTask --> Dedup --> RawDB
    RawDB --> AnalyzeTask
    subgraph Analysis
        AnalyzeTask[Analyze Celery\nanalysis/tasks/analyze.py]
        OpenAI[(OpenAI API)]
        Insights[(Postgres\nprocessed_insights)]
    end
    AnalyzeTask -->|Prompt| OpenAI -->|JSON| AnalyzeTask
    AnalyzeTask --> Insights
    Insights --> Materializer
    subgraph Publish & Delivery
        Materializer[publish/materializer.py]
        ApiDB[(report_snapshot)]
        FastAPI[api/routes.py]
        Web[Next.js UI]
        Slack[(Slack Bot\n(미도입))]
    end
    Materializer --> ApiDB --> FastAPI --> Web
    Materializer -->|JobRun 기록| RawDB

## 3. 데이터 파이프라인 흐름

sequenceDiagram
    participant Beat as Celery Beat
    participant Collect as collect_core
    participant Redis as RedisKeyStore
    participant RawDB as raw_articles
    participant Analyze as analyze_core
    participant OpenAI as OpenAI API
    participant Insights as processed_insights
    participant Materialize as materialize_reports
    participant API as FastAPI
    participant Web as Next.js

    Beat->>Collect: schedule(ticker, source)
    Collect->>Redis: fingerprint 조회
    Collect->>RawDB: 신규 기사 insert + JobRun
    Collect->>Analyze: (수동 혹은 Beat) 트리거
    Analyze->>RawDB: 최신 기사 조회
    Analyze->>OpenAI: 구조화 프롬프트 전송
    OpenAI-->>Analyze: JSON insight
    Analyze->>Insights: 저장 + JobRun
    Materialize->>Insights: 최신 insight 조회
    Materialize->>API: ReportSnapshot 생성
    Web->>API: REST 조회/챗 메시지 호출

## 4. 핵심 모듈 한줄 요약

- 수집(Celery): ingestion/tasks/collect.py:60의 collect_core가 커넥터 결과를 Redis/DB 이중 중복 제거 후 저장하고 JobRun으
  로 추적합니다. 스케줄러는 ingestion/celery_app.py:23가 구성합니다.
- 중복 제거: ingestion/services/deduplicator.py:31의 RedisKeyStore가 Redis NX set을 사용, 실패 시 메모리 백업으로 전환합
  니다.
- 설정/검증: ingestion/settings.py:78는 수집 스케줄 JSON을 파싱하고 중복 ticker/source를 차단합니다.
- LLM 분석: analysis/tasks/analyze.py:45는 최신 raw 기사 5건을 모아 OpenAI 호출, 비용 상한 및 JSON 재시도 로직은 analysis/
  client/openai_client.py:78에 구현됩니다.
- 게시물 생성: publish/materializer.py:18가 processed_insights를 report_snapshot으로 변환, 이미 게시된 insight는 건너뛰며
  JobRun(stage=deliver)을 남깁니다.
- API: api/routes.py:92는 보고서 목록을 sentiment 필터와 즐겨찾기 여부로 응답하고, 단순 챗봇 엔드포인트를 제공합니다.
- 웹 UI:
    - 구독 화면 web/app/subscriptions/page.tsx:21은 REST API를 호출해 구독 CRUD를 제공합니다.
    - 보고서 보드 web/components/ReportsBoard.tsx:27는 필터링/즐겨찾기 토글 및 상세 링크를 렌더링합니다.
    - 상세·챗 화면 web/app/reports/[insightId]/page.tsx:27는 insight 내용을 전시하고 3초 폴링 기반 챗 UI를 제공합니다.
- 관찰성: ingestion/utils/logging.py:40는 JSON/텍스트 로그 전환을 지원하며 trace_id를 공통 필드로 기록합니다.

## 5. 품질 & 테스트 현황

| 영역 | 커버리지 |
| --- | --- |
| Ingestion 회귀 | tests/ingestion/test_collect_task.py:58 (중복저장, 실패시 JobRun) |
| LLM 분석 | tests/analysis/test_analyze_task.py:93 (성공, 실패, 비용초과) |
| Publish | tests/publish/test_materializer.py:42 (스냅샷 생성·Idempotency·JobRun) |
| End-to-End | tests/api/test_reports_api.py:44 (Materializer → FastAPI → REST 검증) |
| 설정/스키마 | 각 Settings/ORM 테스트로 환경 변수·마이그레이션 보증 |

## 6. 운영 & 배포 고려사항

- 인프라: docker-compose.yml:2는 Redis와 Postgres를 기본으로 올리며, SQLite로도 개발 테스트 가능.
- JobRun 추적: ingestion/repositories/articles.py:31이 Stage/Status를 저장해 실패 샘플을 쉽게 찾음.
- LLM 비용 가드: analysis/client/openai_client.py:107에서 추정 비용이 상한 초과 시 PermanentLLMError를 발생.
- 웹/API 분리: API는 FastAPI(Uvicorn), 프런트는 Next.js standalone 빌드.

## 7. 발표 타임라인(5분)

| 구간 | 메시지 | 시각 자료 |
| --- | --- | --- |
| 0:00–1:00 | 문제 정의·미션, KPI | 1번 표 |
| 1:00–2:00 | 전체 아키텍처 & 핵심 기술 선택 | 아키텍처 다이어그램 |
| 2:00–3:00 | 단계별 데이터 흐름, JobRun 추적 | 시퀀스 다이어그램 |
| 3:00–4:00 | 코드 하이라이트(Collect/Analyze/Materialize) & 테스트 근거 | 코드 위치 + 테스트 표 |
| 4:00–5:00 | 운영 전략·로드맵·Q&A 준비 | 향후 단계 & 리스크 |

## 8. 로드맵 & Q&A 대비 포인트

- 로드맵: Slack Bot 연동, 다중 데이터 소스(RSS 재검토), LLM 가드레일/챗 고도화 (docs/web_application_plan.md, docs/
  ingestion/news_integration_plan.md).
- 리스크 대비
    1. 뉴스 Rate Limit 시 대응? → Redis 백오프 + 스케줄 JSON으로 신속 비활성화 (ingestion/tasks/collect.py:43, ingestion/
       settings.py:70).
    2. 비용 초과? → LLM 비용상한 예외 + JobRun 오류 기록.
    3. 데이터 품질? → 중복 해시, 언어/타이틀 trimming, 테스트 기반 마이그레이션 검증.

———
```
