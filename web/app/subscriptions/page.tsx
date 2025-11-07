'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  Subscription,
  CreateSubscriptionPayload,
  fetchSubscriptions,
  createSubscription,
  updateAlertWindow,
  deleteSubscription
} from '../../lib/api';

type AlertOption = {
  value: string;
  label: string;
};

const alertOptions: AlertOption[] = [
  { value: 'intraday', label: '당일 즉시' },
  { value: 'daily_open', label: '매일 장 시작 전' },
  { value: 'daily_close', label: '매일 장 마감 후' },
  { value: 'weekly', label: '주간 요약' }
];

export default function SubscriptionsPage() {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [ticker, setTicker] = useState('');
  const [alertWindow, setAlertWindow] = useState(alertOptions[0].value);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    fetchSubscriptions()
      .then((data) => {
        if (mounted) {
          setSubscriptions(data);
        }
      })
      .catch((err) => setError(err.message));
    return () => {
      mounted = false;
    };
  }, []);

  const activeCount = useMemo(
    () => subscriptions.filter((item) => item.status === 'Active').length,
    [subscriptions]
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!ticker.trim()) {
      setError('종목 티커를 입력하세요.');
      return;
    }
    setLoading(true);
    const payload: CreateSubscriptionPayload = {
      ticker: ticker.trim().toUpperCase(),
      alert_window: alertWindow
    };
    try {
      const created = await createSubscription(payload);
      setSubscriptions((prev) => [...prev, created]);
      setTicker('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '등록에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }

  async function handleAlertChange(
    subscriptionId: string,
    value: string
  ): Promise<void> {
    setError(null);
    try {
      await updateAlertWindow(subscriptionId, value);
      setSubscriptions((prev) =>
        prev.map((item) =>
          item.subscription_id === subscriptionId
            ? { ...item, alert_window: value }
            : item
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : '알림 변경 실패');
    }
  }

  async function handleDelete(subscriptionId: string): Promise<void> {
    setError(null);
    try {
      await deleteSubscription(subscriptionId);
      setSubscriptions((prev) =>
        prev.filter((item) => item.subscription_id !== subscriptionId)
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : '구독 해지 실패');
    }
  }

  return (
    <div className="grid">
      <section className="card">
        <h2>구독 종목 등록</h2>
        <p className="label">
          감시할 종목 티커와 리포트 수신 시간을 선택하세요.
        </p>
        <form className="grid two" onSubmit={handleSubmit}>
          <label className="grid" htmlFor="ticker-input">
            <span className="label">종목 티커</span>
            <input
              id="ticker-input"
              className="input"
              placeholder="예: AAPL"
              value={ticker}
              onChange={(event) => setTicker(event.target.value)}
            />
          </label>

          <label className="grid" htmlFor="alert-window">
            <span className="label">알림 윈도우</span>
            <select
              id="alert-window"
              className="input"
              value={alertWindow}
              onChange={(event) => setAlertWindow(event.target.value)}
            >
              {alertOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <div className="actions" style={{ gridColumn: 'span 2' }}>
            <button className="button" type="submit" disabled={loading}>
              {loading ? '등록 중...' : '구독 추가'}
            </button>
          </div>
        </form>
        {error && <p className="label" style={{ color: '#ff6b6b' }}>{error}</p>}
      </section>

      <section className="card">
        <header
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}
        >
          <h2>구독 목록</h2>
          <span className="badge">활성 {activeCount}</span>
        </header>
        {subscriptions.length === 0 ? (
          <div className="empty-state">등록된 종목이 없습니다.</div>
        ) : (
          <div className="list">
            {subscriptions.map((item) => (
              <article key={item.subscription_id} className="list-item">
                <div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>
                    {item.ticker}
                  </div>
                  <div style={{ fontSize: '0.85rem', color: '#8d97ab' }}>
                    상태: {item.status} · 생성일:{' '}
                    {new Date(item.created_at).toLocaleString('ko-KR')}
                  </div>
                </div>
                <div className="actions">
                  <select
                    className="input"
                    value={item.alert_window}
                    onChange={(event) =>
                      handleAlertChange(
                        item.subscription_id,
                        event.target.value
                      )
                    }
                    style={{ width: '160px' }}
                  >
                    {alertOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  <button
                    className="button secondary"
                    onClick={() => handleDelete(item.subscription_id)}
                    type="button"
                  >
                    해지
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
