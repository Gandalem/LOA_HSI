import React from 'react';

function gold(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return `${Math.round(Number(value)).toLocaleString('ko-KR')}G`;
}

function number(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Number(value).toLocaleString('ko-KR', { maximumFractionDigits: digits });
}

function percent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return `${Number(value).toFixed(1)}%`;
}

function verdictTone(avgGold) {
  const value = Number(avgGold || 0);
  if (value >= 8_000_000) return 'high';
  if (value >= 3_000_000) return 'mid';
  return 'low';
}

function verdictLabel(avgGold) {
  const tone = verdictTone(avgGold);
  if (tone === 'high') return '복구 부담 큼';
  if (tone === 'mid') return '복구 부담 보통';
  return '복구 부담 안정';
}

function cohortVerdictLabel(verdict) {
  const labels = {
    much_harder_than_peers: '같은 스펙대보다 확실히 비싼 편',
    harder_than_peers: '같은 스펙대보다 다소 비싼 편',
    similar_to_peers: '같은 스펙대와 비슷한 편',
    easier_than_peers: '같은 스펙대보다 다소 수월한 편',
    much_easier_than_peers: '같은 스펙대보다 확실히 수월한 편',
    unavailable: '같은 스펙대 비교 보류',
  };
  return labels[verdict] || '같은 스펙대 비교 보류';
}

function cohortBasisLabel(value) {
  const labels = {
    strict: '같은 직업 · 같은 역할 · 좁은 레벨대',
    balanced: '같은 직업 · 같은 역할 · 넓은 레벨대',
    relaxed: '같은 직업 · 비슷한 레벨대',
    broad: '같은 직업 전체 표본',
  };
  return labels[value] || '같은 직업 기준 표본';
}

function dominantCostModule(equipmentSummary, stoneSummary, accessorySummary) {
  const candidates = [
    { label: '재련', value: Number(equipmentSummary?.avgGold || 0) },
    { label: '스톤', value: Number(stoneSummary?.avgGold || 0) },
    { label: '장신구/팔찌', value: Number(accessorySummary?.avgGold || 0) },
  ].filter((item) => item.value > 0);

  if (!candidates.length) return null;
  return candidates.sort((a, b) => b.value - a.value)[0];
}

function accessoryVerdictText(accessorySummary, marketSummary, accessoryTarget, accessoryMarketTotal) {
  const connected = Number(accessoryMarketTotal?.auctionConnectedItemCount || 0);
  const total = Number(accessoryMarketTotal?.itemCount || 0);
  const ratio = total > 0 ? connected / total : null;
  const expectedAttempts = Number(accessoryTarget?.expectedAttempts || 0);
  const marketGold = Number(marketSummary?.accessoryMedianGold || 0);
  const simulationGold = Number(accessorySummary?.avgGold || 0);

  if (!total || !connected) {
    return '조건을 끝까지 만족한 실매물이 부족해, 이 구간은 시세보다 희소성 자체를 먼저 봐야 합니다.';
  }

  const clauses = [];
  if (ratio < 0.5) clauses.push('조건을 끝까지 만족한 매물이 적어 희소성이 강합니다');
  else clauses.push('조건을 만족한 매물이 꾸준히 잡혀 시장 기준은 비교적 선명합니다');

  if (expectedAttempts >= 15) clauses.push('핵심 병목은 시세보다 연마 난도입니다');
  else clauses.push('핵심 연마 난도는 과도하게 높지 않습니다');

  if (marketGold > 0 && simulationGold > 0) {
    if (marketGold <= simulationGold * 0.8) clauses.push('직접 재현보다 매수 쪽이 더 합리적입니다');
    else if (marketGold >= simulationGold * 1.2) clauses.push('매수보다 직접 재현이 더 나을 수 있습니다');
  }

  return `${clauses.join('. ')}.`;
}

function braceletVerdictText(officialBracelet, braceletRandom, braceletMarket) {
  const attempts = Number(braceletRandom?.expectedAttempts || 0);
  const base = Number(braceletMarket?.baseBraceletPriceGold || 0);
  const reroll = Number(braceletMarket?.expectedRerollCostGold || 0);
  const total = Number(braceletMarket?.expectedReproductionCostGold || 0);
  const leapPoints = Number(officialBracelet?.leapPoints || 0);

  if (!base && !total && !attempts) {
    return '팔찌 시세 또는 공식 확률 데이터가 충분하지 않아 판정을 보류합니다.';
  }

  const clauses = [];
  if (reroll > base) clauses.push('이 팔찌는 베이스 가격보다 랜덤 옵션 복구 비용이 더 큽니다');
  else if (base > 0) clauses.push('이 팔찌는 랜덤 옵션보다 베이스 매물 확보가 먼저입니다');

  if (attempts >= 80) clauses.push('한 번에 끝날 기대를 두기 어려운 편입니다');
  else if (attempts >= 25) clauses.push('재시도 부담이 분명하게 남는 편입니다');
  else clauses.push('재시도 부담은 비교적 완만한 편입니다');

  if (leapPoints > 0) clauses.push(`현재 판정은 도약 ${number(leapPoints, 0)}P 공식 확률표를 기준으로 계산했습니다`);

  return `${clauses.join('. ')}.`;
}

function overallVerdictText(totalSummary, equipmentSummary, stoneSummary, accessorySummary, cohortComparison) {
  const tone = verdictTone(totalSummary?.avgGold);
  const dominant = dominantCostModule(equipmentSummary, stoneSummary, accessorySummary);
  const cohortMetric = cohortPrimaryMetric(cohortComparison);

  const clauses = [];
  if (tone === 'high') clauses.push('지금 세팅은 다시 맞추는 순간 골드가 크게 새는 고난도 구간입니다');
  else if (tone === 'mid') clauses.push('지금 세팅은 복구 비용이 분명히 들지만 과열 구간까지는 아닌 편입니다');
  else clauses.push('지금 세팅은 다시 맞춰도 비용 폭이 비교적 안정적인 편입니다');

  if (dominant?.label) clauses.push(`특히 ${dominant.label}이 전체 예산을 가장 많이 끌어올립니다`);
  if (cohortComparison?.available && cohortMetric?.verdict) clauses.push(`같은 스펙대 기준으로는 ${cohortVerdictLabel(cohortMetric.verdict)}`);

  return `${clauses.join('. ')}.`;
}

function cohortMetricByName(cohortComparison, metricName) {
  return cohortComparison?.metrics?.[metricName] || null;
}

function peerLineText({ label, metric, loading, cohortAvailable, noun = '비용' }) {
  if (loading) {
    return `같은 스펙대 ${label} ${noun} 표본과 대조 중입니다.`;
  }
  if (!cohortAvailable) {
    return `같은 스펙대 표본이 부족해 ${label} ${noun} 비교는 잠시 보류합니다.`;
  }
  if (!metric?.available || metric?.percentile == null) {
    return `같은 스펙대 ${label} ${noun} 비교 데이터가 아직 충분하지 않습니다.`;
  }

  const percentileText = `${percent(metric.percentile)} 구간`;
  if (metric.verdict === 'much_harder_than_peers') {
    return `같은 스펙대 ${label} ${noun} 기준 ${percentileText}으로, 평균보다 확실히 무거운 편입니다.`;
  }
  if (metric.verdict === 'harder_than_peers') {
    return `같은 스펙대 ${label} ${noun} 기준 ${percentileText}으로, 평균보다 다소 무거운 편입니다.`;
  }
  if (metric.verdict === 'much_easier_than_peers') {
    return `같은 스펙대 ${label} ${noun} 기준 ${percentileText}으로, 평균보다 확실히 수월한 편입니다.`;
  }
  if (metric.verdict === 'easier_than_peers') {
    return `같은 스펙대 ${label} ${noun} 기준 ${percentileText}으로, 평균보다 다소 수월한 편입니다.`;
  }
  return `같은 스펙대 ${label} ${noun} 기준 ${percentileText}으로, 평균권에 가까운 편입니다.`;
}

function nonEmptyMemoryCount(memoryHints = {}) {
  let count = 0;
  if (memoryHints.stoneAttempts !== '' && memoryHints.stoneAttempts !== undefined) count += 1;
  if (Array.isArray(memoryHints.pityRecords)) {
    count += memoryHints.pityRecords.filter((row) => row?.part !== 'unknown' || row?.target !== 'unknown').length;
  }
  const accessory = memoryHints.accessoryAcquisitions || {};
  count += Object.values(accessory).filter((row) => row?.mode && row.mode !== 'unknown').length;
  if (memoryHints.braceletAcquisition?.mode && memoryHints.braceletAcquisition.mode !== 'unknown') count += 1;
  return count;
}

function SectionMetric({ label, value, note, accent = '' }) {
  return (
    <article className={`result-metric-card ${accent}`.trim()}>
      <span className="result-metric-label">{label}</span>
      <strong className="result-metric-value">{value}</strong>
      {note ? <p className="result-metric-note">{note}</p> : null}
    </article>
  );
}

function SummaryLine({ label, value, accent = false }) {
  return (
    <div className={`result-summary-line ${accent ? 'accent' : ''}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function VerdictCard({ text }) {
  if (!text) return null;

  return (
    <div className="result-summary-card total-review-card">
      <div className="total-review-badge-row">
        <span className="subtle-badge">판정</span>
      </div>
      <p className="section-copy">{text}</p>
    </div>
  );
}

function PeerComparisonLine({ text }) {
  if (!text) return null;
  return <p className="result-metric-note">{text}</p>;
}

function ResultSection({ eyebrow, title, description, children, tone = '' }) {
  return (
    <section className={`card result-section-card ${tone}`.trim()}>
      <div className="section-heading">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
          {description ? <p className="section-copy">{description}</p> : null}
        </div>
      </div>
      {children}
    </section>
  );
}

function cohortPrimaryMetric(cohortComparison) {
  const metrics = cohortComparison?.metrics || {};
  return (
    metrics.totalSimulationAvgGold
    || metrics.equipmentAvgGold
    || metrics.marketReproductionGold
    || metrics.stoneExpectedGold
    || null
  );
}

function CohortSummaryCard({ cohortComparison, loading }) {
  if (loading) {
    return (
      <div className="result-summary-card total-review-card">
        <div className="total-review-badge-row">
          <span className="subtle-badge">같은 스펙대 비교 중</span>
        </div>
        <p className="result-metric-note">같은 직업과 비슷한 아이템 레벨 구간 표본을 찾고 있습니다.</p>
      </div>
    );
  }

  if (!cohortComparison?.available) {
    const reason = cohortComparison?.reason || '';
    const detail = reason === 'request_failed'
      ? `비교군 계산 요청이 실패했습니다${cohortComparison?.errorMessage ? `: ${cohortComparison.errorMessage}` : '.'}`
      : '현재 수집 데이터에서 같은 직업과 비슷한 레벨대 표본이 충분하지 않아 비교를 생략했습니다.';
    return (
      <div className="result-summary-card total-review-card">
        <div className="total-review-badge-row">
          <span className="subtle-badge">같은 스펙대 비교 보류</span>
        </div>
        <p className="result-metric-note">
          {detail}
        </p>
      </div>
    );
  }

  const cohort = cohortComparison.cohort || {};
  const metric = cohortPrimaryMetric(cohortComparison);
  const distribution = metric?.distribution || {};
  const dataset = cohortComparison.dataset || {};

  return (
    <div className="result-summary-card total-review-card">
      <div className="total-review-badge-row">
        <span className="subtle-badge">{cohortVerdictLabel(metric?.verdict)}</span>
        <span className="subtle-badge">{number(cohort.sampleCount, 0)}명 표본</span>
      </div>
      <SummaryLine label="비교 기준" value={cohortBasisLabel(cohort.comparisonBasis)} />
      <SummaryLine label="표본 구간" value={cohort.strategyLabel || cohort.itemLevelBand || '-'} />
      <SummaryLine label="비교군 풀" value={dataset.comparisonDistinctCharacters ? `${number(dataset.comparisonDistinctCharacters, 0)}명` : '-'} />
      <SummaryLine label="현재 위치" value={percent(metric?.percentile)} accent />
      <SummaryLine label="같은 스펙 평균" value={gold(distribution.avg)} />
      <SummaryLine label="같은 스펙 중앙값" value={gold(distribution.p50)} />
    </div>
  );
}

export default function ResultPanel({
  result,
  memoryHints,
  cohortComparison,
  cohortLoading,
}) {
  if (!result) return null;

  const modules = result.modules || {};
  const equipmentSummary = modules.equipment?.summary || {};
  const stoneSummary = modules.abilityStone?.summary || {};
  const accessorySummary = modules.accessory?.summary || {};
  const totalSummary = result.total?.summary || {};

  const expectedValues = result.expectedValues || {};
  const stoneExpected = expectedValues.abilityStone || {};
  const officialAccessory = expectedValues.officialAccessoryEffects || {};
  const officialBracelet = expectedValues.officialBraceletT4 || {};
  const marketCost = expectedValues.marketCost || {};
  const marketSummary = marketCost.summary || {};
  const accessoryMarket = marketCost.accessoryMarket || {};
  const accessoryMarketTotal = accessoryMarket.total || {};
  const braceletMarket = marketCost.braceletMarket || {};
  const braceletRandom = officialBracelet.randomOptionBasis || {};
  const accessoryTarget = officialAccessory.mostDifficultItem || {};

  const memoryCount = nonEmptyMemoryCount(memoryHints);
  const totalTone = verdictTone(totalSummary.avgGold);
  const cohortAvailable = Boolean(cohortComparison?.available);
  const accessoryVerdict = accessoryVerdictText(accessorySummary, marketSummary, accessoryTarget, accessoryMarketTotal);
  const braceletVerdict = braceletVerdictText(officialBracelet, braceletRandom, braceletMarket);
  const overallVerdict = overallVerdictText(totalSummary, equipmentSummary, stoneSummary, accessorySummary, cohortComparison);
  const equipmentPeerLine = peerLineText({
    label: '재련',
    metric: cohortMetricByName(cohortComparison, 'equipmentAvgGold'),
    loading: cohortLoading,
    cohortAvailable,
    noun: '비용',
  });
  const stonePeerLine = peerLineText({
    label: '스톤',
    metric: cohortMetricByName(cohortComparison, 'stoneExpectedGold'),
    loading: cohortLoading,
    cohortAvailable,
    noun: '비용',
  });
  const accessoryPeerLine = peerLineText({
    label: '장신구',
    metric: cohortMetricByName(cohortComparison, 'accessoryExpectedAttempts'),
    loading: cohortLoading,
    cohortAvailable,
    noun: '난도',
  });
  const braceletPeerLine = peerLineText({
    label: '팔찌',
    metric: cohortMetricByName(cohortComparison, 'braceletExpectedAttempts'),
    loading: cohortLoading,
    cohortAvailable,
    noun: '난도',
  });

  return (
    <div className="result-shell result-journey-shell">
      <ResultSection
        eyebrow="01. Honing"
        title="재련"
        description="현재 장비 단계까지 다시 올린다고 가정했을 때의 기대 비용 분포입니다."
      >
        <div className="result-metric-grid">
          <SectionMetric label="평균 재련 비용" value={gold(equipmentSummary.avgGold)} note="같은 장비 단계를 반복 재현한 평균값" accent="primary" />
          <SectionMetric label="중앙값" value={gold(equipmentSummary.p50Gold)} note="절반은 이보다 적게, 절반은 더 많이 듭니다" />
          <SectionMetric label="상위 10%" value={gold(equipmentSummary.p90Gold)} note="운이 나쁜 편으로 밀릴 때의 비용선" accent="warning" />
          <SectionMetric label="상위 1%" value={gold(equipmentSummary.p99Gold)} note="극단적으로 비용이 많이 드는 구간" accent="danger" />
        </div>
        <PeerComparisonLine text={equipmentPeerLine} />
      </ResultSection>

      <ResultSection
        eyebrow="02. Stone"
        title="스톤"
        description="현재 각인 결과를 만들기 위한 기대 비용과 시도량 기준입니다."
      >
        <div className="result-split-grid">
          <div className="result-summary-card">
            <SummaryLine label="평균 재현 비용" value={gold(stoneSummary.avgGold)} accent />
            <SummaryLine label="중앙값" value={gold(stoneSummary.p50Gold)} />
            <SummaryLine label="상위 10%" value={gold(stoneSummary.p90Gold)} />
            <SummaryLine label="상위 1%" value={gold(stoneSummary.p99Gold)} />
          </div>
          <div className="result-summary-card">
            <SummaryLine label="기대 골드" value={gold(stoneExpected.expectedGold)} accent />
            <SummaryLine label="기대 스톤 수" value={`${number(stoneExpected.expectedStones)}개`} />
            <SummaryLine label="기억 입력 시도 수" value={memoryHints?.stoneAttempts ? `${number(memoryHints.stoneAttempts, 0)}회` : '-'} />
            <SummaryLine label="목표 조합" value={stoneExpected.targetLabel || '-'} />
          </div>
        </div>
        <PeerComparisonLine text={stonePeerLine} />
      </ResultSection>

      <ResultSection
        eyebrow="03. Accessory"
        title="장신구"
        description="핵심 연마 옵션 난도와 경매장 유사 매물 기준 시장 재현 비용입니다."
      >
        <div className="result-metric-grid">
          <SectionMetric label="평균 재현 비용" value={gold(accessorySummary.avgGold)} note="장신구와 팔찌를 포함한 액세서리 모듈 평균값" accent="primary" />
          <SectionMetric label="시장 재현 비용" value={gold(marketSummary.accessoryMedianGold)} note="유사 매물 중앙값 합계 기준" />
          <SectionMetric label="가장 어려운 연마" value={number(accessoryTarget.expectedAttempts)} note={accessoryTarget.name || accessoryTarget.slot || '핵심 옵션 기준 기대 시도 수'} />
          <SectionMetric
            label="경매장 연결 매물"
            value={`${number(accessoryMarketTotal.auctionConnectedItemCount, 0)} / ${number(accessoryMarketTotal.itemCount, 0)}건`}
            note="Options 직접 검증으로 연결된 매물 수"
          />
        </div>
        <VerdictCard text={accessoryVerdict} />
        <PeerComparisonLine text={accessoryPeerLine} />
      </ResultSection>

      <ResultSection
        eyebrow="04. Bracelet"
        title="팔찌"
        description="고정 효과 베이스 가격과 랜덤 옵션 기대 난도를 분리해서 계산한 결과입니다."
      >
        <div className="result-metric-grid">
          <SectionMetric
            label="랜덤 옵션 기대 시도"
            value={number(braceletRandom.expectedAttempts)}
            note={(braceletRandom.targetCategories || []).join(', ') || '필요 카테고리 기준'}
            accent="primary"
          />
          <SectionMetric label="베이스 팔찌 가격" value={gold(braceletMarket.baseBraceletPriceGold)} note={braceletMarket.gradeLabel || '고정 효과 기준 경매장 가격'} />
          <SectionMetric label="기대 재현 비용" value={gold(braceletMarket.expectedReproductionCostGold)} note="베이스 가격 + 랜덤 옵션 기대 비용" />
          <SectionMetric label="도약 포인트" value={officialBracelet.leapPoints == null ? '-' : `${number(officialBracelet.leapPoints, 0)}P`} note="T4 공식 확률표 기준" />
        </div>
        <VerdictCard text={braceletVerdict} />
        <PeerComparisonLine text={braceletPeerLine} />
      </ResultSection>

      <ResultSection
        eyebrow="05. Overall"
        title="총평"
        description="전체 기대 비용과 같은 스펙대 비교를 함께 보여주는 최종 판정입니다."
        tone={`tone-${totalTone}`}
      >
        <div className="result-metric-grid">
          <SectionMetric label="평균 총비용" value={gold(totalSummary.avgGold)} note="전체 모듈 재현 평균값" accent="primary" />
          <SectionMetric label="중앙값" value={gold(totalSummary.p50Gold)} note="가장 대표적인 전체 비용 구간" />
          <SectionMetric label="상위 10%" value={gold(totalSummary.p90Gold)} note="운이 나쁘게 몰릴 때의 총비용" accent="warning" />
          <SectionMetric label="상위 1%" value={gold(totalSummary.p99Gold)} note="극단 구간 기준 총비용" accent="danger" />
        </div>
        <div className="result-split-grid">
          <div className="result-summary-card total-review-card">
            <div className="total-review-badge-row">
              <span className={`verdict-badge ${totalTone}`}>{verdictLabel(totalSummary.avgGold)}</span>
              <span className="subtle-badge">기억 입력 {memoryCount}건</span>
            </div>
            <p className="section-copy">{overallVerdict}</p>
            <SummaryLine label="시장 재현 총액" value={gold(marketSummary.marketReproductionGold)} accent />
            <SummaryLine label="재련 평균" value={gold(equipmentSummary.avgGold)} />
            <SummaryLine label="스톤 평균" value={gold(stoneSummary.avgGold)} />
            <SummaryLine label="장신구/팔찌 평균" value={gold(accessorySummary.avgGold)} />
          </div>
          <CohortSummaryCard cohortComparison={cohortComparison} loading={cohortLoading} />
        </div>
      </ResultSection>
    </div>
  );
}
