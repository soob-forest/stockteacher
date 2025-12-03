# DS-3: Chroma 기반 RAG 통합 TODO

## Problem 1-Pager
- 배경: DS-1(필터 확장), DS-2(관련 리포트)가 키워드/티커 조합만으로 탐색·추천을 제공해 관련도 한계가 있음. 채팅도 하드코딩/컨텍스트 부족. 벡터 기반 검색/컨텍스트 주입이 필요.
- 문제: 자연어 질의·관련 리포트·채팅 답변에서 문맥 일치율이 낮고, 긴급/핵심 리포트를 놓칠 수 있음.
- 목표: Chroma를 Vector DB로 도입해 (1) 검색/추천 품질 개선, (2) 채팅 RAG 컨텍스트 주입으로 답변 질 향상. 응답 지연은 검색/추천 p95 <200ms, 채팅 첫 토큰 <2s 유지.
- 비목표: 개인화/랭킹 학습, CTR 피드백 반영, 다국어 임베딩 최적화, 멀티 테넌시.
- 제약: 파일≤300LOC/함수≤50LOC, 외부 I/O는 경계층으로, OpenAI 임베딩 비용 상한 적용, anomaly 임계 기본 0.4 유지, 네트워크 호출/비밀 로깅 금지.

## 사용처
1) 검색: 자연어 질의 → 임베딩 → 벡터 검색 → 필터(티커/날짜/감성) 결합.  
2) 관련 리포트: 기준 리포트 임베딩으로 KNN 조회 → 티커 우선·키워드 교집합 보강 → 최대 3개.  
3) 채팅: 사용자 메시지 임베딩 → 상위 N개 리포트 컨텍스트 → 프롬프트 주입 후 스트리밍 응답.

## 설계 선택(Chroma)
- Vector DB: **Chroma** (컬렉션: `reports`). 필드: `insight_id`(pk), `ticker`, `published_at`, `keywords`, `embedding`, `anomaly_score`, `headline/summary_text`(메타). 메타 JSON은 최소화.
- 임베딩 모델: OpenAI text-embedding-3-small 우선, 토큰/비용 상한 설정. 대안으로 로컬 임베딩은 후속 검토.
- 하이브리드 정렬: 벡터 점수 + 티커 가중치(+0.2) + 키워드 교집합 보너스(+0.1) 단순 가중 합.

## 설계 세부
- 초기화: `scripts/init_chroma.py`(가칭)에서 컬렉션 생성, distance metric=cosine, dimension은 임베딩 모델에서 자동 감지. 존재 시 no-op, 없을 때만 생성. 헬스체크 엔드포인트는 `CHROMA_URL/api/v1/heartbeat` 호출.
- 임베딩 생성: `publish/materializer.py` 이후 후행 워커(`ingestion/tasks/embed.py` 또는 `analysis/tasks/embed.py` 신규)에서 ReportSnapshot을 읽어 요약+키워드 기반 텍스트를 임베딩. 중복 방지를 위해 insight_id로 이미 업서트된 경우 skip/update.
- 업서트: Chroma `add/update`를 insight_id 키로 idempotent 처리, 게시 롤백/숨김 시 `delete(ids=[insight_id])` 경로 제공.
- 조회: 검색/추천/채팅 모두 동일 컬렉션 `reports` 사용, `where` 필터로 날짜/티커 제한, `n_results` 기본 10(검색) / 3(추천) / 5(채팅 컨텍스트).

## TODO (작업 단위)
- 데이터 파이프라인
  - [ ] publish 완료 후 임베딩 생성 워커 추가(ProcessedInsight 요약/키워드 기반), 실패 시 DLQ/재시도.
  - [ ] Chroma 컬렉션 초기화 스크립트 작성(distance=cosine, collection=`reports`, dim 자동 감지).
  - [ ] 업서트/삭제 동작(idempotent) 구현: insight_id 단위 UPSERT, 게시 롤백 시 delete 경로 포함.
  - [ ] 임베딩/업서트 메트릭(토큰, 비용, 성공률) 로그/지표 추가.
- API
  - [ ] `/api/search` 신설 또는 `/api/reports` 확장: query(자연어), tickers[], date_from/to, limit/offset; 질의 임베딩 → Chroma 검색 → DB fetch → 하이브리드 정렬 적용.
  - [ ] `/api/reports/:id/related` 벡터 버전: 기준 리포트 임베딩으로 KNN, 티커 우선·키워드 보강, 최대 3개 반환; 응답 스키마에 distance/score 포함 여부 결정.
  - [ ] 채팅 컨텍스트 API/서비스: 메시지 임베딩 후 상위 N개 컨텍스트를 LLM 프롬프트 빌더로 전달(토큰 예산 적용).
  - [ ] 점수 통합/하이브리드 로직 함수화(테스트 가능) 및 환경 변수로 가중치 노출.
  - [ ] 오류/타임아웃 가드: Chroma 장애 시 키워드/티커 기반 폴백.
- 채팅 RAG
  - [ ] 채팅 메시지 임베딩 → Chroma 검색 → 상위 N개 컨텍스트 선택(토큰 예산 내 슬라이싱) → 시스템/사용자 프롬프트 주입.
  - [ ] 스트리밍 응답 경로에 컨텍스트 포함 및 비용 상한/타임아웃 유지.
  - [ ] 세션 캐시(Redis)와 RAG 결과 병합 규칙 정의 및 테스트.
- 웹(UI)
  - [ ] 검색 결과/필터 UI는 DS-1 필터와 결합, 벡터 결과 순위/거리 표시 여부 결정.
  - [ ] 리포트 상세 “관련 리포트” 섹션을 벡터 결과 기반으로 교체/보강, 빈 상태/에러 메시지 명시.
  - [ ] 채팅 UI에 컨텍스트 사용 안내/토큰 초과 메시지 표시.
- 테스트
  - [ ] 단위: 임베딩 생성, 점수 통합 함수, Chroma 클라이언트 래퍼(실제 로컬 Chroma 대상).
  - [ ] 통합: 검색/관련 리포트 API를 로컬 Chroma 테스트 컬렉션으로 매칭/비매칭/필터 결합 시나리오 검증.
  - [ ] 채팅 RAG: 세션 메시지 → 컨텍스트 주입 → 응답 포함 여부 모킹 테스트(LLM 호출은 모킹, Chroma는 로컬 인스턴스).
  - [ ] 부하: 벡터 검색 p95, 업서트 TPS, 채팅 동시 연결 샘플 부하 테스트 계획.
- 설정/운영
  - [ ] 환경 변수 정의: `CHROMA_URL`, `CHROMA_COLLECTION=reports`, `EMBEDDING_MODEL`, 가중치/상한값.
  - [ ] 헬스체크 및 장애 시 폴백 경로 로그/알림 설정.
  - [ ] 피처 플래그(RAG on/off, vector 추천 on/off)로 안전 롤아웃 및 롤백 전략 마련.

## 리스크 및 완화
- 비용 상승: 임베딩 배치 간격/토큰 상한 설정, 중복 업서트 방지.
- 품질 불안정: 티커/키워드 보강, 거리 임계치 적용, 폴백 유지.
- 운영 복잡도: 초기화 스크립트와 피처 플래그로 단계적 배포, 장애 시 즉시 키워드 기반으로 전환.
