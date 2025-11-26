# Analysis (데이터 분석) 모듈

## 개요

OpenAI LLM을 활용하여 수집된 텍스트를 분석하고 인사이트를 생성합니다.

## 주요 기능

- **키워드 추출**: 핵심 키워드 3-10개 추출
- **요약 생성**: 최대 1200자 요약문 생성
- **감성 분석**: -1.0(매우 부정) ~ 1.0(매우 긍정) 점수
- **이상 징후 탐지**: 비정상 패턴 감지 (급등락, 대규모 인수, 규제/소송 등)
- **비용 가드레일**: 요청당 비용 상한 설정
- **재시도 로직**: 일시 오류 시 최대 3회 재시도

## 문서

- [분석 구현 계획](./analysis-plan.md) - LLM 분석 파이프라인 구현 계획 및 체크리스트

## 주요 파일

| 파일 | 설명 | 주요 함수/클래스 |
|-----|------|----------------|
| `analysis/tasks/analyze.py:45` | 분석 핵심 로직 | `analyze_core()` |
| `analysis/client/openai_client.py:78` | OpenAI 클라이언트 래퍼 | `OpenAIClient` |
| `analysis/prompts/templates.py` | 프롬프트 템플릿 | `build_analysis_messages()` |
| `analysis/repositories/insights.py` | ProcessedInsight 저장 | `save_insight()` |
| `analysis/settings.py` | 설정 및 검증 | `get_analysis_settings()` |
| `analysis/models/domain.py` | 도메인 모델 | `AnalysisInput`, `AnalysisResult` |

## 설정

### 환경 변수

```bash
# OpenAI API
OPENAI_API_KEY=sk-your-key-here

# 모델 설정
ANALYSIS_MODEL=gpt-4o-mini
ANALYSIS_MAX_TOKENS=512
ANALYSIS_TEMPERATURE=0.2

# 비용 및 성능
ANALYSIS_COST_LIMIT_USD=0.02
ANALYSIS_REQUEST_TIMEOUT_SECONDS=15
ANALYSIS_RETRY_MAX_ATTEMPTS=2

# 언어 및 로케일
DEFAULT_LOCALE=ko_KR
```

## 실행 방법

### 수동 분석 실행
```bash
uv run -- python -c "from analysis.tasks.analyze import analyze_core; print(analyze_core('AAPL'))"
```

### Celery 워커 (분석 전용)
```bash
uv run -- celery -A ingestion.celery_app:get_celery_app worker -Q analysis.analyze -l info
```

## 데이터 흐름

```
1. analyze_core → 최신 raw_articles 조회 (최근 5건)
2. 프롬프트 빌더 → 구조화 메시지 생성
3. OpenAI 클라이언트 → API 호출 (JSON 모드)
4. 응답 파싱 → AnalysisResult 객체 생성
5. Repository → ProcessedInsight 테이블에 저장
6. JobRun → stage=analyze, 토큰/비용 기록
```

## 출력 구조

### ProcessedInsight (DB)
- `insight_id`: UUID
- `ticker`: 종목 코드
- `summary_text`: 요약 (최대 4000자)
- `keywords`: 키워드 배열
- `sentiment_score`: 감성 점수 (-1.0 ~ 1.0)
- `anomalies`: 이상 징후 배열
- `llm_model`: 사용 모델 (gpt-4o-mini)
- `llm_tokens_prompt`: 프롬프트 토큰 수
- `llm_tokens_completion`: 완성 토큰 수
- `llm_cost`: 비용 (USD)
- `generated_at`: 생성 시각

### JSON 스키마 (OpenAI 응답)
```json
{
  "summary_text": "요약 내용 (최대 1200자)",
  "keywords": ["키워드1", "키워드2", "키워드3"],
  "sentiment_score": 0.5,
  "anomalies": [
    {
      "label": "이벤트명 (최대 64자)",
      "description": "설명 (최대 512자)",
      "score": 0.8
    }
  ]
}
```

## 테스트

### 단위 테스트
```bash
uv run -- python -m pytest tests/analysis/test_analyze_task.py
```

### Fake Provider 사용
```python
# tests/analysis/conftest.py
@pytest.fixture
def fake_provider():
    def _provider(payload):
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "summary_text": "Test summary",
                        "keywords": ["test"],
                        "sentiment_score": 0.5,
                        "anomalies": []
                    })
                }
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50
            }
        }
    return _provider
```

### 커버리지
```bash
uv run -- python -m pytest tests/analysis/ --cov=analysis --cov-report=term-missing
```

## 관찰성

### 로그 이벤트
- `analyze.start`: 분석 시작 (기사 수 포함)
- `analyze.saved`: 분석 완료 (model, tokens, cost 포함)
- `analyze.no_articles`: 분석할 기사 없음
- `analyze.transient_error`: 일시 오류 (재시도 가능)
- `analyze.permanent_error`: 영구 오류 (재시도 불가)
- `analyze.unexpected_error`: 예상치 못한 오류

### JobRun 추적
```sql
SELECT * FROM job_runs
WHERE stage = 'analyze' AND source = 'openai'
ORDER BY started_at DESC
LIMIT 10;
```

## 에러 처리

### TransientLLMError (재시도 가능)
- 네트워크 타임아웃
- Rate Limit (429)
- JSON 파싱 실패 (일시적)
- 재시도: 지터 백오프, 최대 3회

### PermanentLLMError (재시도 불가)
- 비용 상한 초과
- 인증 실패 (401, 403)
- 잘못된 요청 (400)
- 재시도 없이 즉시 실패

## 비용 관리

### 토큰 추정
- 프롬프트: ~100-200 토큰
- 완성: ~200-500 토큰 (설정에 따라)
- 총: ~300-700 토큰/요청

### 비용 추정 (gpt-4o-mini 기준)
- 입력: $0.150 / 1M 토큰
- 출력: $0.600 / 1M 토큰
- 평균 비용: ~$0.01-0.02 / 요청

### 비용 절감 방안
1. `ANALYSIS_MAX_TOKENS` 감소 (512 → 256)
2. 수집 빈도 감소 (interval_minutes 증가)
3. 저렴한 모델 사용 (이미 gpt-4o-mini 사용 중)
4. 배치 처리 (여러 기사를 한 번에)

## 관련 문서

- [전체 아키텍처](../ARCHITECTURE.md)
- [운영 가이드 - LLM 분석](../OPERATIONS.md#분석llm-운영)
- [테스트 전략 - Analysis](../TESTING.md#analysis-테스트)
- [의사결정 - LLM 전략](../DECISIONS.md#adr-003-llm-분석-전략---단일-프롬프트)
