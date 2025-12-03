'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  NotificationChannel,
  NotificationFrequency,
  NotificationPolicy,
  NotificationPolicyPayload,
  NotificationWindow,
  fetchNotificationPolicy,
  fetchNotificationTimezones,
  saveNotificationPolicy
} from '../lib/api';

const windowOptions: { value: NotificationWindow; label: string }[] = [
  { value: 'morning_open', label: '장 시작 전' },
  { value: 'daily_close', label: '장 마감 후' },
  { value: 'immediate', label: '즉시' }
];

const frequencyOptions: { value: NotificationFrequency; label: string }[] = [
  { value: 'daily', label: '매일' },
  { value: 'weekly', label: '주간' }
];

const channelOptions: { value: NotificationChannel; label: string }[] = [
  { value: 'email', label: '이메일' },
  { value: 'web-push', label: '웹 푸시' }
];

const fallbackTimezones = [
  'Asia/Seoul',
  'Asia/Tokyo',
  'Asia/Shanghai',
  'Asia/Singapore',
  'Europe/London',
  'Europe/Berlin',
  'America/New_York',
  'America/Los_Angeles',
  'America/Sao_Paulo',
  'Australia/Sydney'
];

function normalizePolicy(data: NotificationPolicy): NotificationPolicyPayload {
  return {
    timezone: data.timezone,
    window: data.window,
    frequency: data.frequency,
    channels: data.channels,
    quiet_hours_start: data.quiet_hours_start ?? null,
    quiet_hours_end: data.quiet_hours_end ?? null
  };
}

export function NotificationSettings() {
  const [policy, setPolicy] = useState<NotificationPolicyPayload | null>(null);
  const [timezones, setTimezones] = useState<string[]>(fallbackTimezones);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    let canceled = false;
    async function load() {
      try {
        setError(null);
        const [tzList, policyData] = await Promise.all([
          fetchNotificationTimezones().catch(() => fallbackTimezones),
          fetchNotificationPolicy()
        ]);
        if (canceled) return;
        setTimezones(tzList.length > 0 ? tzList : fallbackTimezones);
        setPolicy(normalizePolicy(policyData));
      } catch (err) {
        if (canceled) return;
        setError(err instanceof Error ? err.message : '알림 정책을 불러오지 못했습니다.');
      } finally {
        if (!canceled) {
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      canceled = true;
    };
  }, []);

  const quietHoursEnabled = useMemo(() => {
    if (!policy) return false;
    return Boolean(policy.quiet_hours_start && policy.quiet_hours_end);
  }, [policy]);

  function updateChannel(channel: NotificationChannel, checked: boolean) {
    if (!policy) return;
    const nextChannels = checked
      ? Array.from(new Set([...policy.channels, channel]))
      : policy.channels.filter((c) => c !== channel);
    setPolicy({ ...policy, channels: nextChannels });
  }

  function handleQuietToggle(checked: boolean) {
    if (!policy) return;
    if (!checked) {
      setPolicy({
        ...policy,
        quiet_hours_start: null,
        quiet_hours_end: null
      });
      return;
    }
    setPolicy({
      ...policy,
      quiet_hours_start: policy.quiet_hours_start ?? '22:00',
      quiet_hours_end: policy.quiet_hours_end ?? '07:00'
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!policy) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const payload = quietHoursEnabled
        ? policy
        : { ...policy, quiet_hours_start: null, quiet_hours_end: null };
      const saved = await saveNotificationPolicy(payload);
      setPolicy(normalizePolicy(saved));
      setSuccess('알림 정책을 저장했습니다.');
    } catch (err) {
      setError(err instanceof Error ? err.message : '알림 정책 저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <section className="card">
        <h2>알림 정책</h2>
        <p className="label">불러오는 중...</p>
      </section>
    );
  }

  if (!policy) {
    return (
      <section className="card">
        <h2>알림 정책</h2>
        <p className="label" style={{ color: '#ff6b6b' }}>
          알림 정책을 불러오지 못했습니다.
        </p>
      </section>
    );
  }

  return (
    <section className="card">
      <h2>알림 정책</h2>
      <p className="label">
        시간대·윈도우·채널을 선택하고 조용한 시간을 설정하세요.
      </p>
      <form className="grid two" onSubmit={handleSubmit}>
        <label className="grid" htmlFor="timezone-select">
          <span className="label">시간대</span>
          <select
            id="timezone-select"
            className="input"
            value={policy.timezone}
            data-testid="notification-timezone"
            onChange={(event) =>
              setPolicy({ ...policy, timezone: event.target.value })
            }
          >
            {timezones.map((tz) => (
              <option key={tz} value={tz}>
                {tz}
              </option>
            ))}
          </select>
        </label>

        <label className="grid" htmlFor="window-select">
          <span className="label">알림 윈도우</span>
          <select
            id="window-select"
            className="input"
            value={policy.window}
            data-testid="notification-window"
            onChange={(event) =>
              setPolicy({
                ...policy,
                window: event.target.value as NotificationWindow
              })
            }
          >
            {windowOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="grid" htmlFor="frequency-select">
          <span className="label">빈도</span>
          <select
            id="frequency-select"
            className="input"
            value={policy.frequency}
            data-testid="notification-frequency"
            onChange={(event) =>
              setPolicy({
                ...policy,
                frequency: event.target.value as NotificationFrequency
              })
            }
          >
            {frequencyOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <fieldset className="grid" style={{ minWidth: 0 }}>
          <legend className="label">채널</legend>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            {channelOptions.map((option) => (
              <label
                key={option.value}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem'
                }}
              >
                <input
                  type="checkbox"
                  checked={policy.channels.includes(option.value)}
                  onChange={(event) => updateChannel(option.value, event.target.checked)}
                  data-testid={`notification-channel-${option.value}`}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="grid" style={{ gridColumn: 'span 2' }}>
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.6rem'
            }}
          >
              <input
                type="checkbox"
                checked={quietHoursEnabled}
                data-testid="quiet-hours-toggle"
                onChange={(event) => handleQuietToggle(event.target.checked)}
              />
            <span className="label" style={{ margin: 0 }}>
              조용한 시간(Quiet hours) 설정
            </span>
          </label>
          {quietHoursEnabled && (
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <label className="grid" style={{ minWidth: '160px' }}>
                <span className="label">시작</span>
                <input
                  type="time"
                  className="input"
                  value={policy.quiet_hours_start ?? ''}
                  data-testid="quiet-start"
                  onChange={(event) =>
                    setPolicy({
                      ...policy,
                      quiet_hours_start: event.target.value || null
                    })
                  }
                />
              </label>
              <label className="grid" style={{ minWidth: '160px' }}>
                <span className="label">종료</span>
                <input
                  type="time"
                  className="input"
                  value={policy.quiet_hours_end ?? ''}
                  data-testid="quiet-end"
                  onChange={(event) =>
                    setPolicy({
                      ...policy,
                      quiet_hours_end: event.target.value || null
                    })
                  }
                />
              </label>
            </div>
          )}
          <p className="label">
            조용한 시간대에는 알림을 발송하지 않습니다. (선택 사항)
          </p>
        </div>

        {error && (
          <p className="label" style={{ color: '#ff6b6b' }}>
            {error}
          </p>
        )}
        {success && (
          <p className="label" style={{ color: '#8be28b' }}>
            {success}
          </p>
        )}

        <div className="actions" style={{ gridColumn: 'span 2' }}>
          <button className="button" type="submit" disabled={saving}>
            {saving ? '저장 중...' : '알림 정책 저장'}
          </button>
        </div>
      </form>
    </section>
  );
}
