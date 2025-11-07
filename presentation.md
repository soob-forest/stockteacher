# StockTeacher 설명

## 1. 프로젝트 개요

| 항목        | 내용                                                                                                                     |
| ----------- | ------------------------------------------------------------------------------------------------------------------------ |
| 미션        | 주식/공시/SNS 뉴스를 분 단위로 수집·요약해 Slack 리포트와 웹 포털로 전달                                                 |
| 형태        | Python 기반 3단계 파이프라인(Ingestion → Analysis → Publish) + FastAPI API + Next.js 대시보드 + Vector DB 기반 검색/챗봇 |
| 주요 데이터 | raw_articles(수집 원문), processed_insights(LLM 요약), report_snapshot(웹/챗 노출), insight_embeddings(Vector DB)        |
| 운영 환경   | Python 3.13+, Celery, Redis, PostgreSQL, Vector DB(chroma 등), OpenAI API, Next.js 14                                    |
| 현재 범위   | NewsAPI 기반 뉴스 수집, LLM 요약, 웹 포털/챗 MVP + Vector DB 도입으로 추천·RAG 챗 지원                                   |

## 2. 아키텍처

```mermaid
flowchart LR
    subgraph Sources
        NewsAPI[(NewsAPI)]
    end
    NewsAPI --> CollectTask
    subgraph Ingestion
        CollectTask[Collect]
        Dedup[Redis/InMemory KeyStore]
        RawDB[(Postgres
                    raw_articles)]
    end
    CollectTask --> Dedup --> RawDB
    RawDB --> AnalyzeTask
    subgraph Analysis
        AnalyzeTask[Analyze]
        OpenAI[(OpenAI API)]
        Insights[(Postgres
                    processed_insights)]
    end
    AnalyzeTask -->|Prompt| OpenAI -->|JSON| AnalyzeTask
    AnalyzeTask --> Insights
    Insights --> Materializer
    subgraph Publish & Delivery
        Materializer[Materialize]
        EmbedWorker[Embedding Worker / vector_upsert]
        ApiDB[(report_snapshot)]
        VectorDB[(Vector DB)]
        FastAPI[Api]
        Web[Next.js UI]
    end
    Materializer --> ApiDB --> FastAPI --> Web
    Insights --> EmbedWorker --> VectorDB
    FastAPI -->|semantic query| VectorDB
```

## 3. 데이터 파이프라인 & 챗봇 RAG 흐름

```mermaid
sequenceDiagram
    participant Beat as Celery Beat
    participant Collect as collect_core
    participant Redis as RedisKeyStore
    participant RawDB as raw_articles
    participant Analyze as analyze_core
    participant OpenAI as OpenAI API
    participant Insights as processed_insights
    participant Materialize as materialize_reports
    participant Embed as Embedding Worker
    participant Vector as Vector DB
    participant API as FastAPI
    participant Web as Next.js

    Beat->>Collect: schedule(ticker, source)
    Collect->>Redis: fingerprint 조회
    Collect->>RawDB: 신규 기사 insert + JobRun(stage=collect)
    Collect->>Analyze: 트리거 혹은 schedule
    Analyze->>RawDB: 최신 기사 조회
    Analyze->>OpenAI: 구조화 프롬프트 전송
    OpenAI-->>Analyze: JSON insight
    Analyze->>Insights: 저장 + JobRun(stage=analyze)
    Materialize->>Insights: 최신 insight 조회
    Materialize->>API: ReportSnapshot 생성 (JobRun stage=deliver)
    Materialize->>Embed: 새 insight 알림
    Embed->>Vector: 임베딩 업서트

    Web->>API: 챗 질문 제출
    API->>Vector: 관련 insight 검색(top_k)
    Vector-->>API: 유사도 결과 + 메타데이터
    API->>OpenAI: 컨텍스트 포함 답변 요청(RAG)
    OpenAI-->>API: 챗 응답
    API-->>Web: 답변 + 근거 링크 반환
```
