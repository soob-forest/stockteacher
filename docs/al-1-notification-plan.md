# AL-1: 알림 정책(시간대·빈도·채널) 계획

## 목표
- 사용자가 리포트 알림 시간대/빈도/채널을 직접 제어할 수 있게 하고, 기본값을 제공해 온보딩 마찰을 낮춘다.

## 범위
- 포함: 알림 정책 스키마/API/UI, 기본값 설정, 유효성 검증.
- 제외: 실제 이메일/푸시 발송 파이프라인(별도 이슈), Slack 연동.

## 요구사항
1) 필드: timezone(예: Asia/Seoul), window(아침/저녁/즉시), frequency(매일/주간), channel(web-push|email; 다중 선택 가능), quiet_hours(optional).
2) 기본값: timezone=Asia/Seoul, window=daily_close, frequency=daily, channel=email.
3) 검증: 시간대 표준 리스트, quiet_hours는 start<end, channel 최소 1개.
4) UI: 구독/설정 화면에서 선택·미리보기, 기본값 표시.
5) API: 조회(GET), 저장/업데이트(PUT/PATCH) 엔드포인트, 사용자별 정책 저장.

## 태스크
- [ ] 정책 모델/테이블 또는 사용자 설정 테이블 확장.
- [ ] API 추가: GET/PUT `/api/notifications/policy` (또는 user settings).
- [ ] UI 폼: 선택 옵션/기본값 적용, 저장 시 토스트/에러 처리.
- [ ] 테스트: 기본값 반환, 검증 오류(시간대/quiet_hours), 저장/조회 왕복.

## 리스크
- 인증 부재로 사용자 식별이 불완전 → 임시 user_id 유지, 향후 OAuth 도입 시 마이그레이션 필요.
- 푸시 채널은 HTTPS/권한 요구 → 초기엔 email-only로 동작하도록 기본값/feature flag 제공.
