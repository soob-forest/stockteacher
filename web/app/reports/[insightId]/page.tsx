'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  ReportDetail,
  fetchReportDetail,
  toggleFavorite,
  startChatSession,
  ChatSession,
} from '../../../lib/api';
import { useChatWebSocket } from '../../../hooks/useChatWebSocket';

type PageProps = {
  params: { insightId: string };
};

const sentimentMeter = (score: number): string => {
  if (score > 0.4) return '🙂 ██████░░';
  if (score > 0.1) return '🙂 █████░░░';
  if (score < -0.4) return '☹️ ██░░░░░░';
  if (score < -0.1) return '☹️ ███░░░░░';
  return '😐 ████░░░░';
};

export default function ReportDetailPage({ params }: PageProps) {
  const { insightId } = params;
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState<ChatSession | null>(null);
  const [messageDraft, setMessageDraft] = useState('');

  // WebSocket hook for real-time chat
  const { messages, isConnected, error: wsError, isTyping, sendMessage } = useChatWebSocket(
    session?.session_id || null
  );

  useEffect(() => {
    let canceled = false;
    setLoading(true);
    fetchReportDetail(insightId)
      .then((detail) => {
        if (!canceled) {
          setReport(detail);
        }
      })
      .catch((err) => {
        if (!canceled) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (!canceled) {
          setLoading(false);
        }
      });
    return () => {
      canceled = true;
    };
  }, [insightId]);

  useEffect(() => {
    let canceled = false;
    startChatSession(insightId)
      .then((created) => {
        if (!canceled) {
          setSession(created);
        }
      })
      .catch((err) => setError(err.message));
    return () => {
      canceled = true;
    };
  }, [insightId]);

  // Update error from WebSocket
  useEffect(() => {
    if (wsError) {
      setError(wsError);
    }
  }, [wsError]);

  const sentimentLabel = useMemo(() => {
    if (!report) return '';
    if (report.sentiment_score > 0.2) return '긍정';
    if (report.sentiment_score < -0.2) return '부정';
    return '중립';
  }, [report]);

  async function handleFavorite(): Promise<void> {
    if (!report) return;
    setError(null);
    const next = !report.favorite;
    try {
      await toggleFavorite(report.insight_id, next);
      setReport({ ...report, favorite: next });
    } catch (err) {
      setError(err instanceof Error ? err.message : '즐겨찾기 변경 실패');
    }
  }

  function handleSend(): void {
    if (!messageDraft.trim()) return;
    sendMessage(messageDraft.trim());
    setMessageDraft('');
  }

  if (loading) {
    return (
      <section className="card">
        <span className="badge">상세 로딩 중</span>
      </section>
    );
  }

  if (error) {
    return (
      <section className="card">
        <h2>오류</h2>
        <p className="label" style={{ color: '#ff6b6b' }}>
          {error}
        </p>
      </section>
    );
  }

  if (!report) return null;

  return (
    <div className="grid" style={{ gap: '1.5rem' }}>
      <section className="card">
        <header
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem'
          }}
        >
          <div style={{ display: 'grid', gap: '0.4rem' }}>
            <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
              <h2 style={{ margin: 0 }}>{report.ticker}</h2>
              <span className="badge">{sentimentLabel}</span>
            </div>
            <div className="sentiment-meter">
              {sentimentMeter(report.sentiment_score)} ·{' '}
              {new Date(report.published_at).toLocaleString('ko-KR')}
            </div>
          </div>
          <button className="button" type="button" onClick={handleFavorite}>
            {report.favorite ? '즐겨찾기 해제' : '즐겨찾기'}
          </button>
        </header>
        <article style={{ display: 'grid', gap: '1rem', marginTop: '1.5rem' }}>
          <div>
            <span className="label">요약</span>
            <p style={{ lineHeight: 1.6 }}>{report.summary_text}</p>
          </div>
          <div>
            <span className="label">키워드</span>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {report.keywords.map((word) => (
                <span key={word} className="badge">
                  #{word}
                </span>
              ))}
            </div>
          </div>
          <div>
            <span className="label">이상 징후 점수</span>
            <div className="badge">{report.anomaly_score.toFixed(2)}</div>
          </div>
          <div>
            <span className="label">원문 링크</span>
            <div style={{ display: 'grid', gap: '0.35rem' }}>
              {report.source_refs.map((ref) => (
                <a
                  key={ref.url}
                  href={ref.url}
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: '#3a8dff' }}
                >
                  {ref.title}
                </a>
              ))}
            </div>
          </div>
          {report.attachments.length > 0 && (
            <div>
              <span className="label">첨부</span>
              <div style={{ display: 'grid', gap: '0.5rem' }}>
                {report.attachments.map((attachment) => (
                  <a
                    key={attachment.url}
                    href={attachment.url}
                    target="_blank"
                    rel="noreferrer"
                    className="button secondary"
                    style={{
                      display: 'inline-flex',
                      gap: '0.5rem',
                      alignItems: 'center'
                    }}
                  >
                    {attachment.label} ({attachment.type.toUpperCase()})
                  </a>
                ))}
              </div>
            </div>
          )}
        </article>
      </section>

      <section className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <h2>에이전트 대화</h2>
          <span style={{ fontSize: '0.9rem' }}>
            {isConnected ? '🟢 연결됨' : '🔴 연결 끊김'}
          </span>
        </div>
        <p className="label">
          리포트 내용을 바탕으로 후속 질문을 입력하면 에이전트가 답변합니다.
        </p>
        <div className="chat-panel">
          <div className="chat-messages">
            {messages.length === 0 ? (
              <div className="empty-state">
                아직 메시지가 없습니다. 질문을 입력해보세요.
              </div>
            ) : (
              messages.map((message) => (
                <div key={message.message_id} className="chat-message">
                  <span className="sender">{message.sender.toUpperCase()}</span>
                  <span>{message.content}</span>
                  <span className="label">
                    {new Date(message.created_at).toLocaleTimeString('ko-KR')}
                  </span>
                </div>
              ))
            )}
            {isTyping && (
              <div className="chat-message" style={{ opacity: 0.7 }}>
                <span className="sender">AGENT</span>
                <span>입력 중...</span>
              </div>
            )}
          </div>
          <div className="chat-input">
            <textarea
              placeholder="질문을 입력하세요..."
              value={messageDraft}
              onChange={(event) => setMessageDraft(event.target.value)}
            />
            <button
              className="button"
              type="button"
              onClick={handleSend}
              disabled={!isConnected || isTyping || messageDraft.trim().length === 0}
            >
              {isTyping ? '응답 대기 중...' : '전송'}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
