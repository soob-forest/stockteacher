운영 런북 (MVP)

개요
- 목적: 수집 파이프라인(Beat/Worker) 운영 중 주요 절차와 점검 항목을 요약합니다.

사전 준비
- Redis 기동: `docker-compose up -d redis` (포트 6379)
- 환경 변수: `.env`에 필수 값 설정(INGESTION_REDIS_URL, POSTGRES_DSN, COLLECTION_SCHEDULES 등)
- DB 마이그레이션: `uv run -- alembic upgrade head`

프로세스 기동
- 워커: `uv run -- celery -A ingestion.celery_app:get_celery_app worker -l info`
- 비트: `uv run -- celery -A ingestion.celery_app:get_celery_app beat -l info`

관찰성
- 로그 레벨: `STRUCTLOG_LEVEL=INFO|DEBUG`
- JSON 로그: `LOG_JSON=1` → trace_id, ticker, source, saved 등 필드 확인
- 실패 태스크 확인: 워커 로그에서 예외 스택과 trace_id로 검색

분석(LLM) 운영
- 사전 준비: `.env`에 `OPENAI_API_KEY`, `ANALYSIS_MODEL`(gpt-4o-mini 추천), `ANALYSIS_MAX_TOKENS`, `ANALYSIS_TEMPERATURE`,
  `ANALYSIS_COST_LIMIT_USD`, `ANALYSIS_REQUEST_TIMEOUT_SECONDS`, `ANALYSIS_RETRY_MAX_ATTEMPTS` 설정
- 수동 실행: `uv run -- python -c "from analysis.tasks.analyze import analyze_core; print(analyze_core('AAPL'))"`
- 레이트 제한: 워커 동시성 낮추기, Beat 간격 확장, 토큰 상한 조정
- 워커/큐 운영: 분석 태스크는 ingestion Celery 워커에서 처리되며 필요 시 `uv run -- celery -A ingestion.celery_app:get_celery_app worker -Q analysis.analyze -l info` 전용 워커를 추가합니다.
- 관찰 포인트: `analyze.start`(기사 수), `analyze.saved`(model/tokens/cost), `analyze.transient_error`/`analyze.permanent_error`/`analyze.unexpected_error` 로그로 성공·실패를 구분하고 JobRun(stage=analyze, source=openai) 상태를 함께 확인
- 플레이북
  - 기사 없음: `analyze.no_articles` → 수집 상태/스케줄 점검
  - JSON 파싱 실패: 프롬프트 템플릿/로케일 확인, 재시도 횟수 조정(`TransientLLMError`는 최대 3회 자동 재시도)
  - 비용 상한 초과: 모델/토큰 상한 하향, Beat 간격 조정, 대안 모델 고려(PermanentLLMError → 재시도 없음)
  - 타임아웃: 요청 타임아웃 상향 또는 입력 청크 축소, 동시성 하향

장애 대응 체크리스트
- [ ] Redis 연결 확인(`INGESTION_REDIS_URL`, docker-compose 상태)
- [ ] DB 연결 확인(POSTGRES_DSN 접속, 마이그레이션 적용 여부)
- [ ] Rate limit/일시 오류 증가 시 재시도 지표 확인(로그에서 Transient 표시)
- [ ] 중복 적재 급증 시 fingerprint/키스토어 설정 점검
- [ ] 연속 실패 시 Beat 스케줄 비활성화 또는 간격 확대, 원인 분석 후 복구

운영 팁
- 개발 환경에서는 SQLite(파일)로 빠르게 확인하고, 배포 환경은 관리형 DB를 사용하세요.
- 민감 정보는 로그에 포함하지 않고, trace_id를 통해 사건을 상관 분석합니다.
