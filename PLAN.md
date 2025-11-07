# Vector DB 통합 PLAN

## Problem 1-Pager
- **배경**: StockTeacher는 뉴스 수집→LLM 요약→웹/챗 전달 파이프라인을 제공하지만, 사용자가 유사 이슈 탐색이나 심화 질문을 할 때 재사용할 지식 기반이 부족하다.
- **문제**: 정적 DB 조회만으로는 연관 리포트 추천·후속 Q&A가 제한적이며, 분석 단계도 raw 기사 전체를 사용해 토큰 낭비가 발생한다.
- **목표**: Vector DB를 도입해 임베딩 기반 검색을 지원하고, 사용자 경험(추천/챗)과 분석 효율(RAG)을 향상시킬 수 있는 경로를 비교·선택한다.
- **비목표**: 현 단계에서는 Slack 봇 출시, 완전한 Guardrail 구축, 비용 청구 시스템 연동은 범위에서 제외한다.
- **제약**: LLM 비용 상한 유지, 기존 Celery JobRun 로깅 유지, 테스트 추가, 5분 이내 챗 응답 SLA 준수.

## 대안 비교

| 옵션 | 개요 | 장점 | 단점 | 주요 변경 지점 |
| --- | --- | --- | --- | --- |
| **Option A**<br/>리포트 추천 검색 | ProcessedInsight/RawArticle 임베딩을 Vector DB에 저장, REST/웹에서 유사 리포트 추천 | 사용자 추천·검색 즉시 가능, 챗/Slack 재활용 이점 | 임베딩 파이프라인/백필 필요, 추가 인프라 운영 | publish/materializer.py 이후 임베딩 큐; API 보고서 엔드포인트; 웹 UI 추천 섹션 |
| **Option B**<br/>분석 단계 RAG | Celery analyze_core 실행 시 Vector DB에서 기사 선택 후 프롬프트 구성 | 토큰 절감, Insight 품질 향상 | Celery 파이프라인 복잡도 증가, 재시도/에러 처리 위험 | analysis/tasks/analyze.py, analysis/prompts/templates.py, tests/analysis/* |
| **Option C**<br/>챗봇 RAG (선택안) | 챗 질문 임베딩→Vector 검색→LLM 응답 | 사용자 체감 효과 큼, API 레이어 변경, Slack/추천 기능 확장 쉬움 | LLM 응답/가드레일 신규 개발, Vector 인프라 운영 | api/routes.py 챗 핸들러, api/repositories.py, tests/api/test_reports_api.py, web/app/reports/[insightId]/page.tsx |

**결론**: Option C를 1순위로 진행한다. 변경 범위가 API/웹 레이어에 집중되어 리스크가 낮고, 구축된 벡터 인덱스는 Option A 확장에 재활용 가능하다. Option A는 C 구현 후 자연스럽게 파생 기능으로 고려하고, Option B는 파이프라인 안정화 이후 재검토한다.

## Option A 구현 시 변경 사항
1. **임베딩 파이프라인**
   - `publish/materializer.py` 또는 후속 비동기 작업에서 ProcessedInsight/RawArticle을 임베딩 → Vector DB 업서트.
   - 실패 시 재시도 큐(Celery beat or worker) 도입, JobRun(stage=deliver) 로그에 embedding_stage 추가.
2. **API 확장**
   - `api/routes.py`에 `/reports/{id}/related` 및 `/reports/search` 추가.
   - `api/repositories.py`에서 Vector 검색 결과를 받아 Postgres 정보 결합.
3. **웹 UI**
   - `web/components/ReportsBoard.tsx` 또는 `web/app/reports/[insightId]/page.tsx`에 “관련 리포트” 섹션 표시.
4. **테스트/관찰성**
   - `tests/api`에 추천 API 회귀 테스트.
   - Vector 호출 로그(쿼리, 매칭 score)와 실패 알림 추가.

## Option B 구현 시 변경 사항
1. **분석 Celery 파이프라인**
   - `analysis/tasks/analyze.py`에서 `_select_recent_articles` 대신 Vector 검색 결과를 사용.
   - 검색 실패 시 fallback(기존 로직)과 재시도 정책 조정.
2. **프롬프트/토큰 관리**
   - `analysis/prompts/templates.py`에서 retrieved snippet 기반 컨텍스트 구성, max_chars 조정.
   - `analysis/client/openai_client.py` 비용 상한 조정(기사 수 감소로 기대 비용 감소).
3. **설정/운영**
   - `analysis/settings.py`에 Vector 검색 토글 및 top_k 설정 추가.
4. **테스트**
   - `tests/analysis/test_analyze_task.py`, `test_openai_client.py`에 새 경로 추가.
   - Vector 검색을 Mocking한 회귀 테스트 필요.

## Option C(선택안) 실행 계획
1. **임베딩/업서트 파이프라인**
   - Option A 준비 중 일부를 공유: ProcessedInsight 저장 후 임베딩 큐 처리.
2. **챗 API RAG**
   - `api/routes.py` 챗 엔드포인트에서 질문 임베딩→Vector 검색→LLM 응답.
   - `api/repositories.py`에 Vector 검색 헬퍼/캐싱 추가.
   - 예상 LLM 비용/쿼리 로깅.
3. **웹/Slack 확장**
   - `web/app/reports/[insightId]/page.tsx` 챗 UI에서 RAG 응답 표시.
   - Slack 봇은 동일 API를 호출하도록 설계(후순위).
4. **검증**
   - RAG 성공/실패 E2E 테스트 작성.
   - 관찰성: Vector 검색 latency, 매칭 ID, LLM 토큰 로그.

