# Publish (게시) 모듈

## 개요

ProcessedInsight를 웹/Slack으로 전달하기 위한 ReportSnapshot을 생성합니다.

## 주요 기능

- **Materializer**: ProcessedInsight → ReportSnapshot 변환
- **Idempotency**: 중복 게시 방지
- **아티팩트 관리**: 이미지/PDF 링크 관리
- **SLA 모니터링**: 10분 이내 게시 목표
- **JobRun 추적**: stage=publish, 성공/실패 기록

## 주요 파일

| 파일 | 설명 | 주요 함수 |
|-----|------|---------|
| `publish/materializer.py:18` | ReportSnapshot 생성 | `materialize_reports()` |

## 데이터 흐름

```
1. materialize_reports() → 미게시 ProcessedInsight 조회
2. 변환 → ReportSnapshot 생성
   - insight_id (복사)
   - ticker, headline, summary_text
   - sentiment_score, anomaly_score
   - tags, keywords (가공)
   - source_refs, attachments
   - published_at (현재 시각)
3. DB 저장 → report_snapshot 테이블
4. 정적 자산 → ./var/storage 보관 (선택)
5. JobRun → stage=publish, status=SUCCESS/FAILED
```

## ReportSnapshot 스키마

### DB 테이블 (report_snapshot)
- `insight_id` (PK, FK → processed_insights)
- `ticker`: 종목 코드
- `headline`: 제목 (summary_text 첫 줄 추출)
- `summary_text`: 요약
- `sentiment_score`: 감성 점수
- `anomaly_score`: 이상 징후 점수 (최대값)
- `tags`: 태그 배열 (감성 기반 자동 생성)
- `keywords`: 키워드 배열
- `source_refs`: 원문 참조 배열
- `attachments`: 첨부 파일 배열 (향후)
- `published_at`: 게시 시각

### 변환 규칙
- `headline`: summary_text의 첫 줄 (최대 200자)
- `tags`: sentiment_score 기반
  - >0.3: ["긍정"]
  - <-0.3: ["부정"]
  - 그 외: ["중립"]
- `anomaly_score`: anomalies 배열의 최대 score

## 실행 방법

### 수동 실행
```bash
uv run -- python -c "from publish.materializer import materialize_reports; materialize_reports()"
```

### Celery 통합 (향후)
```bash
# Celery Beat 스케줄에 추가
# 예: 5분마다 materialize_reports 실행
```

## Idempotency 보장

### 중복 게시 방지
- `report_snapshot.insight_id`가 이미 존재하면 건너뜀
- `INSERT ... ON CONFLICT DO NOTHING` 사용 (PostgreSQL)
- 또는 사전 조회 후 존재하면 스킵

### 재실행 안전
- 동일 ProcessedInsight를 여러 번 materialize 해도 안전
- JobRun은 매번 새로 생성 (실행 이력 추적)

## SLA 모니터링

### 목표
- 수집 완료 → 웹 게시: 10분 이내

### 추적 방법
```sql
-- SLA 위반 조회
SELECT
  pi.ticker,
  pi.generated_at,
  rs.published_at,
  EXTRACT(EPOCH FROM (rs.published_at - pi.generated_at)) AS seconds_diff
FROM processed_insights pi
JOIN report_snapshot rs ON pi.id = rs.insight_id
WHERE EXTRACT(EPOCH FROM (rs.published_at - pi.generated_at)) > 600;
```

### SLA 초과 시
- JobRun에 `sla_breach=true` 플래그 기록
- Ops 알림 발송 (PagerDuty/Slack)
- 수동 개입 필요

## 테스트

### 단위 테스트
```bash
uv run -- python -m pytest tests/publish/test_materializer.py
```

### 주요 테스트 케이스
```python
def test_materialize_reports_creates_snapshot():
    """ReportSnapshot 생성 검증."""
    # Given: ProcessedInsight 1건
    # When: materialize_reports() 실행
    # Then: ReportSnapshot 저장, JobRun SUCCESS

def test_materialize_reports_idempotent():
    """중복 게시 방지 검증."""
    # Given: 동일 ProcessedInsight
    # When: materialize_reports() 2회 실행
    # Then: 1번만 저장, 2번째는 건너뜀

def test_materialize_reports_records_failure():
    """게시 실패 시 JobRun 기록."""
    # Given: DB 연결 실패
    # When: materialize_reports() 실행
    # Then: JobRun FAILED, 에러 메시지 포함
```

## 관찰성

### 로그 이벤트
- `publish.start`: 게시 시작
- `publish.materialized`: ReportSnapshot 생성 완료 (개수 포함)
- `publish.skipped`: 이미 게시됨 (중복)
- `publish.failed`: 게시 실패

### JobRun 추적
```sql
SELECT * FROM job_runs
WHERE stage = 'publish'
ORDER BY started_at DESC
LIMIT 10;
```

## 아티팩트 관리 (향후)

### 계획
- 이미지/PDF 링크를 `attachments` 배열에 저장
- `./var/storage/{ticker}/{date}/{filename}` 구조
- S3 백엔드로 교체 예정

### 스키마
```json
{
  "attachments": [
    {
      "type": "image",
      "url": "/storage/AAPL/2025/11/27/chart-123.png",
      "caption": "주가 차트"
    }
  ]
}
```

## 현재 구현 상태

### 완료 ✅
- ProcessedInsight → ReportSnapshot 변환
- Idempotency 보장
- JobRun 추적
- 기본 테스트

### 계획됨 📋
- Celery Beat 스케줄 통합
- SLA 모니터링 자동화
- 아티팩트 호스팅
- Slack 알림 (향후)

## 관련 문서

- [전체 아키텍처](../ARCHITECTURE.md)
- [Analysis 모듈](../analysis/README.md) - ProcessedInsight 생성
- [API 모듈](../api/README.md) - ReportSnapshot 조회
- [운영 가이드](../OPERATIONS.md)
- [테스트 전략 - Publish](../TESTING.md#publish-테스트)
