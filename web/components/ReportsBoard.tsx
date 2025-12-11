'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import {
  ReportSummary,
  ReportFilter,
  fetchReports,
  toggleFavorite,
  updateReportStatus
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

function splitCsv(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

export function ReportsBoard({
  initialFilter = {},
  title = '리포트 목록',
  lockFavoritesOnly = false
}: ReportsBoardProps) {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [filter, setFilter] = useState<ReportFilter>({
    ...initialFilter,
    favorites_only: lockFavoritesOnly ? true : initialFilter.favorites_only,
    vector: initialFilter.vector ?? false
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tickersInput, setTickersInput] = useState(
    (initialFilter.tickers || []).join(', ')
  );
  const [keywordsInput, setKeywordsInput] = useState(
    (initialFilter.keywords || []).join(', ')
  );

  useEffect(() => {
    setTickersInput((filter.tickers || []).join(', '));
    setKeywordsInput((filter.keywords || []).join(', '));
  }, [filter.tickers, filter.keywords]);

  const activeBadges = useMemo(() => {
    const badges: string[] = [];
    if (filter.tickers?.length) {
      badges.push(...filter.tickers.map((t) => `#${t}`));
    }
    if (filter.keywords?.length) {
      badges.push(...filter.keywords.map((kw) => `키워드:${kw}`));
    }
    if (filter.date_from) badges.push(`from ${filter.date_from}`);
    if (filter.date_to) badges.push(`to ${filter.date_to}`);
    if (filter.sentiment) badges.push(`감성:${filter.sentiment}`);
    if (filter.favorites_only) badges.push('즐겨찾기');
    if (filter.urgent_only) badges.push('긴급(이상≥0.4)');
    if (filter.vector) badges.push('벡터');
    return badges;
  }, [filter]);

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

  async function handleStatusUpdate(
    insightId: string,
    next: 'published' | 'hidden'
  ): Promise<void> {
    setError(null);
    try {
      const updated = await updateReportStatus(insightId, { status: next });
      setReports((prev) =>
        prev.map((report) =>
          report.insight_id === insightId
            ? { ...report, status: updated.status }
            : report
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : '상태 변경 실패');
    }
  }

  function resetFilters(): void {
    setTickersInput('');
    setKeywordsInput('');
    setFilter({
      ...initialFilter,
      favorites_only: lockFavoritesOnly ? true : initialFilter.favorites_only
    });
  }

  return (
    <div className="grid">
      <section className="card">
        <h2>리포트 필터</h2>
        <div className="grid two">
          <label className="grid">
            <span className="label">티커(쉼표 구분)</span>
            <input
              className="input"
              placeholder="AAPL, TSLA"
              value={tickersInput}
              onChange={(event) => {
                const next = event.target.value;
                setTickersInput(next);
                setFilter((prev) => ({
                  ...prev,
                  tickers: next ? splitCsv(next.toUpperCase()) : undefined
                }));
              }}
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
            <span className="label">키워드(쉼표 구분)</span>
            <input
              className="input"
              placeholder="battery, AI"
              value={keywordsInput}
              onChange={(event) => {
                const next = event.target.value;
                setKeywordsInput(next);
                setFilter((prev) => ({
                  ...prev,
                  keywords: next ? splitCsv(next) : undefined
                }));
              }}
            />
          </label>

          <label className="grid">
            <span className="label">검색(티커/헤드라인/태그)</span>
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

          <label className="grid">
            <span className="label">게시 상태</span>
            <select
              className="input"
              value={filter.status ?? ''}
              onChange={(event) =>
                setFilter((prev) => ({
                  ...prev,
                  status: event.target.value || undefined
                }))
              }
            >
              <option value="">게시됨만</option>
              <option value="all">전체</option>
              <option value="hidden">숨김만</option>
              <option value="draft">대기(draft)</option>
            </select>
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
          <label
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
            title="벡터 기반 정렬/검색을 실험적으로 활성화합니다."
          >
            <input
              type="checkbox"
              checked={Boolean(filter.vector)}
              onChange={(event) =>
                setFilter((prev) => ({
                  ...prev,
                  vector: event.target.checked || undefined
                }))
              }
            />
            <span className="label" style={{ margin: 0 }}>
              벡터 검색/정렬(실험)
            </span>
          </label>
        </div>

        <div className="grid two" style={{ marginTop: '0.75rem' }}>
          <label className="grid">
            <span className="label">시작일</span>
            <input
              type="date"
              className="input"
              value={filter.date_from ?? ''}
              onChange={(event) =>
                setFilter((prev) => ({
                  ...prev,
                  date_from: event.target.value || undefined
                }))
              }
            />
          </label>
          <label className="grid">
            <span className="label">종료일</span>
            <input
              type="date"
              className="input"
              value={filter.date_to ?? ''}
              onChange={(event) =>
                setFilter((prev) => ({
                  ...prev,
                  date_to: event.target.value || undefined
                }))
              }
            />
          </label>
          <label
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            <input
              type="checkbox"
              checked={Boolean(filter.urgent_only)}
              onChange={(event) =>
                setFilter((prev) => ({
                  ...prev,
                  urgent_only: event.target.checked ? true : undefined
                }))
              }
            />
            <span className="label" style={{ margin: 0 }}>
              긴급만(이상 점수 ≥ 0.4)
            </span>
          </label>
          <button className="button secondary" type="button" onClick={resetFilters}>
            필터 초기화
          </button>
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
        {activeBadges.length > 0 && (
          <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', margin: '0.5rem 0' }}>
            {activeBadges.map((badge) => (
              <span key={badge} className="badge secondary">
                {badge}
              </span>
            ))}
          </div>
        )}
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
                      {report.status !== 'published' && (
                        <span className="badge secondary">
                          {report.status === 'hidden' ? '숨김' : '대기'}
                        </span>
                      )}
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
                      className="button secondary"
                      type="button"
                      onClick={() =>
                        handleStatusUpdate(
                          report.insight_id,
                          report.status === 'hidden' ? 'published' : 'hidden'
                        )
                      }
                    >
                      {report.status === 'hidden' ? '복구(게시)' : '숨기기'}
                    </button>
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
