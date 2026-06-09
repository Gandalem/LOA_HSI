import React, { useEffect, useState } from 'react';
import { getDatasetStats } from '../api/client.js';

function formatBytes(value) {
  const n = Number(value || 0);
  if (n >= 1024 * 1024 * 1024) return `${(n / 1024 / 1024 / 1024).toFixed(2)}GB`;
  if (n >= 1024 * 1024) return `${(n / 1024 / 1024).toFixed(2)}MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(1)}KB`;
  return `${n.toLocaleString('ko-KR')}B`;
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString('ko-KR');
}

function formatDate(value) {
  if (!value) return '-';
  try {
    return new Date(value).toLocaleString('ko-KR');
  } catch (_e) {
    return value;
  }
}

export default function DatasetPanel({ refreshSignal }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function loadStats() {
    setLoading(true);
    setError('');
    try {
      const data = await getDatasetStats();
      setStats(data);
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadStats();
  }, [refreshSignal]);

  const accessoryMatching = stats?.accessoryMatching || {};
  const recent = stats?.recentSnapshots || [];

  return (
    <section className="card input-card dataset-panel">
      <div className="price-panel">
        <div>
          <h2>데이터셋 상태</h2>
          <p className="hint">리포트 생성 시 로컬 Parquet/DuckDB 데이터셋에 누적 저장됩니다.</p>
        </div>
        <div className="price-actions">
          <span className="auto-loaded-badge">{loading ? '갱신 중' : formatBytes(stats?.totalSizeBytes)}</span>
          <button className="ghost" type="button" onClick={loadStats} disabled={loading}>{loading ? '확인 중...' : '상태 새로고침'}</button>
        </div>
      </div>

      {error && <p className="hint auto-price-status">데이터셋 상태 확인 실패: {error}</p>}

      <div className="module-toggle-grid">
        <div className="module-toggle checked"><span className="module-toggle-icon">◆</span><span><strong>{formatNumber(stats?.characterSnapshotCount)}</strong><small>캐릭터 스냅샷</small></span></div>
        <div className="module-toggle checked"><span className="module-toggle-icon">⚔</span><span><strong>{formatNumber(stats?.equipmentItemCount)}</strong><small>장비 레코드</small></span></div>
        <div className="module-toggle checked"><span className="module-toggle-icon">✦</span><span><strong>{formatNumber(stats?.accessoryEffectCount)}</strong><small>장신구 효과</small></span></div>
        <div className="module-toggle checked"><span className="module-toggle-icon">◇</span><span><strong>{formatNumber(stats?.braceletEffectCount)}</strong><small>팔찌 효과</small></span></div>
        <div className="module-toggle checked"><span className="module-toggle-icon">●</span><span><strong>{formatNumber(stats?.abilityStoneCount)}</strong><small>스톤 레코드</small></span></div>
        <div className="module-toggle checked"><span className="module-toggle-icon">☰</span><span><strong>{formatNumber(stats?.memoryInputCount)}</strong><small>기억 입력</small></span></div>
      </div>

      <details className="notice-panel" open={recent.length > 0}>
        <summary>최근 저장된 캐릭터</summary>
        {recent.length ? (
          <div className="notice-list">
            {recent.map((row) => (
              <p key={row.snapshot_id}>
                <strong>{row.character_name}</strong> · {row.server_name || '-'} · {row.class_name || '-'} · Lv.{row.item_avg_level || '-'} · {formatDate(row.captured_at)}
              </p>
            ))}
          </div>
        ) : (
          <p className="hint">아직 저장된 스냅샷이 없습니다. 리포트를 한 번 생성하면 이곳에 표시됩니다.</p>
        )}
      </details>

      <p className="hint">
        장신구 공식 매칭: {formatNumber(accessoryMatching.matched_effects)}개 성공 / {formatNumber(accessoryMatching.unmatched_effects)}개 실패
      </p>
    </section>
  );
}
