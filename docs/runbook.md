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

장애 대응 체크리스트
- [ ] Redis 연결 확인(`INGESTION_REDIS_URL`, docker-compose 상태)
- [ ] DB 연결 확인(POSTGRES_DSN 접속, 마이그레이션 적용 여부)
- [ ] Rate limit/일시 오류 증가 시 재시도 지표 확인(로그에서 Transient 표시)
- [ ] 중복 적재 급증 시 fingerprint/키스토어 설정 점검
- [ ] 연속 실패 시 Beat 스케줄 비활성화 또는 간격 확대, 원인 분석 후 복구

운영 팁
- 개발 환경에서는 SQLite(파일)로 빠르게 확인하고, 배포 환경은 관리형 DB를 사용하세요.
- 민감 정보는 로그에 포함하지 않고, trace_id를 통해 사건을 상관 분석합니다.

