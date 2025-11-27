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
          // Streaming chunk received → append to agent message
          setMessages((prev) => {
            const lastMsg = prev[prev.length - 1];
            if (lastMsg && lastMsg.sender === 'agent' && !lastMsg.message_id) {
              // Append to existing agent message
              return [
                ...prev.slice(0, -1),
                { ...lastMsg, content: lastMsg.content + data.content },
              ];
            } else {
              // Start new agent message
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
          // Streaming complete
          setIsTyping(false);
          setMessages((prev) => {
            const lastMsg = prev[prev.length - 1];
            return [
              ...prev.slice(0, -1),
              { ...lastMsg, message_id: data.message_id || `msg-${Date.now()}` },
            ];
          });
        } else if (data.type === 'error') {
          setError(data.detail);
          setIsTyping(false);
        }
      };

      ws.onerror = () => {
        setError('WebSocket 연결 오류');
        setIsConnected(false);
      };

      ws.onclose = () => {
        setIsConnected(false);
        setIsTyping(false);

        // Reconnect with exponential backoff
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

    // Display user message immediately
    setMessages((prev) => [
      ...prev,
      {
        message_id: `temp-${Date.now()}`,
        sender: 'user',
        content,
        created_at: new Date().toISOString(),
      },
    ]);

    // Send to server
    wsRef.current.send(JSON.stringify({ type: 'message', content }));
  };

  return { messages, isConnected, error, isTyping, sendMessage };
}
