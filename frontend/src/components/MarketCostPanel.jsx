import React from 'react';

function gold(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return `${Math.round(Number(value)).toLocaleString('ko-KR')}G`;
}

function number(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Number(value).toLocaleString('ko-KR', { maximumFractionDigits: digits });
}

function priceText(value, failed = false) {
  return failed ? '조회 실패' : gold(value);
}

function StatLine({ label, value, accent = false }) {
  return (
    <div className={`detail-stat-line ${accent ? 'accent' : ''}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AccessoryRow({ item }) {
  const estimate = item?.similarListingEstimate || {};
  const failed = estimate.status === 'failed';
  return (
    <article className={`market-listing-card ${failed ? 'failed' : ''}`}>
      <div className="market-listing-head">
        <strong>{item?.partLabel || item?.slot || '장신구'}</strong>
        <span>품질 {item?.quality ?? '-'}</span>
      </div>
      <div className="market-listing-price">{priceText(estimate.medianGold, failed)}</div>
      <p>
        {failed
          ? (estimate.failureReason || '조건에 맞는 매물을 찾지 못했습니다.')
          : `${gold(estimate.minGold)} ~ ${gold(estimate.q75Gold)} / 품질 ${item?.qualityBand || '-'}`}
      </p>
    </article>
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
  const accessoryFailed = total.status === 'failed';

  return (
    <section className="card detail-card market-cost-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Market Replay</p>
          <h2>시장 재현 비용</h2>
          <p className="section-copy">
            장신구는 실제 경매장 검색 결과를, 팔찌는 고정 효과 기준 베이스 가격과 랜덤 옵션 기대값을 분리해 계산합니다.
          </p>
        </div>
        <span className="subtle-badge">
          {marketCost.tradeApiConnected ? '경매장 연동' : '일부 조회 실패'}
        </span>
      </div>

      <div className="detail-stat-grid">
        <div className="detail-stat-card">
          <h3>전체 요약</h3>
          <StatLine label="시장 재현 비용" value={priceText(summary.marketReproductionGold, accessoryFailed)} accent />
          <StatLine label="장신구 중앙값 합계" value={priceText(summary.accessoryMedianGold, accessoryFailed)} />
          <StatLine label="팔찌 반영값" value={gold(summary.braceletActualGold)} />
        </div>

        <div className="detail-stat-card">
          <h3>장신구 시세 분포</h3>
          <StatLine label="연결 매물 수" value={`${number(total.auctionConnectedItemCount, 0)} / ${number(total.itemCount, 0)}건`} />
          <StatLine label="중앙값 합계" value={priceText(total.medianGold, accessoryFailed)} accent />
          <StatLine label="하위 25%" value={priceText(total.q25Gold, accessoryFailed)} />
          <StatLine label="상위 25%" value={priceText(total.q75Gold, accessoryFailed)} />
        </div>

        <div className="detail-stat-card">
          <h3>팔찌 재현 비용</h3>
          <StatLine label="입력 시도 수" value={`${number(bracelet.userAttempts, 0)}회`} />
          <StatLine label="팔찌 1회 비용" value={gold(bracelet.rerollStonePriceGold)} />
          <StatLine label="기대 재현 비용" value={gold(bracelet.expectedReproductionCostGold)} accent />
        </div>
      </div>

      <div className="listing-grid">
        {items.length
          ? items.map((item, index) => <AccessoryRow item={item} key={`${item.slot || 'accessory'}-${index}`} />)
          : <p className="section-copy">장신구 시세 조회 결과가 없습니다.</p>}
      </div>

      {limits.length > 0 ? (
        <div className="notice-panel">
          <strong>계산 제한</strong>
          <ul>
            {limits.map((line, index) => <li key={index}>{line}</li>)}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
