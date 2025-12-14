'use client';

import { useState } from 'react';
import { ReportSummary, searchReports } from '../../lib/api';

type SearchState = {
  items: ReportSummary[];
  loading: boolean;
  error: string | null;
};

const sentimentMeter = (score: number): string => {
  if (score > 0.4) return '🙂 ██████░░';
  if (score > 0.1) return '🙂 █████░░░';
  if (score < -0.4) return '☹️ ██░░░░░░';
  if (score < -0.1) return '☹️ ███░░░░░';
  return '😐 ████░░░░';
};

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [tickers, setTickers] = useState('');
  const [keywords, setKeywords] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [sentiment, setSentiment] = useState<'positive' | 'neutral' | 'negative' | ''>('');
  const [state, setState] = useState<SearchState>({
    items: [],
    loading: false,
    error: null,
  });

  const handleSearch = async () => {
    if (!query.trim()) return;

    setState({ items: [], loading: true, error: null });

    try {
      const results = await searchReports({
        query: query.trim(),
        tickers: tickers
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
        keywords: keywords
          .split(',')
          .map((k) => k.trim())
          .filter(Boolean),
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        sentiment: sentiment || undefined,
        limit: 20,
      });
      setState({ items: results, loading: false, error: null });
    } catch (err) {
      setState({
        items: [],
        loading: false,
        error: err instanceof Error ? err.message : '검색 실패',
      });
    }
  };

  return (
    <div className="card" style={{ display: 'grid', gap: '1rem' }}>
      <div>
        <h2>벡터 검색 (실험)</h2>
        <p className="label">
          자연어 질의로 유사한 리포트를 검색합니다. 결과는 벡터 유사도 기반으로 정렬됩니다.
        </p>
      </div>

      {/* 검색 입력 폼 */}
      <div style={{ display: 'grid', gap: '0.5rem' }}>
        <input
          type="text"
          placeholder="자연어 질의 (예: 배터리 기술 혁신 관련 긍정적 뉴스)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <input
          type="text"
          placeholder="티커 (쉼표로 구분, 예: AAPL, TSLA)"
          value={tickers}
          onChange={(e) => setTickers(e.target.value)}
        />
        <input
          type="text"
          placeholder="키워드 (쉼표로 구분, 예: battery, AI)"
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
        />

        {/* 날짜 범위 필터 */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
          <input
            type="date"
            placeholder="시작 날짜"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
          <input
            type="date"
            placeholder="종료 날짜"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </div>

        {/* 감성 필터 */}
        <select
          value={sentiment}
          onChange={(e) => setSentiment(e.target.value as 'positive' | 'neutral' | 'negative' | '')}
        >
          <option value="">감성 (전체)</option>
          <option value="positive">긍정</option>
          <option value="neutral">중립</option>
          <option value="negative">부정</option>
        </select>

        <button
          className="button"
          type="button"
          onClick={handleSearch}
          disabled={state.loading || !query.trim()}
        >
          {state.loading ? '검색 중...' : '검색'}
        </button>
      </div>

      {/* 에러 표시 */}
      {state.error && (
        <div className="badge" style={{ background: '#ffecec', color: '#b30000' }}>
          {state.error}
        </div>
      )}

      {/* 검색 결과 */}
      <div className="list">
        {state.items.map((item, index) => {
          const sentimentLabel =
            item.sentiment_score > 0.2
              ? '긍정'
              : item.sentiment_score < -0.2
              ? '부정'
              : '중립';

          return (
            <article key={item.insight_id} className="list-item">
              <div style={{ display: 'grid', gap: '0.4rem' }}>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                  <span className="badge secondary" style={{ fontSize: '0.85rem' }}>
                    {index + 1}위
                  </span>
                  <span style={{ fontWeight: 600 }}>{item.ticker}</span>
                  <span className="badge">{sentimentLabel}</span>
                  {item.status !== 'published' && (
                    <span className="badge secondary">
                      {item.status === 'hidden' ? '숨김' : '대기'}
                    </span>
                  )}
                </div>
                <div style={{ color: '#c7cedd', fontSize: '0.9rem' }}>{item.headline}</div>
                <div className="sentiment-meter">
                  {sentimentMeter(item.sentiment_score)} ·{' '}
                  {new Date(item.published_at).toLocaleString('ko-KR')}
                </div>
                {item.tags.length > 0 && (
                  <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                    {item.tags.map((tag) => (
                      <span key={`${item.insight_id}-${tag}`} className="badge">
                        #{tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <a className="button secondary" href={`/reports/${item.insight_id}`}>
                열기
              </a>
            </article>
          );
        })}
        {state.items.length === 0 && !state.loading && (
          <div className="empty-state">
            {query ? '검색 결과가 없습니다.' : '검색어를 입력하세요.'}
          </div>
        )}
      </div>
    </div>
  );
}
