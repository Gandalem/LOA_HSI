import React from 'react';

function number(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Number(value).toLocaleString('ko-KR', { maximumFractionDigits: digits });
}

function percent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return `${Number(value).toFixed(1)}%`;
}

function gold(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return `${Math.round(Number(value)).toLocaleString('ko-KR')}G`;
}

function valueText(metricName, value) {
  if (metricName.toLowerCase().includes('gold')) return gold(value);
  return number(value);
}

function metricLabel(metricName) {
  const labels = {
    equipmentAvgGold: '재련 기대 비용',
    totalSimulationAvgGold: '총 기대 비용',
    marketReproductionGold: '시장 재현 비용',
    stoneExpectedGold: '스톤 기대 비용',
    accessoryExpectedAttempts: '장신구 난도',
    braceletExpectedAttempts: '팔찌 난도',
  };
  return labels[metricName] || metricName;
}

function verdictLabel(verdict) {
  const labels = {
    much_harder_than_peers: '비슷한 유저보다 많이 든 편',
    harder_than_peers: '비슷한 유저보다 다소 비싼 편',
    similar_to_peers: '비슷한 유저와 유사한 편',
    easier_than_peers: '비슷한 유저보다 다소 수월한 편',
    much_easier_than_peers: '비슷한 유저보다 확실히 수월한 편',
    unavailable: '비교 불가',
  };
  return labels[verdict] || verdict || '-';
}

function verdictTone(verdict) {
  if (verdict === 'much_harder_than_peers' || verdict === 'harder_than_peers') return 'warning';
  if (verdict === 'much_easier_than_peers' || verdict === 'easier_than_peers') return 'positive';
  return 'neutral';
}

export default function CohortComparisonPanel({ cohortComparison, loading }) {
  if (loading) {
    return (
      <section className="card cohort-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Peer Cohort</p>
            <h2>유사 유저 비교</h2>
          </div>
        </div>
        <p className="section-copy">수집된 실측 데이터에서 비슷한 표본을 찾는 중입니다.</p>
      </section>
    );
  }

  if (!cohortComparison) return null;

  if (!cohortComparison.available) {
    return (
      <section className="card cohort-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Peer Cohort</p>
            <h2>유사 유저 비교</h2>
          </div>
          <span className="subtle-badge">표본 부족</span>
        </div>
        <p className="section-copy">
          현재 수집된 데이터에서는 같은 직업·비슷한 구간의 표본이 충분하지 않아 코호트 비교를 생략합니다.
        </p>
      </section>
    );
  }

  const cohort = cohortComparison.cohort || {};
  const metrics = Object.entries(cohortComparison.metrics || {}).filter(([, value]) => value?.available);

  return (
    <section className="card cohort-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Peer Cohort</p>
          <h2>유사 유저 비교</h2>
          <p className="section-copy">
            실측 데이터에서 같은 직업{cohort.classPresetRole ? ', 같은 역할' : ''}{cohort.itemLevelBand ? `, ${cohort.itemLevelBand}` : ''} 조건으로 표본을 구성했습니다.
          </p>
        </div>
        <div className="overview-badge-stack">
          <span className="subtle-badge">{number(cohort.sampleCount, 0)}명 표본</span>
          <span className="subtle-badge">전략 {cohort.strategy || '-'}</span>
        </div>
      </div>

      {metrics.length ? (
        <div className="cohort-metric-grid">
          {metrics.map(([metricName, metric]) => {
            const distribution = metric.distribution || {};
            return (
              <article className={`cohort-metric-card ${verdictTone(metric.verdict)}`} key={metricName}>
                <div className="cohort-metric-head">
                  <strong>{metricLabel(metricName)}</strong>
                  <span>{verdictLabel(metric.verdict)}</span>
                </div>
                <div className="cohort-metric-body">
                  <div className="cohort-rank-block">
                    <small>표본 내 위치</small>
                    <b>{percent(metric.percentile)}</b>
                  </div>
                  <div className="cohort-distribution-block">
                    <div><span>현재</span><strong>{valueText(metricName, metric.currentValue)}</strong></div>
                    <div><span>평균</span><strong>{valueText(metricName, distribution.avg)}</strong></div>
                    <div><span>중앙값</span><strong>{valueText(metricName, distribution.p50)}</strong></div>
                    <div><span>상위 10%</span><strong>{valueText(metricName, distribution.p90)}</strong></div>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <p className="section-copy">비교 가능한 지표가 아직 없습니다.</p>
      )}
    </section>
  );
}
