# StockTeacher 문서

StockTeacher는 주식 종목의 뉴스/공시를 수집·분석하여 웹 포털에서 리포트를 제공하는 시스템입니다. 이 문서 디렉토리는 프로젝트의 아키텍처, 운영, 테스트 전략, 의사결정 로그를 포함합니다.

## 시작하기

- **프로젝트 README**: [../README.md](../README.md)
- **아키텍처 개요**: [ARCHITECTURE.md](./ARCHITECTURE.md) - 시스템 전체 구조 및 기술 스택
- **운영 가이드**: [OPERATIONS.md](./OPERATIONS.md) - 로컬 개발 및 배포 절차
- **빠른 시작**: ../README.md의 "빠른 시작" 섹션 참조

## 주요 문서

### 시스템 설계
- [ARCHITECTURE.md](./ARCHITECTURE.md) - 전체 아키텍처, 데이터 흐름, 계층별 설계
- [DECISIONS.md](./DECISIONS.md) - 아키텍처 의사결정 로그 (ADR)
- [ROADMAP.md](./ROADMAP.md) - 프로젝트 로드맵 및 마일스톤

### 개발 가이드
- [OPERATIONS.md](./OPERATIONS.md) - 서비스 기동, 모니터링, 장애 대응
- [TESTING.md](./TESTING.md) - 테스트 전략 및 실행 방법

## 모듈별 문서

StockTeacher는 5개 주요 모듈로 구성됩니다:

### [Ingestion (데이터 수집)](./ingestion/README.md)
Celery 기반 스케줄러로 뉴스/공시/SNS 데이터를 수집하고 정규화합니다.

- [아키텍처 개요](./ingestion/architecture.md)
- [데이터 수집 구현 계획](./ingestion/data-collection-plan.md)
- [뉴스 통합 계획](./ingestion/news-integration-plan.md)

### [Analysis (데이터 분석)](./analysis/README.md)
OpenAI LLM을 활용하여 수집된 텍스트를 분석하고 인사이트를 생성합니다.

- [분석 구현 계획](./analysis/analysis-plan.md)

### [Web (웹 애플리케이션)](./web/README.md)
Next.js 기반 사용자 포털과 FastAPI 백엔드를 제공합니다.

- [웹 애플리케이션 구현 계획](./web/web-application-plan.md)
- [E2E 테스트 계획](./web/web-e2e-tests-plan.md)
- [서버 실행 스크립트 계획](./web/server-scripts-plan.md)

### [API](./api/README.md)
FastAPI 기반 REST API와 WebSocket 채팅 인터페이스를 제공합니다.

### [Publish (게시)](./publish/README.md)
ProcessedInsight를 웹/Slack으로 전달하기 위한 ReportSnapshot을 생성합니다.

## 참고 자료

- [Python 라이브러리 가이드](./reference/python-libraries.md) - 프로젝트에서 사용하는 Python 패키지 설명
- [발표 자료](./reference/presentation.md) - 5분 프로젝트 개요 발표 자료

## 문서 구조

```
docs/
├── README.md (이 파일)
├── ARCHITECTURE.md (시스템 아키텍처)
├── DECISIONS.md (의사결정 로그)
├── OPERATIONS.md (운영 가이드)
├── TESTING.md (테스트 전략)
├── ROADMAP.md (로드맵)
│
├── ingestion/ (데이터 수집 모듈)
├── analysis/ (데이터 분석 모듈)
├── web/ (웹 애플리케이션 모듈)
├── api/ (API 모듈)
├── publish/ (게시 모듈)
└── reference/ (참고 자료)
```

## 문서 작성 가이드

### 새 문서 추가 시
1. 모듈 관련 문서는 해당 모듈 디렉토리에 배치
2. 모듈 README.md 업데이트 (문서 목록 추가)
3. 필요 시 이 README.md에 링크 추가

### 의사결정 발생 시
1. DECISIONS.md에 새 ADR 추가 (ADR-XXX 포맷)
2. 관련 모듈 README에서 링크

### 아키텍처 변경 시
1. ARCHITECTURE.md 업데이트
2. 영향받는 모듈 README 확인 및 업데이트
3. DECISIONS.md에 변경 사유 ADR 작성

## 관련 링크

- [프로젝트 README](../README.md)
- [코딩 규칙 (CLAUDE.md)](../CLAUDE.md)
- [개발 환경 설정](../README.md#빠른-시작)
- [기여 가이드](../README.md#기여)
