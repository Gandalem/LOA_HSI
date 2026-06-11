import React from 'react';

function gold(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return `${Math.round(Number(value)).toLocaleString('ko-KR')}G`;
}

function number(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Number(value).toLocaleString('ko-KR', { maximumFractionDigits: digits });
}

function MarketStatLine({ label, value, highlight = false }) {
  return (
    <div className={highlight ? 'evidence-line highlight' : 'evidence-line'}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AccessoryMarketChip({ item }) {
  const estimate = item?.similarListingEstimate || {};
  return (
    <div className="combo-chip">
      <span>{item?.partLabel || item?.slot || '장신구'} · 품질 {item?.quality ?? '-'}</span>
      <strong>{gold(estimate.medianGold)}</strong>
      <small>{gold(estimate.minGold)} ~ {gold(estimate.q75Gold)} · {item?.qualityBand || '-'}</small>
    </div>
  );
}

export default function MarketCostPanel({ marketCost }) {
  if (!marketCost) return null;

  const summary = marketCost.summary || {};
  const accessory = marketCost.accessoryMarket || {};
  const total = accessory.total || {};
  const bracelet = marketCost.braceletMarket || {};
  const items = accessory.items || [];
  const limits = marketCost.limits || [];

  return (
    <div className="expected-panel evidence-panel loa-hsi-market-v601-react" data-loa-hsi-market-v601-react="true">
      <h3>v60.1 시장 재현 비용</h3>
      <p className="hint evidence-intro">
        장신구/팔찌 구매 비용은 운 판정과 분리해 표시합니다. 현재 값은 실제 거래소 조회 전 단계의 임시 시장가 추정입니다.
      </p>

      <div className="evidence-card-grid">
        <section className="evidence-card">
          <div className="evidence-card-head">
            <strong>시장 재현 합계</strong>
            <span>{marketCost.tradeApiConnected ? '실매물 연동' : '임시 추정'}</span>
          </div>
          <MarketStatLine label="합계" value={gold(summary.marketReproductionGold)} highlight />
          <MarketStatLine label="장신구 중앙값" value={gold(summary.accessoryMedianGold)} />
          <MarketStatLine label="팔찌 기억 기반" value={gold(summary.braceletActualGold)} />
        </section>

        <section className="evidence-card">
          <div className="evidence-card-head">
            <strong>장신구 시장가</strong>
            <span>{number(total.itemCount, 0)}개</span>
          </div>
          <MarketStatLine label="중앙값 합계" value={gold(total.medianGold)} highlight />
          <MarketStatLine label="하위 25%" value={gold(total.q25Gold)} />
          <MarketStatLine label="상위 25%" value={gold(total.q75Gold)} />
        </section>

        <section className="evidence-card">
          <div className="evidence-card-head">
            <strong>팔찌 비용</strong>
            <span>{bracelet.gradeLabel || '-'}</span>
          </div>
          <MarketStatLine label="입력 시도 수" value={`${number(bracelet.userAttempts, 0)}회`} highlight />
          <MarketStatLine label="팔찌 돌 1회" value={gold(bracelet.rerollStonePriceGold)} />
          <MarketStatLine label="기대 기준 비용" value={gold(bracelet.expectedReproductionCostGold)} />
        </section>
      </div>

      <div className="combo-chip-grid">
        {items.length ? items.map((item, index) => (
          <AccessoryMarketChip item={item} key={`${item.slot || 'accessory'}-${index}`} />
        )) : <p className="hint">장신구 시장가 추정 항목이 없습니다.</p>}
      </div>

      <div className="notice-panel">
        <strong>비용/운 분리</strong>
        <p className="hint">구형 장신구 시뮬레이션 비용은 연마 확률 기반 참고값이고, 실제 구매 재현 비용은 이 시장가 카드의 값을 우선합니다.</p>
      </div>

      {limits.length > 0 && (
        <div className="notice-panel">
          <strong>계산 제한</strong>
          <ul>{limits.map((line, index) => <li key={index}>{line}</li>)}</ul>
        </div>
      )}
    </div>
  );
}
