'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  ReportSummary,
  ReportDetail,
  fetchReportDetail,
  toggleFavorite,
  startChatSession,
  ChatSession,
  updateReportStatus,
  fetchRelatedReports
} from '../../../lib/api';
import { useChatWebSocket } from '../../../hooks/useChatWebSocket';

type PageProps = {
  params: { insightId: string };
};

function RelatedCard({ item }: { item: ReportSummary }) {
  const sentimentLabel =
    item.sentiment_score > 0.2
      ? '긍정'
      : item.sentiment_score < -0.2
        ? '부정'
        : '중립';
  return (
    <article className="list-item">
      <div style={{ display: 'grid', gap: '0.4rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span style={{ fontWeight: 600 }}>{item.ticker}</span>
          <span className="badge">{sentimentLabel}</span>
        </div>
        <div style={{ color: '#c7cedd', fontSize: '0.9rem' }}>{item.headline}</div>
        <div className="sentiment-meter">
          {new Date(item.published_at).toLocaleString('ko-KR')}
        </div>
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          {item.tags.map((tag) => (
            <span key={`${item.insight_id}-${tag}`} className="badge">
              #{tag}
            </span>
          ))}
        </div>
      </div>
      <div className="actions">
        <a className="button secondary" href={`/reports/${item.insight_id}`}>
          열기
        </a>
      </div>
    </article>
  );
}

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
  const [chatError, setChatError] = useState<string | null>(null);
  const [related, setRelated] = useState<ReportSummary[]>([]);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [relatedError, setRelatedError] = useState<string | null>(null);
  const [session, setSession] = useState<ChatSession | null>(null);
  const [messageDraft, setMessageDraft] = useState('');

  // WebSocket hook for real-time chat
  const {
    messages,
    isConnected,
    error: wsError,
    isTyping,
    isSending,
    latencyWarning,
    sendMessage
  } = useChatWebSocket(session?.session_id || null);
  const banner = null;

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
    setRelatedLoading(true);
    fetchRelatedReports(insightId)
      .then((items) => {
        if (!canceled) {
          setRelated(items);
        }
      })
      .catch((err) => {
        if (!canceled) {
          setRelatedError(err.message);
        }
      })
      .finally(() => {
        if (!canceled) {
          setRelatedLoading(false);
        }
      });
    return () => {
      canceled = true;
    };
  }, [insightId]);

  useEffect(() => {
    let canceled = false;
    const key = `chatSession:${insightId}`;
    const ensureSession = async () => {
      try {
        const savedRaw = typeof window !== 'undefined' ? localStorage.getItem(key) : null;
        if (savedRaw) {
          const saved = JSON.parse(savedRaw) as ChatSession;
          if (saved?.session_id) {
            setSession(saved);
            return;
          }
        }
        const created = await startChatSession(insightId);
        if (canceled) return;
        setSession(created);
        if (typeof window !== 'undefined') {
          localStorage.setItem(key, JSON.stringify(created));
        }
      } catch (err) {
        if (canceled) return;
        setError(err instanceof Error ? err.message : '채팅 세션 생성에 실패했습니다.');
      }
    };
    ensureSession();
    return () => {
      canceled = true;
    };
  }, [insightId]);

  // Update error from WebSocket
  useEffect(() => {
    if (wsError) {
      setChatError(wsError);
    } else {
      setChatError(null);
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

  async function handleStatusChange(next: 'published' | 'hidden'): Promise<void> {
    if (!report) return;
    setError(null);
    try {
      const updated = await updateReportStatus(report.insight_id, { status: next });
      setReport(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : '상태 변경 실패');
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
              {report.status !== 'published' && (
                <span className="badge secondary">
                  {report.status === 'hidden' ? '숨김' : '대기'}
                </span>
              )}
            </div>
            <div className="sentiment-meter">
              {sentimentMeter(report.sentiment_score)} ·{' '}
              {new Date(report.published_at).toLocaleString('ko-KR')}
            </div>
          </div>
          <button className="button" type="button" onClick={handleFavorite}>
            {report.favorite ? '즐겨찾기 해제' : '즐겨찾기'}
          </button>
          <button
            className="button secondary"
            type="button"
            onClick={() =>
              handleStatusChange(report.status === 'hidden' ? 'published' : 'hidden')
            }
          >
            {report.status === 'hidden' ? '복구(게시)' : '숨기기'}
          </button>
        </header>
        {report.status !== 'published' && (
          <div
            className="badge"
            style={{
              background: report.status === 'hidden' ? '#ffecec' : '#fff5d6',
              color: report.status === 'hidden' ? '#b30000' : '#a05a00',
              marginTop: '0.75rem'
            }}
          >
            {report.status === 'hidden'
              ? '이 리포트는 숨김 상태입니다. 사용자에게 노출되지 않습니다.'
              : '이 리포트는 게시 대기(draft) 상태입니다.'}
          </div>
        )}
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
        <header
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}
        >
          <h2>관련 리포트</h2>
          {relatedLoading && <span className="badge">불러오는 중</span>}
        </header>
        {relatedError && (
          <div className="badge" style={{ background: '#ffecec', color: '#b30000' }}>
            {relatedError}
          </div>
        )}
        {relatedLoading && related.length === 0 && (
          <div className="list">
            {[0, 1, 2].map((idx) => (
              <div
                key={`skeleton-${idx}`}
                className="list-item"
                style={{ opacity: 0.4 }}
              >
                <div className="badge secondary" style={{ width: '5rem' }}>
                  로딩중
                </div>
                <div className="label" style={{ marginTop: '0.5rem' }}>
                  관련 리포트를 불러오는 중입니다...
                </div>
              </div>
            ))}
          </div>
        )}
        {related.length === 0 && !relatedLoading ? (
          <div className="empty-state">
            관련 리포트가 없습니다.{' '}
            <a href="/reports" className="button secondary" style={{ marginLeft: '0.5rem' }}>
              전체 리포트 보기
            </a>
          </div>
        ) : (
          <div className="list">
            {related.map((item) => (
              <RelatedCard key={item.insight_id} item={item} />
            ))}
          </div>
        )}
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
        {(chatError || banner) && (
          <div
            className="badge"
            style={{ background: '#ffecec', color: '#b30000', marginBottom: '0.5rem' }}
          >
            {chatError || banner}
          </div>
        )}
        {latencyWarning && !chatError && (
          <div
            className="badge"
            style={{ background: '#fff5d6', color: '#a05a00', marginBottom: '0.5rem' }}
          >
            응답이 지연되고 있습니다. 잠시만 기다려주세요.
          </div>
        )}
        <div className="chat-panel">
          <div className="chat-messages">
            {messages.length === 0 ? (
              <div className="empty-state">
                아직 메시지가 없습니다. 질문을 입력해보세요.
              </div>
            ) : (
              messages.map((message, idx) => (
                <div
                  key={message.message_id || `temp-${idx}`}
                  className="chat-message"
                >
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
              disabled={
                !isConnected || isTyping || isSending || messageDraft.trim().length === 0
              }
            >
              {isTyping ? '응답 대기 중...' : isSending ? '전송 중...' : '전송'}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
