# Phase B: 채팅 에이전트 WebSocket 구현

## 목표

폴링 방식을 WebSocket으로 전환하고, 하드코딩된 응답을 OpenAI LLM 스트리밍 응답으로 교체

## 현재 상태 (2025-11-27 기준)

### 백엔드
- ✅ 채팅 세션/메시지 DB 모델 완성 (`api/db_models.py` 81-117줄)
- ✅ 기본 REST API 완성 (`api/routes.py` 151-189줄)
  - `POST /api/chat/sessions` - 세션 생성
  - `GET /api/chat/sessions/{id}/messages` - 메시지 조회
  - `POST /api/chat/sessions/{id}/messages` - 메시지 전송
- ✅ 채팅 메시지 관리 로직 (`api/repositories.py` 162-227줄)
- 🔴 **하드코딩된 응답**: `api/repositories.py:212-227` `_append_agent_reply()` 함수
- ✅ OpenAI 클라이언트 완성 (`analysis/client/openai_client.py` 176줄)
- ❌ **스트리밍 미지원**: 현재 동기 호출만 사용
- ❌ WebSocket 미구현

### 프론트엔드
- ✅ 채팅 UI 완성 (`web/app/reports/[insightId]/page.tsx`)
- ✅ 폴링 방식 (3초 간격 `setInterval`, 75-99줄)
- ✅ 메시지 전송/표시 로직 (120-134줄, 248-281줄)
- ⚠️ **UX 문제**: 사용자 메시지 즉시 반영 안됨 (폴링 대기 필요)
- ⚠️ **API 중복**: 메시지 전송 후 강제 재조회
- ❌ WebSocket 미구현

## 기술 선택 근거

1. **WebSocket** (vs 폴링/SSE): 양방향 통신 + 사용자 타이핑 표시 가능
2. **공통 llm/ 모듈** (vs analysis 재사용/별도 모듈): DRY 원칙, 단일 설정 관리
3. **스트리밍 청크 방식** (vs 전체 완료 대기): 실시간 피드백 (5-10 토큰 단위)

## 5단계 실행 계획

### Phase 1: LLM 모듈 리팩터링 (1-2일)

**목표**: analysis/client/openai_client.py를 llm/client.py로 이동하고 스트리밍 지원 추가

#### 1-1. llm/ 모듈 생성 및 이동
```bash
mkdir llm llm/client llm/prompts
touch llm/__init__.py llm/client/__init__.py llm/prompts/__init__.py

# 파일 이동 (git mv로 히스토리 보존)
git mv analysis/client/openai_client.py llm/client/openai_client.py
git mv analysis/settings.py llm/settings.py
```

#### 1-2. llm/client/openai_client.py 수정
**파일**: `/Users/soob/Desktop/github/stockteacher/llm/client/openai_client.py`

**추가 메서드**:
```python
def stream_chat(
    self,
    messages: List[dict],
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> Iterator[str]:
    """
    OpenAI Chat Completion API를 스트리밍 모드로 호출.

    Yields:
        str: 각 청크의 텍스트 (delta.content)
    """
    # OpenAI API 스트리밍 호출
    # yield로 청크 반환
```

#### 1-3. analysis/ 모듈 업데이트
**파일**: `/Users/soob/Desktop/github/stockteacher/analysis/tasks/analyze.py`

```python
# Before
from analysis.client.openai_client import OpenAIClient

# After
from llm.client.openai_client import OpenAIClient
```

**회귀 테스트**:
```bash
uv run -- python -c "from analysis.tasks.analyze import analyze_core; print(analyze_core('AAPL'))"
```

**제약**: 파일 ≤300 LOC, 함수 ≤50 LOC (CLAUDE.md)

### Phase 2: WebSocket 백엔드 (2-3일)

#### 2-1. WebSocket 라우트 추가
**파일**: `/Users/soob/Desktop/github/stockteacher/api/routes.py` (신규 섹션)

```python
from fastapi import WebSocket, WebSocketDisconnect

@router.websocket("/chat/ws/{session_id}")
async def chat_websocket(
    websocket: WebSocket,
    session_id: str,
    session: SessionDep,
):
    """
    WebSocket 채팅 엔드포인트.

    클라이언트 → 서버: {"type": "message", "content": "..."}
    서버 → 클라이언트: {"type": "chunk", "content": "..."}
                      {"type": "done", "message_id": "..."}
                      {"type": "error", "detail": "..."}
    """
    await manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # ChatService 호출
            async for chunk in chat_service.handle_message(...):
                await websocket.send_json({"type": "chunk", "content": chunk})
            await websocket.send_json({"type": "done", ...})
    except WebSocketDisconnect:
        manager.disconnect(session_id)
```

**LOC 제한**: 이 섹션만 50줄 이하

#### 2-2. ConnectionManager 구현
**파일**: `/Users/soob/Desktop/github/stockteacher/api/websocket_manager.py` (신규)

```python
class ConnectionManager:
    """WebSocket 연결 관리."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)

    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)

manager = ConnectionManager()
```

**LOC 제한**: ≤100줄

#### 2-3. ChatService 구현
**파일**: `/Users/soob/Desktop/github/stockteacher/api/chat_service.py` (신규)

```python
from llm.client.openai_client import OpenAIClient

class ChatService:
    """채팅 비즈니스 로직."""

    def __init__(self, openai_client: OpenAIClient, redis_cache: RedisSessionCache):
        self.openai_client = openai_client
        self.cache = redis_cache

    async def handle_message(
        self,
        session: Session,
        session_id: str,
        user_message: str,
    ) -> AsyncIterator[str]:
        """
        사용자 메시지 처리 및 LLM 응답 스트리밍.

        1. 사용자 메시지 DB 저장
        2. 리포트 요약 + 대화 히스토리로 컨텍스트 구축
        3. LLM 스트리밍 호출
        4. 각 청크 yield
        5. 전체 응답 DB 저장
        """
        # 1. 사용자 메시지 저장
        add_chat_message(session, session_id, "user", user_message)

        # 2. 컨텍스트 구축
        context = self._build_context(session, session_id)

        # 3. LLM 스트리밍
        full_response = []
        for chunk in self.openai_client.stream_chat(messages=context):
            full_response.append(chunk)
            yield chunk

        # 4. 응답 저장
        add_chat_message(session, session_id, "agent", "".join(full_response))

    def _build_context(self, session: Session, session_id: str) -> List[dict]:
        """
        채팅 컨텍스트 구축.

        Returns:
            [
                {"role": "system", "content": "리포트 요약: ..."},
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."},
                ...
            ]
        """
        chat_session = session.get(db_models.ChatSession, session_id)
        report = session.get(db_models.ReportSnapshot, chat_session.insight_id)

        messages = [
            {"role": "system", "content": f"리포트 요약: {report.summary_text}"}
        ]

        # 대화 히스토리 (최근 10개)
        history = list_chat_messages(session, session_id)[-10:]
        for msg in history:
            role = "user" if msg.sender == "user" else "assistant"
            messages.append({"role": role, "content": msg.content})

        return messages

chat_service = ChatService(OpenAIClient.from_env(), RedisSessionCache())
```

**LOC 제한**: ≤200줄

#### 2-4. RedisSessionCache 구현
**파일**: `/Users/soob/Desktop/github/stockteacher/api/redis_cache.py` (신규)

```python
import redis
from typing import List, Optional

class RedisSessionCache:
    """Redis 기반 채팅 세션 캐시."""

    def __init__(self, redis_url: str = "redis://localhost:6379/1"):
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)
        self.ttl = 3600  # 1시간

    def get_context(self, session_id: str) -> Optional[List[dict]]:
        """세션 컨텍스트 조회."""
        key = f"chat:context:{session_id}"
        data = self.client.get(key)
        return json.loads(data) if data else None

    def set_context(self, session_id: str, context: List[dict]):
        """세션 컨텍스트 저장."""
        key = f"chat:context:{session_id}"
        self.client.setex(key, self.ttl, json.dumps(context))
```

**LOC 제한**: ≤100줄

### Phase 3: LLM 채팅 통합 (1일)

#### 3-1. OpenAI 스트리밍 구현
**파일**: `/Users/soob/Desktop/github/stockteacher/llm/client/openai_client.py`

**stream_chat() 메서드 상세 구현**:
```python
def stream_chat(
    self,
    messages: List[dict],
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> Iterator[str]:
    model = model or self.settings.analysis_model
    max_tokens = max_tokens or self.settings.analysis_max_tokens
    temperature = temperature or self.settings.analysis_temperature

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,  # 스트리밍 활성화
    }

    provider = self._get_provider()

    # OpenAI 스트리밍 응답
    for chunk in provider(payload):
        if "choices" in chunk and len(chunk["choices"]) > 0:
            delta = chunk["choices"][0].get("delta", {})
            content = delta.get("content", "")
            if content:
                yield content
```

#### 3-2. 토큰 추적 (스트리밍 후)
**방법**: 스트리밍 완료 후 전체 응답의 토큰 수를 추정하여 DB에 기록

```python
# ChatService.handle_message() 내부
full_response = "".join(full_response)
estimated_tokens = len(full_response.split()) * 1.3  # 보수적 추정
cost = estimated_tokens * 0.00002  # gpt-4o-mini 가격

# JobRun에 기록 (선택)
job_run = db_models.JobRun(
    stage="chat",
    source="openai",
    status="SUCCESS",
    metadata={"tokens": estimated_tokens, "cost": cost},
)
session.add(job_run)
```

### Phase 4: WebSocket 프론트엔드 (1-2일)

#### 4-1. WebSocket 훅 생성
**파일**: `/Users/soob/Desktop/github/stockteacher/web/hooks/useChatWebSocket.ts` (신규)

```typescript
import { useEffect, useRef, useState } from 'react';

interface ChatMessage {
  message_id: string;
  sender: 'user' | 'agent' | 'system';
  content: string;
  created_at: string;
}

export function useChatWebSocket(sessionId: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);

  useEffect(() => {
    if (!sessionId) return;

    const connect = () => {
      const ws = new WebSocket(`ws://localhost:8000/api/chat/ws/${sessionId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0;
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'chunk') {
          // 스트리밍 청크 수신 → 에이전트 메시지에 추가
          setMessages((prev) => {
            const lastMsg = prev[prev.length - 1];
            if (lastMsg && lastMsg.sender === 'agent' && !lastMsg.message_id) {
              // 기존 에이전트 메시지에 청크 추가
              return [
                ...prev.slice(0, -1),
                { ...lastMsg, content: lastMsg.content + data.content },
              ];
            } else {
              // 새 에이전트 메시지 시작
              return [
                ...prev,
                {
                  message_id: '',
                  sender: 'agent',
                  content: data.content,
                  created_at: new Date().toISOString(),
                },
              ];
            }
          });
          setIsTyping(true);
        } else if (data.type === 'done') {
          // 스트리밍 완료
          setIsTyping(false);
          setMessages((prev) => {
            const lastMsg = prev[prev.length - 1];
            return [
              ...prev.slice(0, -1),
              { ...lastMsg, message_id: data.message_id },
            ];
          });
        } else if (data.type === 'error') {
          setError(data.detail);
          setIsTyping(false);
        }
      };

      ws.onerror = (event) => {
        setError('WebSocket 연결 오류');
        setIsConnected(false);
      };

      ws.onclose = () => {
        setIsConnected(false);
        setIsTyping(false);

        // 재연결 (지수 백오프)
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
        reconnectAttemptsRef.current += 1;

        if (reconnectAttemptsRef.current <= 5) {
          setTimeout(connect, delay);
        } else {
          setError('WebSocket 재연결 실패. 페이지를 새로고침하세요.');
        }
      };
    };

    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [sessionId]);

  const sendMessage = (content: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('WebSocket 연결 없음');
      return;
    }

    // 사용자 메시지 즉시 표시
    setMessages((prev) => [
      ...prev,
      {
        message_id: `temp-${Date.now()}`,
        sender: 'user',
        content,
        created_at: new Date().toISOString(),
      },
    ]);

    // 서버로 전송
    wsRef.current.send(JSON.stringify({ type: 'message', content }));
  };

  return { messages, isConnected, error, isTyping, sendMessage };
}
```

**LOC 제한**: ≤150줄

#### 4-2. 기존 컴포넌트 업데이트
**파일**: `/Users/soob/Desktop/github/stockteacher/web/app/reports/[insightId]/page.tsx`

**변경 사항**:
```typescript
// Before: 폴링 방식
const [messages, setMessages] = useState<ChatMessage[]>([]);
useEffect(() => {
  // 3초마다 fetch
  const timer = setInterval(() => fetchChatMessages(session.session_id), 3000);
  return () => clearInterval(timer);
}, [session]);

// After: WebSocket 방식
import { useChatWebSocket } from '@/hooks/useChatWebSocket';

const { messages, isConnected, error, isTyping, sendMessage } = useChatWebSocket(
  session?.session_id || null
);

// handleSend 함수 단순화
async function handleSend() {
  if (!messageDraft.trim()) return;
  sendMessage(messageDraft.trim());
  setMessageDraft('');
}
```

**추가 UI**:
- 연결 상태 표시: `{isConnected ? '🟢 연결됨' : '🔴 연결 끊김'}`
- 타이핑 표시: `{isTyping && <div>에이전트가 입력 중...</div>}`

### Phase 5: 테스트 및 마무리 (2일)

#### 5-1. 단위 테스트
**파일**: `/Users/soob/Desktop/github/stockteacher/tests/llm/test_openai_client.py` (신규)

```python
from llm.client.openai_client import OpenAIClient

def test_stream_chat_yields_chunks(fake_provider):
    """스트리밍이 청크를 순차적으로 yield하는지 검증."""
    client = OpenAIClient(settings, provider=fake_provider)
    chunks = list(client.stream_chat(messages=[...]))
    assert len(chunks) > 0
    assert all(isinstance(c, str) for c in chunks)
```

#### 5-2. 통합 테스트
**파일**: `/Users/soob/Desktop/github/stockteacher/tests/api/test_websocket.py` (신규)

```python
from fastapi.testclient import TestClient

def test_websocket_chat_flow(client: TestClient, test_session_id):
    """WebSocket 채팅 전체 흐름 테스트."""
    with client.websocket_connect(f"/api/chat/ws/{test_session_id}") as ws:
        # 사용자 메시지 전송
        ws.send_json({"type": "message", "content": "안녕하세요"})

        # 청크 수신
        chunks = []
        while True:
            data = ws.receive_json()
            if data["type"] == "chunk":
                chunks.append(data["content"])
            elif data["type"] == "done":
                break

        assert len(chunks) > 0
        assert len("".join(chunks)) > 0
```

#### 5-3. E2E 테스트
**파일**: `/Users/soob/Desktop/github/stockteacher/web/tests/chat-websocket.spec.ts` (신규)

```typescript
import { test, expect } from '@playwright/test';

test('채팅 WebSocket 흐름', async ({ page }) => {
  await page.goto('http://localhost:3000/reports/insight-123');

  // 연결 상태 확인
  await expect(page.locator('text=🟢 연결됨')).toBeVisible();

  // 메시지 입력
  await page.fill('textarea[name="message"]', '안녕하세요');
  await page.click('button:has-text("전송")');

  // 사용자 메시지 표시 확인
  await expect(page.locator('.message.user:has-text("안녕하세요")')).toBeVisible();

  // 타이핑 표시 확인
  await expect(page.locator('text=에이전트가 입력 중')).toBeVisible();

  // 에이전트 응답 수신 대기 (최대 10초)
  await expect(page.locator('.message.agent')).toBeVisible({ timeout: 10000 });
});
```

#### 5-4. 부하 테스트
**파일**: `/Users/soob/Desktop/github/stockteacher/tests/load/websocket_load.py` (신규)

```python
import asyncio
import websockets

async def simulate_client(session_id: int):
    """단일 클라이언트 시뮬레이션."""
    uri = f"ws://localhost:8000/api/chat/ws/test-session-{session_id}"
    async with websockets.connect(uri) as ws:
        await ws.send('{"type": "message", "content": "안녕하세요"}')
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data["type"] == "done":
                break

async def load_test():
    """100개 동시 연결 테스트."""
    tasks = [simulate_client(i) for i in range(100)]
    await asyncio.gather(*tasks)

# 실행: python tests/load/websocket_load.py
```

**목표**: 100개 동시 연결에서 응답 시간 <5초

## Critical Files (채팅 에이전트)

### 읽어야 할 파일 (구현 전)
1. **`analysis/client/openai_client.py`** (176줄): OpenAI 클라이언트 원본
2. **`api/repositories.py`** (라인 162-228): 채팅 메시지 관리 로직
3. **`web/app/reports/[insightId]/page.tsx`** (라인 27-285): 채팅 UI 및 폴링 로직
4. **`analysis/prompts/templates.py`**: 프롬프트 구축 패턴
5. **`api/db_models.py`** (라인 81-118): ChatSession, ChatMessage 스키마

### 생성할 파일
1. **`llm/client/openai_client.py`** (이동 + 수정): 스트리밍 메서드 추가
2. **`api/websocket_manager.py`**: ConnectionManager
3. **`api/chat_service.py`**: ChatService
4. **`api/redis_cache.py`**: RedisSessionCache
5. **`web/hooks/useChatWebSocket.ts`**: WebSocket 훅

### 수정할 파일
1. **`api/routes.py`**: WebSocket 엔드포인트 추가
2. **`web/app/reports/[insightId]/page.tsx`**: 폴링 → WebSocket 전환
3. **`analysis/tasks/analyze.py`**: import 경로 변경

## 예상 소요 시간

- Phase 1: LLM 모듈 리팩터링 (1-2일)
- Phase 2: WebSocket 백엔드 (2-3일)
- Phase 3: LLM 통합 (1일)
- Phase 4: WebSocket 프론트엔드 (1-2일)
- Phase 5: 테스트 및 마무리 (2일)

**총: 7-10일**

---

# 실행 가능한 TODO 체크리스트

## 준비 단계 (Pre-flight Checklist)

### 환경 설정 확인
- [ ] `OPENAI_API_KEY` 환경 변수 설정 확인
- [ ] Redis 실행 확인 (`docker-compose up -d redis`)
- [ ] DB 마이그레이션 완료 확인 (`alembic upgrade head`)
- [ ] 기존 analysis 파이프라인 동작 확인 (`python -c "from analysis.tasks.analyze import analyze_core; print(analyze_core('AAPL'))"`)


## Step 1: LLM 모듈 리팩터링 (1-2일)

### 1-1. llm/ 모듈 디렉토리 생성 (30분)
- [ ] `mkdir -p llm/client llm/prompts`
- [ ] `touch llm/__init__.py llm/client/__init__.py llm/prompts/__init__.py`
- [ ] Git add 및 커밋: "chore: llm 모듈 디렉토리 생성"

### 1-2. OpenAI 클라이언트 이동 (1시간)
- [ ] `git mv analysis/client/openai_client.py llm/client/openai_client.py`
- [ ] `git mv analysis/settings.py llm/settings.py` (설정 통합 고려)
- [ ] Git 커밋: "refactor: OpenAI 클라이언트를 llm/ 모듈로 이동"

### 1-3. 스트리밍 메서드 추가 (2-3시간)
- [ ] `llm/client/openai_client.py`에 `stream_chat()` 메서드 추가
  - [ ] OpenAI API `stream=True` 파라미터 사용
  - [ ] `yield` 방식으로 청크 반환
  - [ ] 에러 처리 (TransientLLMError, PermanentLLMError)
- [ ] 단위 테스트 작성: `tests/llm/test_openai_client.py`
  - [ ] `test_stream_chat_yields_chunks()` - 스트리밍 검증
  - [ ] `test_stream_chat_handles_errors()` - 에러 처리 검증
- [ ] Git 커밋: "feat: OpenAI 클라이언트에 스트리밍 지원 추가"

### 1-4. analysis 모듈 업데이트 (1-2시간)
- [ ] `analysis/tasks/analyze.py` import 경로 변경
  - [ ] `from analysis.client.openai_client import` → `from llm.client.openai_client import`
- [ ] `analysis/prompts/templates.py` import 경로 확인/변경 (필요시)
- [ ] **회귀 테스트 실행**:
  - [ ] `uv run -- python -m pytest tests/analysis/`
  - [ ] `uv run -- python -c "from analysis.tasks.analyze import analyze_core; print(analyze_core('AAPL'))"`
- [ ] Git 커밋: "refactor: analysis 모듈에서 llm 클라이언트 import 경로 업데이트"

---

## Step 2: WebSocket 백엔드 구현 (2-3일)

### 2-1. ConnectionManager 구현 (1-2시간)
- [ ] 파일 생성: `api/websocket_manager.py`
- [ ] `ConnectionManager` 클래스 구현
  - [ ] `connect()` - WebSocket 연결 수락
  - [ ] `disconnect()` - 연결 해제
  - [ ] `send_message()` - 특정 세션에 메시지 전송
  - [ ] `active_connections: Dict[str, WebSocket]` 관리
- [ ] 단위 테스트: `tests/api/test_websocket_manager.py`
- [ ] Git 커밋: "feat: WebSocket ConnectionManager 구현"

### 2-2. ChatService 구현 (3-4시간)
- [ ] 파일 생성: `api/chat_service.py`
- [ ] `ChatService` 클래스 구현
  - [ ] `__init__()` - OpenAIClient, RedisSessionCache 주입
  - [ ] `handle_message()` - 메시지 처리 및 LLM 스트리밍
    - [ ] 사용자 메시지 DB 저장
    - [ ] 컨텍스트 구축 (리포트 요약 + 대화 히스토리)
    - [ ] LLM 스트리밍 호출
    - [ ] 청크 yield
    - [ ] 전체 응답 DB 저장
  - [ ] `_build_context()` - 채팅 컨텍스트 구축
    - [ ] 시스템 메시지 (리포트 요약)
    - [ ] 대화 히스토리 (최근 10개)
- [ ] 단위 테스트: `tests/api/test_chat_service.py`
  - [ ] `test_handle_message_saves_user_message()`
  - [ ] `test_handle_message_streams_llm_response()`
  - [ ] `test_build_context_includes_report_summary()`
- [ ] Git 커밋: "feat: ChatService 비즈니스 로직 구현"

### 2-3. RedisSessionCache 구현 (1시간)
- [ ] 파일 생성: `api/redis_cache.py`
- [ ] `RedisSessionCache` 클래스 구현
  - [ ] `get_context()` - 세션 컨텍스트 조회
  - [ ] `set_context()` - 세션 컨텍스트 저장 (TTL 1시간)
- [ ] 단위 테스트: `tests/api/test_redis_cache.py`
- [ ] Git 커밋: "feat: Redis 세션 캐시 구현"

### 2-4. WebSocket 엔드포인트 추가 (2-3시간)
- [ ] `api/routes.py`에 WebSocket 라우트 추가
  - [ ] `@router.websocket("/chat/ws/{session_id}")`
  - [ ] ConnectionManager 연결 처리
  - [ ] 메시지 수신 루프
  - [ ] ChatService 호출 및 스트리밍
  - [ ] 청크 전송: `{"type": "chunk", "content": "..."}`
  - [ ] 완료 전송: `{"type": "done", "message_id": "..."}`
  - [ ] 에러 전송: `{"type": "error", "detail": "..."}`
  - [ ] WebSocketDisconnect 처리
- [ ] 통합 테스트: `tests/api/test_websocket.py`
  - [ ] `test_websocket_chat_flow()` - 전체 흐름 테스트
  - [ ] `test_websocket_handles_disconnect()` - 연결 끊김 처리
- [ ] Git 커밋: "feat: WebSocket 채팅 엔드포인트 구현"

### 2-5. 하드코딩 응답 제거 (30분)
- [ ] `api/repositories.py`의 `_append_agent_reply()` 함수 제거 또는 비활성화
- [ ] `add_chat_message()` 함수에서 자동 응답 로직 제거
- [ ] Git 커밋: "refactor: 하드코딩된 채팅 응답 제거"

---

## Step 3: WebSocket 프론트엔드 구현 (1-2일)

### 3-1. WebSocket 훅 생성 (2-3시간)
- [ ] 파일 생성: `web/hooks/useChatWebSocket.ts`
- [ ] `useChatWebSocket` 훅 구현
  - [ ] WebSocket 연결 관리 (useRef)
  - [ ] 상태 관리: `messages`, `isConnected`, `error`, `isTyping`
  - [ ] `onopen` - 연결 성공 처리
  - [ ] `onmessage` - 메시지 타입별 처리
    - [ ] `type: "chunk"` - 스트리밍 청크 추가
    - [ ] `type: "done"` - 스트리밍 완료
    - [ ] `type: "error"` - 에러 표시
  - [ ] `onerror` - 연결 에러 처리
  - [ ] `onclose` - 재연결 로직 (지수 백오프, 최대 5회)
  - [ ] `sendMessage()` - 메시지 전송 함수
  - [ ] Cleanup (useEffect return)
- [ ] TypeScript 타입 정의 추가
- [ ] Git 커밋: "feat: WebSocket 채팅 훅 구현"

### 3-2. 리포트 상세 페이지 업데이트 (1-2시간)
- [ ] `web/app/reports/[insightId]/page.tsx` 수정
  - [ ] 폴링 로직 제거 (setInterval 제거, 75-99줄)
  - [ ] `useChatWebSocket` 훅 사용
  - [ ] `handleSend()` 단순화 (API 중복 호출 제거)
  - [ ] 연결 상태 표시 추가: `{isConnected ? '🟢' : '🔴'}`
  - [ ] 타이핑 표시 추가: `{isTyping && <div>에이전트가 입력 중...</div>}`
  - [ ] 메시지 자동 스크롤 추가
- [ ] Git 커밋: "feat: 폴링 방식을 WebSocket으로 전환"

### 3-3. 스타일 개선 (30분-1시간)
- [ ] `web/app/globals.css` 업데이트
  - [ ] 연결 상태 표시 스타일 추가
  - [ ] 타이핑 표시 애니메이션 추가
  - [ ] 스트리밍 청크 표시 최적화
- [ ] Git 커밋: "style: WebSocket 채팅 UI 스타일 개선"

---

## Step 4: 통합 테스트 및 E2E (1-2일)

### 4-1. 백엔드 통합 테스트 (2-3시간)
- [ ] `tests/api/test_websocket_integration.py` 작성
  - [ ] `test_websocket_chat_end_to_end()` - 전체 시나리오 테스트
  - [ ] `test_websocket_multiple_messages()` - 여러 메시지 교환
  - [ ] `test_websocket_reconnection()` - 재연결 시나리오
- [ ] 테스트 실행: `uv run -- python -m pytest tests/api/test_websocket*.py`
- [ ] Git 커밋: "test: WebSocket 통합 테스트 추가"

### 4-2. E2E 테스트 (Playwright) (2-3시간)
- [ ] `web/tests/chat-websocket.spec.ts` 작성
  - [ ] 연결 상태 확인 테스트
  - [ ] 메시지 전송/수신 테스트
  - [ ] 타이핑 표시 확인 테스트
  - [ ] 스트리밍 청크 표시 테스트
  - [ ] 재연결 테스트
- [ ] E2E 테스트 실행: `cd web && npx playwright test`
- [ ] Git 커밋: "test: WebSocket 채팅 E2E 테스트 추가"

### 4-3. 부하 테스트 (선택, 1-2시간)
- [ ] `tests/load/websocket_load.py` 작성
  - [ ] 100개 동시 연결 시뮬레이션
  - [ ] 응답 시간 측정
  - [ ] 연결 안정성 확인
- [ ] 부하 테스트 실행 및 결과 분석
- [ ] Git 커밋: "test: WebSocket 부하 테스트 추가"

---

## Step 5: 문서화 및 배포 준비 (1일)

### 5-1. 문서 업데이트 (2-3시간)
- [ ] `docs/web/README.md` 업데이트
  - [ ] WebSocket 구현 내용 추가
  - [ ] 현재 상태 업데이트 (폴링 → WebSocket)
- [ ] `docs/api/README.md` 업데이트
  - [ ] WebSocket 엔드포인트 문서 추가
  - [ ] ChatService 설명 추가
- [ ] `docs/ARCHITECTURE.md` 업데이트
  - [ ] llm/ 모듈 아키텍처 추가
  - [ ] WebSocket 데이터 흐름 다이어그램 추가
- [ ] `docs/DECISIONS.md`에 ADR 추가
  - [ ] ADR-007: 채팅 프로토콜 - WebSocket 선택
- [ ] Git 커밋: "docs: WebSocket 채팅 구현 문서화"

### 5-2. 환경 변수 문서화 (30분)
- [ ] `README.md` 환경 변수 섹션 업데이트
  - [ ] `OPENAI_API_KEY` 필수 표시
  - [ ] `CHAT_REDIS_URL` 추가 (세션 캐시용)
- [ ] `.env.example` 파일 업데이트 (있다면)
- [ ] Git 커밋: "docs: 채팅 환경 변수 문서화"

### 5-3. 최종 회귀 테스트 (1-2시간)
- [ ] 전체 테스트 스위트 실행
  - [ ] `uv run -- python -m pytest tests/`
  - [ ] `cd web && npm test` (있다면)
  - [ ] `cd web && npx playwright test`
- [ ] 수동 테스트
  - [ ] 서버 기동: `./scripts/run_servers.sh`
  - [ ] 브라우저에서 채팅 기능 테스트
  - [ ] 여러 세션 동시 테스트
  - [ ] 네트워크 끊김 시뮬레이션
- [ ] 모든 테스트 통과 확인

### 5-4. 최종 커밋 및 PR (1시간)
- [ ] 변경사항 요약 작성
- [ ] 최종 커밋: "feat: WebSocket 기반 실시간 채팅 구현 완료"
- [ ] PR 생성 또는 main 브랜치 병합
- [ ] 태그 생성: `git tag -a v0.2.0 -m "WebSocket 채팅 구현"`

---

## 성공 기준 체크리스트

### 기능 요구사항
- [ ] WebSocket 연결 성공 (<500ms)
- [ ] 첫 토큰 도착 (<2초)
- [ ] 스트리밍 속도 (10-20 토큰/초)
- [ ] 사용자 메시지 즉시 UI 반영
- [ ] 에이전트 응답 실시간 스트리밍
- [ ] 연결 끊김 시 자동 재연결 (최대 5회)

### 비기능 요구사항
- [ ] 채팅 턴당 비용 <$0.01
- [ ] 50개 동시 연결 지원
- [ ] 기존 analysis 파이프라인 회귀 없음
- [ ] 테스트 커버리지 >80% (llm, api/chat 관련)

### 문서 요구사항
- [ ] API 문서 업데이트
- [ ] 아키텍처 문서 업데이트
- [ ] 환경 변수 문서화
- [ ] ADR 추가

---

## 위험 및 완화 방안

| 위험 | 완화 방안 |
|-----|----------|
| WebSocket 연결 끊김 | 재연결 로직 (지수 백오프 최대 5회) + Redis 컨텍스트 유지 |
| Analysis 파이프라인 중단 | Phase 1에서 회귀 테스트, 점진적 마이그레이션 |
| 토큰 추적 부정확 | 보수적 추정 (단어 수 × 1.3) + 하드 제한 |
| Redis 메모리 고갈 | TTL 1시간 + LRU 제거 정책 |
| 동시 연결 과부하 | 연결 제한 100개 + 부하 테스트 |

## 롤백 계획

- **Phase 1 실패**: `git revert`로 analysis 원복
- **Phase 2-3 실패**: WebSocket 엔드포인트 제거, 기존 REST API 유지
- **Phase 4 실패**: 프론트엔드만 롤백, 백엔드 API는 유지 (향후 재시도)
- **치명적 버그**: 환경 변수로 WebSocket 기능 비활성화

---

## 다음 단계

Phase B 완료 후:
1. 프로덕션 배포 (staging 환경에서 검증 후)
2. 사용자 피드백 수집
3. Vector DB 통합 (RAG) 준비 (Phase C)
