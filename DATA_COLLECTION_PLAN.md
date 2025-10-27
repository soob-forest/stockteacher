# 데이터 수집 구현 계획

## Problem 1-Pager
- **배경**: SPEC.md 기반 Slack 주식 리포트 봇은 신뢰할 수 있는 공시·뉴스·SNS 데이터 파이프라인이 필요하다.
- **문제**: 현재 종목별 정기 수집, 중복 제거, 실패 복구 체계가 없어 다운스트림 분석이 불안정하다.
- **목표**: Celery 기반 스케줄링/작업, 공시/뉴스 + SNS 커넥터, 정규화·중복 제거, PostgreSQL 저장, 관찰성(구조화 로그·JobRun)까지 포함한 MVP를 제공한다.
- **비목표**: 분석/리포트, 스트리밍 알림, 대규모 오케스트레이션(Airflow 등), 유료 API 통합은 범위 밖이다.
 - **제약**: Python + Celery Beat/Worker, Redis/PostgreSQL/로컬 파일 시스템 저장소(로컬은 docker-compose 볼륨 사용), 환경변수 기반 시크릿, 파일 ≤300 LOC, 함수 ≤50 LOC, 사이클로매틱 ≤10, 새 코드에는 결정적 테스트를 작성한다.

## 대안 비교
- **공시/뉴스 커넥터**
  - Option A: NewsAPI 등 공식 API 사용 — 장점: 응답 포맷 안정, 빠른 MVP; 단점: 쿼터 한계, 유료 전환 가능; 위험: rate limit 시 작업 지연.
  - Option B: RSS/스크래핑 — 장점: 비용 저렴; 단점: 포맷 불안정, 차단 가능; 위험: HTML 변경으로 빈번한 고장.
  - **선택**: Option A 기반 구현, Option B는 예비 모듈로 인터페이스만 준비.
- **Schema 관리**
  - Option A: SQLAlchemy + Alembic — 장점: 명시적 마이그레이션, 장기 유지 용이; 단점: 초기 설정 부담; 위험: 번거로운 부트스트랩.
  - Option B: 경량 ORM 자동 생성 — 장점: 빠른 시작; 단점: 스키마 통제 어려움; 위험: 스키마 드리프트.
  - **선택**: Option A 채택.

## 실행 계획
- [x] Step 1 — ingestion/ 구조와 Celery 진입점 요구사항 정리, 관련 코드/설정 전체 리딩으로 영향 범위 파악.
- [x] Step 2 — 설정 모듈(pydantic 기반)과 Celery Beat/Worker 초기화 코드 작성, 설정 단위 테스트.
- [x] Step 3 — SQLAlchemy 모델(RawArticle, JobRun)과 Alembic 베이스라인 마이그레이션 작성, 마이그레이션 검증 테스트.
- [x] Step 4 — 커넥터 추상화 및 News API + RSS 커넥터 구현, 응답 정규화·재시도/중복 방지 유닛 테스트.
- [x] Step 5 — 수집 태스크(Celery) 및 JobRun 기록 로직 구현, Redis/DB 기반 중복 제거 로직 테스트.
- [ ] Step 6 — 구조화 로깅/메트릭 훅 추가, docker-compose/README/Runbook 갱신과 운영 체크리스트 작성.

## 리스크 & 대응
- **Rate Limit 초과**: 지수적 백오프 + 캐시, 실패 시 JobRun 기록과 알림 훅으로 모니터링.
- **데이터 포맷 변경**: 커넥터 버전 관리와 스키마 검증 테스트 도입.
- **중복 데이터**: Redis 키 + DB unique 제약 이중 방어, 해시 전략 문서화.
- **비밀 관리**: 환경변수/시크릿 매니저 사용, 로그에는 민감 정보 제거.

## 완료 체크
- [ ] 모든 체크 항목 완료 후 최종 검토 및 사용자 보고.
