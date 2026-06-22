import React from 'react';

function number(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Number(value).toLocaleString('ko-KR', { maximumFractionDigits: digits });
}

function percent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return `${(Number(value) * 100).toFixed(4)}%`;
}

function roleLabel(value) {
  const map = { core: '핵심', secondary: '보조', conditional: '조건부', unmatched: '미분류' };
  return map[value] || value || '-';
}

function basisLabel(value) {
  const map = {
    user_input: '사용자 직접 입력',
    auto_special_count: '특수 옵션 수 기반 자동 추정',
    auto_special_count_requires_all_random_special: '랜덤 특수 옵션 3개 기준 추정',
    auto_estimate: '자동 추정',
    auto_fallback: '자동 보정',
    partial_user_input_auto_completed: '일부 입력 + 자동 보정',
    official_distribution: '공식 분포표 기준',
  };
  return map[value] || value || '-';
}

function requiredCategoryLabel(required) {
  const entries = Object.entries(required || {});
  if (!entries.length) return '-';
  return entries.map(([key, value]) => `${key} ${value}개`).join(', ');
}

function StatLine({ label, value, accent = false }) {
  return (
    <div className={`detail-stat-line ${accent ? 'accent' : ''}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function EffectChip({ effect }) {
  const category = effect?.categoryLabel || effect?.category || '-';
  return (
    <article className="effect-chip-card">
      <span>{effect?.rawEffect || '-'}</span>
      <strong>{category}</strong>
      <small>{roleLabel(effect?.matchRole)} · 표시 확률 {percent(effect?.categoryDisplayProbability)}</small>
    </article>
  );
}

export default function BraceletOfficialPanel({ officialBracelet }) {
  if (!officialBracelet) return null;

  const data = officialBracelet || {};
  const random = data.randomOptionBasis || {};
  const purchase = data.purchaseStructure || {};
  const userInput = purchase.userInput || {};
  const inference = userInput.inference || {};
  const fixedBasis = purchase.fixedEffectBasis || {};
  const randomBasis = purchase.randomEffectBasis || {};
  const effects = (data.matchedEffects || []).slice(0, 8);
  const limits = data.limits || [];
  const fixedCount = fixedBasis.effectiveFixedOptionCount ?? userInput.fixedOptionCount;
  const randomCount = randomBasis.effectiveRandomOptionSlotCount ?? userInput.randomOptionSlotCount;
  const calcBasis = inference.basis || random.requirementBasis || randomBasis.basis || '-';
  const targetCategories = (random.targetCategories || []).join(', ') || '-';

  return (
    <section className="card detail-card bracelet-detail-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Bracelet Logic</p>
          <h2>팔찌 공식 분포 기준</h2>
          <p className="section-copy">
            팔찌는 전체 옵션을 한 번에 목표값으로 두지 않고, 고정 효과 베이스와 랜덤 옵션 슬롯 확률을 분리해서 해석합니다.
          </p>
        </div>
        <span className="subtle-badge">{data.gradeLabel || 'T4 기준'}</span>
      </div>

      <div className="detail-stat-grid">
        <div className="detail-stat-card">
          <h3>구매 구조</h3>
          <StatLine label="고정 옵션 기준" value={fixedCount == null ? '자동 추정 불가' : `고정 ${fixedCount}개`} accent />
          <StatLine label="랜덤 슬롯 기준" value={randomCount == null ? '자동 추정 불가' : `랜덤 ${randomCount}개`} />
          <StatLine label="계산 기준" value={basisLabel(calcBasis)} />
          <StatLine label="추정 사유" value={inference.reason || '-'} />
        </div>

        <div className="detail-stat-card">
          <h3>현재 팔찌 매칭</h3>
          <StatLine label="매칭 성공 효과" value={`${number(data.matchedEffectCount, 0)}개`} accent />
          <StatLine label="특수 옵션 수" value={`${number(inference.specialEffectCount, 0)}개`} />
          <StatLine label="핵심 효과 수" value={`${number(data.coreEffectCount, 0)}개`} />
          <StatLine label="역할 판정" value={data.role === 'support' ? '서포터' : '딜러'} />
        </div>

        <div className="detail-stat-card">
          <h3>랜덤 옵션 기대값</h3>
          <StatLine label="필요 카테고리" value={requiredCategoryLabel(random.requiredRandomCategoryCounts)} />
          <StatLine label="대상 카테고리" value={targetCategories} />
          <StatLine label="가중 성공 확률" value={percent(random.weightedSuccessProbability)} accent />
          <StatLine label="기대 시도 수" value={`${number(random.expectedAttempts)}회`} />
        </div>
      </div>

      <div className="notice-panel">
        <strong>전체 옵션을 한 번에 계산하지 않는 이유</strong>
        <p className="section-copy">
          {data.wholeBraceletEffectReason || '현재 팔찌는 고정 옵션과 랜덤 옵션이 섞여 있고 구매 후 계정 귀속되므로, 전체 결과를 하나의 랜덤 목표로 단순화하지 않습니다.'}
        </p>
      </div>

      <div className="effect-chip-grid">
        {effects.length
          ? effects.map((effect, index) => <EffectChip effect={effect} key={`${effect.rawEffect || 'effect'}-${index}`} />)
          : <p className="section-copy">공식 카테고리와 매칭된 팔찌 효과가 없습니다.</p>}
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
