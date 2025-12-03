import { useEffect, useRef, useState } from 'react';
import { buildWebSocketUrl, fetchChatMessages } from '../lib/api';

interface ChatMessage {
  message_id: string;
  sender: 'user' | 'agent' | 'system';
  content: string;
  created_at: string;
}

const HISTORY_LIMIT = 20;

export function useChatWebSocket(sessionId: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  const [status, setStatus] = useState<'idle' | 'sending' | 'streaming'>('idle');
  const [latencyWarning, setLatencyWarning] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const latencyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const enableSseFallback =
    typeof process !== 'undefined' &&
    process.env.NEXT_PUBLIC_ENABLE_SSE_FALLBACK === 'true';

  const trimHistory = (items: ChatMessage[]): ChatMessage[] => {
    return items.slice(-HISTORY_LIMIT);
  };

  const startLatencyTimer = () => {
    if (latencyTimerRef.current) clearTimeout(latencyTimerRef.current);
    latencyTimerRef.current = setTimeout(() => {
      setLatencyWarning(true);
    }, 2500);
  };

  const clearLatencyTimer = () => {
    if (latencyTimerRef.current) {
      clearTimeout(latencyTimerRef.current);
      latencyTimerRef.current = null;
    }
    setLatencyWarning(false);
  };

  const mapErrorMessage = (code?: string, detail?: string): string => {
    if (code === 'cost_limit') return 'LLM 비용 상한을 초과해 응답이 중단되었습니다. 메시지를 축약해 다시 시도해주세요.';
    if (code === 'llm_unavailable') return '일시적 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
    if (code === 'session_not_found') return '채팅 세션을 찾을 수 없습니다. 페이지를 새로고침하세요.';
    if (code === 'report_not_found') return '리포트 정보를 불러오지 못했습니다.';
    return detail || '채팅 처리 중 오류가 발생했습니다.';
  };

  useEffect(() => {
    if (!sessionId) return;
    setMessages([]);
    setError(null);
    setBanner(null);
    setStatus('idle');
    clearLatencyTimer();
    let cancelled = false;

    const loadHistory = async () => {
      try {
        const history = await fetchChatMessages(sessionId);
        if (cancelled) return;
        setMessages(trimHistory(history));
      } catch (err) {
        if (cancelled) return;
        setError('초기 히스토리 로드에 실패했습니다.');
      }
    };
    loadHistory();

    const connect = () => {
      const ws = new WebSocket(buildWebSocketUrl(sessionId));
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0;
        setStatus('idle');
        setBanner(null);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'chunk') {
          // Streaming chunk received → append to agent message
          setStatus('streaming');
          clearLatencyTimer();
          setMessages((prev) => {
            const lastMsg = prev[prev.length - 1];
            if (lastMsg && lastMsg.sender === 'agent' && !lastMsg.message_id) {
              // Append to existing agent message
              return trimHistory([
                ...prev.slice(0, -1),
                { ...lastMsg, content: lastMsg.content + data.content },
              ]);
            } else {
              // Start new agent message
              return trimHistory([
                ...prev,
                {
                  message_id: '',
                  sender: 'agent',
                  content: data.content,
                  created_at: new Date().toISOString(),
                },
              ]);
            }
          });
          setIsTyping(true);
        } else if (data.type === 'done') {
          // Streaming complete
          setIsTyping(false);
          clearLatencyTimer();
          setStatus('idle');
          setMessages((prev) => {
            const lastMsg = prev[prev.length - 1];
            if (!lastMsg) return prev;
            return trimHistory([
              ...prev.slice(0, -1),
              { ...lastMsg, message_id: data.message_id || `msg-${Date.now()}` },
            ]);
          });
        } else if (data.type === 'error') {
          setError(mapErrorMessage(data.code, data.detail));
          setBanner(mapErrorMessage(data.code, data.detail));
          setIsTyping(false);
          clearLatencyTimer();
          setStatus('idle');
        }
      };

      ws.onerror = () => {
        setError('WebSocket 연결 오류');
        setBanner('연결 오류가 발생했습니다. 재시도 중입니다.');
        setIsConnected(false);
        setStatus('idle');
        clearLatencyTimer();
      };

      ws.onclose = () => {
        setIsConnected(false);
        setIsTyping(false);
        setStatus('idle');
        clearLatencyTimer();
        setBanner('연결이 끊어졌습니다. 재연결 중...');

        // Reconnect with exponential backoff
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
        reconnectAttemptsRef.current += 1;

        if (reconnectAttemptsRef.current <= 5) {
          setTimeout(connect, delay);
        } else {
          const fallbackMsg = enableSseFallback
            ? 'WebSocket 재연결 실패. SSE 폴백이 필요합니다(현재 미구현).'
            : 'WebSocket 재연결 실패. 네트워크를 확인하거나 다시 시도해주세요.';
          setError(fallbackMsg);
          setBanner(fallbackMsg);
        }
      };
    };

    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      clearLatencyTimer();
      cancelled = true;
    };
  }, [sessionId]);

  const sendMessage = (content: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('WebSocket 연결 없음');
      return;
    }
    if (status !== 'idle') {
      setError('이전 메시지 처리가 끝난 후 다시 시도해주세요.');
      return;
    }

    // Display user message immediately
    setMessages((prev) => trimHistory([
      ...prev,
      {
        message_id: `temp-${Date.now()}`,
        sender: 'user',
        content,
        created_at: new Date().toISOString(),
      },
    ]));

    setStatus('sending');
    setIsTyping(false);
    clearLatencyTimer();
    startLatencyTimer();
    setError(null);

    // Send to server
    wsRef.current.send(JSON.stringify({ type: 'message', content }));
  };

  return {
    messages,
    isConnected,
    error,
    isTyping,
    isSending: status !== 'idle',
    latencyWarning,
    banner,
    sendMessage,
  };
}
