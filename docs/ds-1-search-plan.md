# DS-1: 검색 필터 확장 계획

## 목표
- 리포트 검색/필터를 티커+키워드+날짜 범위+감성+즐겨찾기/긴급 토글로 확장해 탐색성을 높인다.

## 범위
- 포함: API 쿼리 파라미터 확장, UI 필터 컴포넌트 개선, 긴급 필터(이상 점수 임계) 추가.
- 제외: Vector 검색/RAG, 자동 추천(별도 DS-2), 정렬 옵션(후속 검토).

## 요구사항
1) 필터 파라미터: tickers(복수), keywords(복수), date_from/date_to, sentiment(positive/neutral/negative), favorites_only, urgent_only(이상 점수 ≥ 임계).
2) 기본 동작: 필터 미지정 시 기존 목록과 동일. 긴급 필터는 anomaly_score >= 0.4(설정 가능) 기준.
3) UI: 다중 선택/토글 제공, 필터 배지 표시, “필터 초기화” 버튼.
4) 퍼포먼스: 기본 DB 인덱스(published_at, ticker) 활용, 필터 결합 시에도 p95 < 500ms 목표.

## 태스크
- [x] API: 쿼리 파라미터 확장 및 서버측 필터 로직 추가, anomaly_score 임계 설정(기본 0.4).
- [x] UI: 필터 컴포넌트 다중 선택/범위 입력/토글 추가, 상태 표시.
- [x] 테스트: 조합 필터(티커+감성+날짜) 결과 검증, 긴급 필터 시 anomaly_score 조건 확인.

## 리스크
- 인덱스 미비 시 쿼리 지연 → ticker/published_at/anomaly_score에 인덱스 점검.
- 키워드 검색은 단순 포함 검색으로 정확도 한계 → 사용자 기대 관리(툴팁/설명).

## 구현 메모 (2025-02)
- API: `tickers[]`, `keywords[]`, `date_from/to`, `urgent_only`(anomaly_score≥0.4), `favorites_only`, `sentiment`를 조합 필터로 지원. 키워드 필터는 교집합 매칭, 검색(term)은 티커/헤드라인/태그 부분 일치.
- UI: 티커/키워드 쉼표 입력, 날짜 범위, 긴급 토글, 배지/초기화 버튼 추가.
- 테스트: 확장 필터 경로 회귀 테스트 추가 (`tests/api/test_reports_api.py::test_reports_endpoint_supports_extended_filters`).
