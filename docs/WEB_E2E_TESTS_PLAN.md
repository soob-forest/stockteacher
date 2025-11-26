# 웹 E2E 테스트 (Playwright) PLAN

## Problem 1-Pager
- 배경: StockTeacher 웹 앱(Next.js)은 구독 관리, 리포트 목록/즐겨찾기, 리포트 상세+챗 페이지를 제공하지만, 현재는 API 단위 테스트만 있고 브라우저 관점에서 각 화면이 제대로 렌더링되고 기본 상호작용이 동작하는지 검증할 수 있는 자동화된 E2E 테스트가 없다.
- 문제: 코드 변경 후에도 네비게이션/레이아웃/폼 요소가 깨졌는지 수동으로 확인해야 하며, API 서버/DB 시드와의 연동 상태도 눈으로만 검증해야 한다. 특히 리다이렉트(Index → Subscriptions)나 필터/즐겨찾기 토글 등은 DOM 구조가 바뀌면 바로 감지하기 어렵다.
- 목표: Playwright 기반 브라우저 테스트를 도입해 루트(`/`), 구독(`/subscriptions`), 리포트 목록(`/reports`), 즐겨찾기(`/reports/favorites`), 리포트 상세(`/reports/:id`) 페이지가 기본적으로 렌더되고 핵심 텍스트/폼이 존재하는지 검증한다. 외부 네트워크에는 의존하지 않고, 로컬 API(`http://localhost:8000`)와 정해진 더미 데이터에만 의존하는 결정적 테스트를 작성한다.
- 비목표: 실제 LLM 응답 흐름(채팅 전송/스트리밍)이나 복잡한 필터 조합, 반응형 디자인까지 모두 자동화하는 것은 이번 범위 밖이다. CI 환경에서 브라우저 설치/병렬 실행을 튜닝하는 작업도 후속 단계로 남긴다.
- 제약: 테스트는 1개 파일 ≤ 300 LOC로 유지하고, 각 테스트 케이스는 한 가지 시나리오(페이지 진입 → 핵심 요소 확인)에 집중한다. 테스트 실행 전에는 웹 앱(Next.js dev 서버)과 API(FastAPI)가 `./scripts/run_servers.sh` 등으로 이미 실행 중이라는 가정을 둔다. 브라우저 바이너리 설치는 Playwright CLI(`npx playwright install`)에 맡기며, 코드에서 직접 네트워크 설치를 시도하지 않는다.

## 대안 비교
- Option A: web 서브디렉터리 내에서 Playwright를 설정하고, baseURL을 `http://localhost:3000`으로 두고 이미 실행 중인 dev 서버에 붙는 전통적인 E2E 구성
  - 장점: Next.js 앱 구조와 자연스럽게 맞고, 프로젝트 루트의 Python 의존성과 분리되어 Node 전용 devDependencies로 관리할 수 있다.
  - 단점: 테스트 실행 전 서버를 별도 스크립트로 올려야 하며, 포트/환경이 맞지 않으면 테스트가 실패한다.
  - 위험: 개발자가 서버를 올리지 않은 채 테스트를 실행하면 연결 실패로 인해 혼동이 생길 수 있다.
- Option B: Playwright 테스트에서 Next.js dev 서버를 직접 부트스트랩(`webServer` 옵션)해 올린 뒤, API는 테스트 중에 모킹하거나 별도 스크립트로 기동
  - 장점: `npx playwright test`만으로 self-contained 실행이 가능해진다.
  - 단점: dev 서버 기동/종료 시간만큼 테스트가 느려지고, API/DB까지 통합하려면 설정이 복잡해진다.
  - 위험: 포트 충돌, 서버 기동 실패 등으로 테스트 실패 원인이 복잡해질 수 있다.

**선택**: Option A를 우선 채택한다. 이미 `scripts/run_servers.sh`로 API/Web 서버를 한 번에 올릴 수 있으므로, Playwright는 이를 전제로 단순히 브라우저에서 페이지 레벨의 상태를 검증하는 역할에 집중한다. 후속 단계에서 필요하다면 `webServer` 설정을 추가해 CI에서 self-contained 실행을 지원할 수 있다.

