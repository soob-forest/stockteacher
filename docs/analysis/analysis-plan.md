# 분석 구현 계획 (OpenAI LLM)

## Problem 1-Pager
- 배경: 수집 파이프라인이 RawArticle을 안정적으로 적재한다. 이제 분석 단계에서 종목별 텍스트를 요약/키워드/감성/이상 징후로 구조화해 ProcessedInsight로 저장하고, 이후 Slack 리포트에 활용해야 한다.
- 문제: LLM 호출을 안전하고 예측 가능한 비용/지연으로 운영하며, 결과를 일관된 스키마로 저장하는 표준 경로가 없다.
- 목표: OpenAI 라이브러리 기반 LLM 분석 파이프라인을 구현한다. 프롬프트/모델/토큰 상한/비용 측정/관찰성(trace_id)/리트라이를 포함해 결정적 테스트 가능하도록 구성한다.
- 비목표: 고급 랭킹/재랭크/멀티에이전트 오케스트레이션, 장기 메모리, 모델 미세조정.
- 제약: 파일 ≤ 300 LOC, 함수 ≤ 50 LOC, 매개변수 ≤ 5, 순환 복잡도 ≤ 10. 외부 I/O는 경계층(클라이언트 래퍼/리포지토리/태스크)로 격리. 민감값 로깅 금지. 테스트는 네트워크 없이 Fake Provider로 결정적이어야 한다.

## 대안 비교(요약)
- 출력 파싱
  - Option A: LLM 구조화(JSON 스키마/함수 호출) — 장점: 안정 파싱, 단점: 프롬프트 제약, 위험: 모델 호환성.
  - Option B: 프리텍스트+정규식 파싱 — 장점: 유연성, 단점: 취약, 위험: 포맷 흔들림.
  - 선택: Option A(구조화 JSON) 우선, 파서 방어 로직 추가.
- 호출 전략
  - Option A: 단일 프롬프트로 종합 출력 — 장점: 비용/지연 최소, 단점: 길이/품질 트레이드오프.
  - Option B: 모듈별(요약/키워드/감성/이상) 분리 — 장점: 품질/제어, 단점: 비용 증가.
  - 선택: Option A 기본, 품질 이슈 구간만 옵션 B로 확장 가능하도록 훅 유지.
- 모델 선택
  - Option A: gpt-4o-mini — 비용 효율/속도. Option B: gpt-4.1 — 고품질(비용↑). 스위치 가능하도록 설정화.

## 실행 계획(체크리스트)
- [x] Step A — 분석 Settings 정의(OPENAI_API_KEY, 모델, 최대 토큰/비용 상한, 타임아웃, 재시도, 언어/톤 설정). 단위 테스트.
- [x] Step B — DTO/스키마 정의(AnalysisInput, AnalysisResult; summary, keywords[], sentiment_score, anomalies[], llm_model, tokens_prompt, tokens_completion, cost).
- [x] Step C — 프롬프트 템플릿과 프롬프트 빌더(입력 정규화/언어/톤/길이 제한). 결정적 테스트.
- [x] Step D — OpenAI 클라이언트 래퍼(재시도/타임아웃/관찰성/비용 추적/구조화 출력 파서). Fake Provider 기반 테스트.
- [x] Step E — 리포지토리/마이그레이션(ProcessedInsight 저장, llm_* 메타 저장). 스모크 테스트.
- [x] Step F — Celery 태스크(analyze_articles_for_ticker): 배치/청크/레이트 제한, JobRun 기록, 에러/재시도. 성공/실패 경로 테스트.
- [x] Step G — README/Runbook 업데이트(OPENAI 설정, 비용 상한, 운영 체크리스트) 및 SPEC 반영 검토.

## 설계 개요
- 모듈 구성(초안)
  - analysis/settings.py — OpenAI/분석 설정 로딩 및 검증
  - analysis/models/domain.py — DTO/스키마
  - analysis/prompts/templates.py — 템플릿(시스템/유저), 다국어/톤/길이 파라미터화
  - analysis/client/openai_client.py — OpenAI 호출 래퍼(구조화 JSON, 재시도, 시간/토큰/비용 기록)
  - analysis/services/analyzer.py — 입력 준비(청크/필터) → 클라이언트 호출 → 결과 통합
  - analysis/repositories/insights.py — ProcessedInsight 저장(ORM 사용)
  - analysis/tasks/analyze.py — Celery 태스크(큐/동시성/레이트 제한)

- 데이터 흐름
  1) 수집 완료된 RawArticle 조회(티커·기간). 2) 길이/언어 정규화 및 청크. 3) OpenAI 호출(구조화 JSON 기대). 4) AnalysisResult 정규화. 5) DB 저장. 6) JobRun/로그/메트릭 기록.

## 테스트 전략
- 단위 테스트: 설정 파싱(필수키, 기본값), 템플릿 빌더(파라미터 반영), 클라이언트 래퍼(Fake Provider로 재시도/타임아웃/구조화 파싱), 서비스(청크/집계), 리포지토리(ORM round-trip), 태스크(JobRun 상태).
- 통합 테스트(네트워크 없음): Fake OpenAI Provider로 end-to-end(입력→분석→저장) 시나리오.
- 실패/경계: 토큰 초과/비용 상한 초과/구조화 파싱 실패/빈 입력/로케일 미스매치/동시성으로 인한 재시도.

## 리스크 & 대응
- 비용/토큰 급증: 상한선(요청/일간) 적용, 초과 시 즉시 실패+경보.
- 구조화 파싱 실패: 스키마 검증 + 재프롬프트 1회, 실패 시 원문과 함께 JobRun 실패 기록.
- 지연시간: 청크 크기/동시성 제한, Batch API 고려(후속).
- 민감 정보/규정: OPENAI_API_KEY 비밀 관리, PII 마스킹, 로깅 시 프롬프트/응답 샘플 보관 금지(옵션으로 해시/길이만 기록).

## 운영 체크리스트
- [ ] OPENAI_API_KEY 설정 및 권한 검증(조직/프로젝트 스코프)
- [ ] 모델/온도/최대 토큰/비용 상한 설정 확인
- [ ] 레이트 제한/재시도 정책 점검
- [ ] 로그/메트릭 대시보드: 호출 수, 토큰, 비용, 실패율
- [ ] 이상 증가 시 프롬프트/청크 크기/동시성 조정

## API/설정 초안
- 환경 변수
  - `OPENAI_API_KEY` — 필수
  - `ANALYSIS_MODEL` — 기본 `gpt-4o-mini`
  - `ANALYSIS_MAX_TOKENS` — 기본 512
  - `ANALYSIS_TEMPERATURE` — 기본 0.2
  - `ANALYSIS_COST_LIMIT_USD` — 요청당 비용 상한(기본 0.02)
  - `ANALYSIS_REQUEST_TIMEOUT_SECONDS` — 기본 15
  - `ANALYSIS_RETRY_MAX_ATTEMPTS` — 기본 2
  - `DEFAULT_LOCALE` — ko_KR

## 산출물
- 코드: analysis/* 스켈레톤 + 테스트
- 마이그레이션: ProcessedInsight에 llm_* 컬럼 추가(토큰/모델/비용)
- 문서: README, SPEC, Runbook(분석 섹션) 업데이트
