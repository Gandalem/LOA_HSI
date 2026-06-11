import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';

function number(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Number(value).toLocaleString('ko-KR', { maximumFractionDigits: digits });
}

function percent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '계산 안 함';
  return `${(Number(value) * 100).toFixed(4)}%`;
}

function roleLabel(value) {
  const map = { core: '핵심', secondary: '보조', conditional: '조건부', unmatched: '미분류' };
  return map[value] || value || '-';
}

function basisLabel(value) {
  const map = {
    user_input: '사용자 입력',
    auto_special_count: '자동 추정 · 특수옵션 3개 감지',
    auto_special_count_requires_all_random_special: '특수옵션 3개 랜덤 필요',
    auto_estimate: '자동 추정',
    auto_fallback: '자동 보정',
    partial_user_input_auto_completed: '일부 입력 + 자동 보정',
    official_distribution: '공식 분포'
  };
  return map[value] || value || '-';
}

function braceletSignature(data) {
  if (!data) return '';
  return JSON.stringify({
    version: data.version,
    matched: data.matchedEffectCount,
    unmatched: data.unmatchedEffectCount,
    core: data.coreEffectCount,
    randomProbability: data.randomOptionBasis && data.randomOptionBasis.weightedSuccessProbability,
    user: data.purchaseStructure && data.purchaseStructure.userInput,
    effects: (data.matchedEffects || []).map((row) => [row.rawEffect, row.category, row.matchRole])
  });
}

function requiredCategoryLabel(required) {
  const entries = Object.entries(required || {});
  if (!entries.length) return '-';
  return entries.map(([key, value]) => `${key} ${value}개`).join(', ');
}

function EffectChip({ effect }) {
  const category = effect?.categoryLabel || effect?.category || '-';
  return (
    <div className="combo-chip">
      <span>{effect?.rawEffect || '-'}</span>
      <strong>{category} · {roleLabel(effect?.matchRole)}</strong>
      <small>카테고리 표기확률 {percent(effect?.categoryDisplayProbability)}</small>
    </div>
  );
}

function StatLine({ label, value, highlight = false }) {
  return (
    <div className={highlight ? 'evidence-line highlight' : 'evidence-line'}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function BraceletOfficialCard({ officialBracelet }) {
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
  const signature = braceletSignature(data);

  return (
    <div
      className="expected-panel evidence-panel loa-hsi-bracelet-react"
      data-loa-hsi-bracelet-v54="true"
      data-loa-hsi-bracelet-react="true"
      data-signature={signature}
    >
      <h3>팔찌 T4 공식 매칭</h3>
      <p className="hint evidence-intro">
        v60.1 기준 팔찌 슬롯 수는 기본 자동 추정합니다. 특수옵션이 3개면 랜덤 3개 구성으로 우선 추정하고, 기대값은 필요한 카테고리 개수 기준으로 계산합니다.
      </p>

      <div className="evidence-card-grid">
        <section className="evidence-card">
          <div className="evidence-card-head">
            <strong>구매/귀속 구조</strong>
            <span>{data.gradeLabel || '-'}</span>
          </div>
          <StatLine label="고정 옵션 기준" value={fixedCount == null ? '자동 추정 불가' : `고정 ${fixedCount}개`} highlight />
          <StatLine label="랜덤 슬롯 기준" value={randomCount == null ? '자동 추정 불가' : `랜덤 ${randomCount}개`} />
          <StatLine label="계산 기준" value={basisLabel(calcBasis)} />
          <StatLine label="추정 사유" value={inference.reason || '-'} />
        </section>

        <section className="evidence-card">
          <div className="evidence-card-head">
            <strong>현재 팔찌 매칭</strong>
            <span>{data.role === 'support' ? '서포터' : '딜러'}</span>
          </div>
          <StatLine label="매칭 성공" value={`${number(data.matchedEffectCount, 0)}개`} highlight />
          <StatLine label="특수옵션" value={`${number(inference.specialEffectCount, 0)}개`} />
          <StatLine label="핵심 효과" value={`${number(data.coreEffectCount, 0)}개`} />
        </section>

        <section className="evidence-card">
          <div className="evidence-card-head">
            <strong>랜덤 옵션 기준</strong>
            <span>직접 돌린 슬롯</span>
          </div>
          <StatLine label="필요 카테고리" value={requiredCategoryLabel(random.requiredRandomCategoryCounts)} highlight />
          <StatLine label="대상 카테고리" value={targetCategories} />
          <StatLine label="랜덤 슬롯 기준 성공률" value={percent(random.weightedSuccessProbability)} />
          <StatLine label="기대 시도 수" value={`${number(random.expectedAttempts)}회`} />
        </section>
      </div>

      <div className="notice-panel">
        <strong>전체 효과 확률</strong>
        <p className="hint">{data.wholeBraceletEffectReason || '현재 팔찌 전체 효과는 고정 옵션과 랜덤 옵션이 섞일 수 있어 하나의 랜덤 목표로 계산하지 않습니다.'}</p>
      </div>

      <div className="combo-chip-grid">
        {effects.length ? effects.map((effect, index) => (
          <EffectChip effect={effect} key={`${effect.rawEffect || 'effect'}-${index}`} />
        )) : <p className="hint">공식 카테고리와 매칭된 팔찌 효과가 없습니다.</p>}
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

export default function BraceletOfficialPanel({ officialBracelet }) {
  const [portalHost, setPortalHost] = useState(null);

  useEffect(() => {
    if (!officialBracelet) {
      setPortalHost(null);
      return undefined;
    }

    let cancelled = false;
    let timer = null;
    let attempts = 0;

    function ensureHost() {
      if (cancelled) return;
      attempts += 1;
      const details = document.querySelector('.detail-section');
      if (!details) {
        if (attempts < 30) timer = window.setTimeout(ensureHost, 100);
        return;
      }

      details.querySelectorAll('[data-loa-hsi-bracelet-v54="true"]:not([data-loa-hsi-bracelet-react="true"])').forEach((node) => node.remove());

      let host = details.querySelector('[data-loa-hsi-bracelet-portal="true"]');
      if (!host) {
        host = document.createElement('div');
        host.dataset.loaHsiBraceletPortal = 'true';
        const marketHost = details.querySelector('[data-loa-hsi-market-v601-portal="true"]');
        if (marketHost) details.insertBefore(host, marketHost);
        else details.appendChild(host);
      }
      setPortalHost(host);
    }

    ensureHost();

    return function cleanup() {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [officialBracelet]);

  if (!officialBracelet || !portalHost) return null;
  return createPortal(<BraceletOfficialCard officialBracelet={officialBracelet} />, portalHost);
}
