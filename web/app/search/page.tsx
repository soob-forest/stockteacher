'use client';

import { useEffect, useState } from 'react';
import { ReportSummary, fetchReports } from '../../lib/api';

type SearchResult = {
  items: ReportSummary[];
  loading: boolean;
  error: string | null;
};

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [tickers, setTickers] = useState('');
  const [keywords, setKeywords] = useState('');
  const [result, setResult] = useState<SearchResult>({
    items: [],
    loading: false,
    error: null,
  });

  const handleSearch = async () => {
    setResult((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const params = new URLSearchParams();
      params.set('query', query);
      tickers
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean)
        .forEach((t) => params.append('tickers', t));
      keywords
        .split(',')
        .map((k) => k.trim())
        .filter(Boolean)
        .forEach((k) => params.append('keywords', k));
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'}/api/search?${params.toString()}`, {
        method: 'GET',
        headers: { Accept: 'application/json' },
        cache: 'no-store',
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || '검색 실패');
      }
      const data = (await res.json()) as ReportSummary[];
      setResult({ items: data, loading: false, error: null });
    } catch (err) {
      setResult({ items: [], loading: false, error: err instanceof Error ? err.message : '검색 실패' });
    }
  };

  useEffect(() => {
    // 초기 렌더링 시 최근 리포트를 불러와 빈 상태를 채운다.
    fetchReports()
      .then((items) => setResult({ items, loading: false, error: null }))
      .catch(() => setResult({ items: [], loading: false, error: null }));
  }, []);

  return (
    <div className="card" style={{ display: 'grid', gap: '1rem' }}>
      <h2>벡터 검색 (실험)</h2>
      <div style={{ display: 'grid', gap: '0.5rem' }}>
        <input
          type="text"
          placeholder="자연어 질의"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <input
          type="text"
          placeholder="티커 (쉼표로 구분)"
          value={tickers}
          onChange={(e) => setTickers(e.target.value)}
        />
        <input
          type="text"
          placeholder="키워드 (쉼표로 구분)"
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
        />
        <button className="button" type="button" onClick={handleSearch} disabled={result.loading || !query.trim()}>
          {result.loading ? '검색 중...' : '검색'}
        </button>
      </div>
      {result.error && <div className="badge" style={{ background: '#ffecec', color: '#b30000' }}>{result.error}</div>}
      <div className="list">
        {result.items.map((item) => (
          <article key={item.insight_id} className="list-item">
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <span style={{ fontWeight: 600 }}>{item.ticker}</span>
              <span className="badge">{new Date(item.published_at).toLocaleString('ko-KR')}</span>
            </div>
            <div style={{ color: '#c7cedd', fontSize: '0.9rem' }}>{item.headline}</div>
            <a className="button secondary" href={`/reports/${item.insight_id}`} style={{ marginTop: '0.5rem' }}>
              열기
            </a>
          </article>
        ))}
        {result.items.length === 0 && !result.loading && <div className="empty-state">검색 결과가 없습니다.</div>}
      </div>
    </div>
  );
}
