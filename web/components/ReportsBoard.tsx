'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import {
  ReportSummary,
  ReportFilter,
  fetchReports,
  toggleFavorite
} from '../lib/api';

const sentimentLabels: Record<
  'positive' | 'neutral' | 'negative',
  { label: string; meter: string }
> = {
  positive: { label: '긍정', meter: '🙂 █████░░░' },
  neutral: { label: '중립', meter: '😐 ████░░░░' },
  negative: { label: '부정', meter: '☹️ ██░░░░░░' }
};

type ReportsBoardProps = {
  initialFilter?: ReportFilter;
  title?: string;
  lockFavoritesOnly?: boolean;
};

export function ReportsBoard({
  initialFilter = {},
  title = '리포트 목록',
  lockFavoritesOnly = false
}: ReportsBoardProps) {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [filter, setFilter] = useState<ReportFilter>(initialFilter);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let canceled = false;
    setLoading(true);
    fetchReports(filter)
      .then((data) => {
        if (!canceled) {
          setReports(data);
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
  }, [filter]);

  async function handleFavoriteToggle(
    insightId: string,
    next: boolean
  ): Promise<void> {
    setError(null);
    try {
      await toggleFavorite(insightId, next);
      setReports((prev) =>
        prev.map((report) =>
          report.insight_id === insightId
            ? { ...report, favorite: next }
            : report
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : '즐겨찾기 실패');
    }
  }

  return (
    <div className="grid">
      <section className="card">
        <h2>리포트 필터</h2>
        <div className="grid two">
          <label className="grid">
            <span className="label">날짜</span>
            <input
              type="date"
              className="input"
              value={filter.date ?? ''}
              onChange={(event) =>
                setFilter((prev) => ({
                  ...prev,
                  date: event.target.value || undefined
                }))
              }
            />
          </label>

          <label className="grid">
            <span className="label">감성</span>
            <select
              className="input"
              value={filter.sentiment ?? ''}
              onChange={(event) =>
                setFilter((prev) => ({
                  ...prev,
                  sentiment: (event.target.value ||
                    undefined) as ReportFilter['sentiment']
                }))
              }
            >
              <option value="">전체</option>
              <option value="positive">긍정</option>
              <option value="neutral">중립</option>
              <option value="negative">부정</option>
            </select>
          </label>

          <label className="grid">
            <span className="label">검색</span>
            <input
              className="input"
              placeholder="티커, 키워드, 헤드라인 검색"
              value={filter.search ?? ''}
              onChange={(event) =>
                setFilter((prev) => ({
                  ...prev,
                  search: event.target.value || undefined
                }))
              }
            />
          </label>

          {!lockFavoritesOnly && (
            <label
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
            >
              <input
                type="checkbox"
                checked={Boolean(filter.favorites_only)}
                onChange={(event) =>
                  setFilter((prev) => ({
                    ...prev,
                    favorites_only: event.target.checked ? true : undefined
                  }))
                }
              />
              <span className="label" style={{ margin: 0 }}>
                즐겨찾기만 보기
              </span>
            </label>
          )}
        </div>
      </section>

      <section className="card">
        <header
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}
        >
          <h2>{title}</h2>
          {loading && <span className="badge">불러오는 중</span>}
        </header>
        {error && <p className="label" style={{ color: '#ff6b6b' }}>{error}</p>}
        {reports.length === 0 && !loading ? (
          <div className="empty-state">조건에 해당하는 리포트가 없습니다.</div>
        ) : (
          <div className="list">
            {reports.map((report) => {
              const sentiment =
                report.sentiment_score > 0.2
                  ? sentimentLabels.positive
                  : report.sentiment_score < -0.2
                    ? sentimentLabels.negative
                    : sentimentLabels.neutral;
              return (
                <article key={report.insight_id} className="list-item">
                  <div style={{ display: 'grid', gap: '0.4rem' }}>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <span
                        style={{ fontWeight: 600, fontSize: '1.05rem' }}
                      >
                        {report.ticker}
                      </span>
                      <span className="badge">{sentiment.label}</span>
                    </div>
                    <div style={{ color: '#c7cedd', fontSize: '0.9rem' }}>
                      {report.headline}
                    </div>
                    <div className="sentiment-meter">
                      {sentiment.meter} ·{' '}
                      {new Date(report.published_at).toLocaleString('ko-KR')}
                    </div>
                    <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                      {report.tags.map((tag) => (
                        <span key={tag} className="badge">
                          #{tag}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="actions">
                    <Link className="button secondary" href={`/reports/${report.insight_id}`}>
                      상세
                    </Link>
                    <button
                      className="button"
                      type="button"
                      onClick={() =>
                        handleFavoriteToggle(report.insight_id, !report.favorite)
                      }
                    >
                      {report.favorite ? '즐겨찾기 해제' : '즐겨찾기'}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
