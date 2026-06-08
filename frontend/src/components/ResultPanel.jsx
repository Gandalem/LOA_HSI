import React from 'react';
import SummaryCard from './SummaryCard.jsx';

function money(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Math.round(Number(value)).toLocaleString('ko-KR');
}

function probPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return `${(Number(value) * 100).toFixed(4)}%`;
}

function number(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Number(value).toLocaleString('ko-KR', { maximumFractionDigits: digits });
}

function presetConfidence(value) {
  const map = { high: '높음', medium: '보통', low: '낮음' };
  return map[value] || value || '-';
}

function krwRateFromSummary(summary) {
  if (!summary || !summary.avgGold || !summary.avgKrw) return 0;
  return Number(summary.avgKrw) / Number(summary.avgGold);
}

function distributionRows(result) {
  if (!result?.summary) return [];
  const s = result.summary;
  const krwPerGold = krwRateFromSummary(s);
  const rows = [
    { name: '평균', gold: Math.round(s.avgGold), meaning: '같은 조건으로 새로 만든다고 가정한 평균 기대 비용', userLabel: '평균 재현 비용' },
    { name: '보통 유저', gold: Math.round(s.p50Gold), meaning: '절반은 이 비용 이하, 절반은 이 비용 이상', userLabel: '중간값' },
    { name: '주의 구간', gold: Math.round(s.p75Gold), meaning: '25%는 이보다 더 많이 사용할 수 있음', userLabel: '상위 25% 고비용선' },
    { name: '억까 의심 비용선', gold: Math.round(s.p90Gold), meaning: '10%는 이보다 더 많이 사용할 수 있음', userLabel: '상위 10% 고비용선' },
    { name: '강한 억까 비용선', gold: Math.round(s.p95Gold), meaning: '5%는 이보다 더 많이 사용할 수 있음', userLabel: '상위 5% 고비용선' },
    { name: '극단 비용선', gold: Math.round(s.p99Gold), meaning: '1%만 이보다 더 많이 사용할 수 있음', userLabel: '상위 1% 극단선' }
  ];
  return rows.map((row) => ({ ...row, krw: row.gold * krwPerGold }));
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function memoryNumber(value) {
  if (value === 'unknown' || value === '' || value === null || value === undefined) return null;
  const n = Number(value);
  if (!Number.isFinite(n) || Number.isNaN(n) || n < 0) return null;
  return Math.floor(n);
}

function moduleName(name) {
  const map = { equipment: '장비 재련', abilityStone: '어빌리티 스톤', accessory: '장신구' };
  return map[name] || name;
}

function expectedCostLine(summary, enabled = true) {
  if (!enabled) return '분석 제외';
  if (!summary) return '계산값 없음';
  return `${money(summary.avgGold)} G 평균 / 상위 10% ${money(summary.p90Gold)} G / 상위 1% ${money(summary.p99Gold)} G`;
}

function partLabel(value) {
  const map = {
    weapon: '무기',
    helmet: '투구',
    chest: '상의',
    pants: '하의',
    gloves: '장갑',
    shoulder: '어깨',
    armor_unknown: '방어구 중 하나',
    unknown: '부위 모름'
  };
  return map[value] || value || '부위 모름';
}

function targetLabel(value) {
  if (!value || value === 'unknown') return '강화 구간 모름';
  return value;
}

function targetToLevel(value) {
  if (!value || value === 'unknown') return null;
  const match = String(value).match(/→\s*\+(\d+)/);
  return match ? Number(match[1]) : null;
}

function currentMaxHoningByPart(character, part) {
  const equipment = character?.equipment || [];
  const isWeapon = (item) => String(item.slot || '').includes('무기');
  const partSlotMap = {
    weapon: '무기',
    helmet: '투구',
    chest: '상의',
    pants: '하의',
    gloves: '장갑',
    shoulder: '어깨'
  };
  const rows = equipment.filter((item) => {
    const slot = String(item.slot || '');
    if (part === 'weapon') return isWeapon(item);
    if (part === 'armor_unknown') return !isWeapon(item);
    if (partSlotMap[part]) return slot.includes(partSlotMap[part]);
    return true;
  });
  const levels = rows.map((item) => Number(item.honing_level || 0)).filter((n) => n > 0);
  return levels.length ? Math.max(...levels) : null;
}

function annotatePityRecords(memoryHints, character) {
  return validPityRecords(memoryHints).map((record) => {
    const targetTo = targetToLevel(record.target);
    const currentMax = currentMaxHoningByPart(character, record.part);
    const disconnected = targetTo !== null && currentMax !== null && targetTo > currentMax;
    return { ...record, targetTo, currentMax, disconnected };
  });
}

function validPityRecords(memoryHints) {
  const records = Array.isArray(memoryHints?.pityRecords) ? memoryHints.pityRecords : [];
  return records
    .map((record) => ({
      part: record.part || 'unknown',
      target: record.target || 'unknown'
    }))
    .filter((record) => record.part !== 'unknown' || record.target !== 'unknown');
}

function stageWeight(target) {
  if (!target || target === 'unknown') return 0.55;
  const match = String(target).match(/\+(\d+)\s*→\s*\+(\d+)/);
  const to = match ? Number(match[2]) : 0;
  if (to >= 23) return 1.45;
  if (to >= 22) return 1.3;
  if (to >= 21) return 1.12;
  if (to >= 20) return 0.95;
  if (to >= 18) return 0.78;
  return 0.62;
}

function scorePityRecord(record) {
  const specificArmor = ['helmet', 'chest', 'pants', 'gloves', 'shoulder'].includes(record.part);
  const partBase = record.part === 'weapon' ? 13 : specificArmor ? 8 : record.part === 'armor_unknown' ? 5.5 : 4;
  const unknownPenalty = record.target === 'unknown' ? 0.55 : 1;
  return partBase * stageWeight(record.target) * unknownPenalty;
}

function buildEquipmentMemoryAnalysis(memoryHints, equipmentEnabled, character) {
  if (!equipmentEnabled) {
    return {
      score: 0,
      label: '분석 제외',
      detail: '장비 재련을 선택하지 않아 장기백 기록을 억까 판정에 반영하지 않았습니다.',
      records: [],
      disconnectedRecords: []
    };
  }

  const records = annotatePityRecords(memoryHints, character);
  const connectedRecords = records.filter((record) => !record.disconnected);
  const disconnectedRecords = records.filter((record) => record.disconnected);
  let score = connectedRecords.reduce((sum, record) => sum + scorePityRecord(record), 0);
  score = clamp(score, 0, 42);

  let label = '입력 없음';
  let detail = '장기백 기록을 입력하면 어느 부위/구간에서 비용 충격이 컸는지 보조 판단합니다.';
  if (records.length && !connectedRecords.length) {
    label = '참고 기록만 있음';
    detail = '입력한 장기백 구간이 현재 캐릭터의 장비 강화 단계보다 높아 강한 억까 점수로 반영하지 않았습니다.';
  } else if (connectedRecords.length) {
    const hasUnknown = connectedRecords.some((record) => record.part === 'unknown' || record.target === 'unknown');
    if (score >= 30) label = '강한 장비 억까 단서';
    else if (score >= 18) label = '장비 억까 단서 있음';
    else label = '참고 단서';
    detail = hasUnknown
      ? '장기백 기억은 있지만 부위나 강화 구간이 모호해 약하게 반영했습니다.'
      : '입력한 장기백 기록의 부위와 강화 구간을 기준으로 비용 충격을 반영했습니다.';
    if (disconnectedRecords.length) {
      detail += ' 단, 현재 장비 단계보다 높은 구간 기록은 참고 기록으로만 분리했습니다.';
    }
  }

  return { score: Math.round(score), label, detail, records, connectedRecords, disconnectedRecords };
}
function stoneDifficulty(stone, enabled) {
  if (!enabled) return 0;
  const expected = Number(stone?.expectedStones || 0);
  if (expected >= 700) return 30;
  if (expected >= 300) return 25;
  if (expected >= 150) return 20;
  if (expected >= 50) return 14;
  if (expected >= 10) return 8;
  return 4;
}

function equipmentDifficulty(module) {
  if (!module) return 0;
  const avg = Number(module?.summary?.avgGold || 0);
  const p90 = Number(module?.summary?.p90Gold || 0);
  const spread = p90 && avg ? (p90 / avg - 1) : 0;
  let score = 0;
  if (avg >= 8000000) score = 34;
  else if (avg >= 5000000) score = 30;
  else if (avg >= 3000000) score = 24;
  else if (avg >= 1000000) score = 16;
  else if (avg > 0) score = 8;
  score += clamp(spread * 30, 0, 8);
  return clamp(score, 0, 38);
}

function accessoryDifficulty(expectedValues, enabled) {
  if (!enabled) return 0;
  const acc = expectedValues?.accessoryPolishing?.combination || {};
  const coreLines = Number(acc.currentCoreEffectLineCount ?? (acc.currentCoreEffects || []).length);
  const secondaryLines = Number(acc.currentSecondaryEffectLineCount ?? (acc.currentSecondaryEffects || []).length);
  const weighted = coreLines + secondaryLines * 0.5;
  if (weighted >= 10) return 16;
  if (weighted >= 6) return 12;
  if (weighted >= 3) return 8;
  if (weighted >= 1) return 4;
  return 0;
}

function braceletDifficulty(expectedValues, enabled) {
  if (!enabled) return 0;
  const bracelet = expectedValues?.braceletT4 || {};
  const validCount = Number((bracelet.currentValidEffects || []).length || 0);
  const secondaryCount = Number((bracelet.currentSecondaryEffects || []).length || 0);
  const conditionalCount = Number((bracelet.currentConditionalEffects || []).length || 0);
  const total = validCount + secondaryCount * 0.5 + conditionalCount * 0.5;
  if (total >= 5) return 16;
  if (total >= 3) return 12;
  if (total >= 1) return 7;
  return 0;
}

function buildDifficultyReport(result) {
  const expected = result?.expectedValues || {};
  const modules = result?.modules || {};
  const equipmentEnabled = Boolean(modules.equipment);
  const stoneEnabled = Boolean(modules.abilityStone);
  const accessoryEnabled = Boolean(modules.accessory);

  const parts = [
    {
      key: 'equipment',
      name: '장비 재련',
      enabled: equipmentEnabled,
      score: Math.round(equipmentDifficulty(modules.equipment)),
      kind: equipmentEnabled ? '재현 비용' : '분석 제외',
      detail: equipmentEnabled ? '현재 강화 단계까지 새로 올린다고 가정한 비용 부담입니다.' : '비교 설정에서 장비 재련을 선택하지 않았습니다.'
    },
    {
      key: 'abilityStone',
      name: '어빌리티 스톤',
      enabled: stoneEnabled,
      score: Math.round(stoneDifficulty(expected.abilityStone, stoneEnabled)),
      kind: stoneEnabled ? '결과물 희귀도' : '분석 제외',
      detail: stoneEnabled ? '현재 활성 레벨 결과물이 나올 기대 시도 수 기준입니다.' : '비교 설정에서 어빌리티 스톤을 선택하지 않았습니다.'
    },
    {
      key: 'accessory',
      name: '장신구 연마',
      enabled: accessoryEnabled,
      score: Math.round(accessoryDifficulty(expected, accessoryEnabled)),
      kind: accessoryEnabled ? '유효 옵션' : '분석 제외',
      detail: accessoryEnabled ? '현재 장신구에 붙은 핵심/보조 유효 옵션 기준입니다.' : '비교 설정에서 장신구/팔찌를 선택하지 않았습니다.'
    },
    {
      key: 'bracelet',
      name: '팔찌',
      enabled: accessoryEnabled,
      score: Math.round(braceletDifficulty(expected, accessoryEnabled)),
      kind: accessoryEnabled ? '유효 옵션' : '분석 제외',
      detail: accessoryEnabled ? '현재 팔찌의 핵심/보조/조건부 옵션 기준입니다.' : '비교 설정에서 장신구/팔찌를 선택하지 않았습니다.'
    }
  ];
  const total = Math.round(clamp(parts.reduce((sum, part) => sum + part.score, 0), 0, 100));
  let label = '보통';
  if (total >= 70) label = '높음';
  else if (total >= 45) label = '약간 높음';
  return { total, label, parts, strongest: [...parts].filter((part) => part.enabled).sort((a, b) => b.score - a.score)[0] || null };
}

function attemptComparisonAnalysis({ actualAttempts, expectedAttempts, itemName = '시도', unit = '회', enabled = true }) {
  if (!enabled) {
    return { score: 0, offsetScore: 0, label: '분석 제외', detail: `${itemName} 항목을 선택하지 않아 판정에 반영하지 않았습니다.`, ratio: null, direction: 'none' };
  }
  if (actualAttempts === null || actualAttempts === undefined) {
    return { score: 0, offsetScore: 0, label: '입력 안 함', detail: `${itemName} 수를 입력하면 기대값 대비 억까인지, 잘 나온 편인지 판단합니다.`, ratio: null, direction: 'none' };
  }
  if (!expectedAttempts || expectedAttempts <= 0) {
    return { score: 0, offsetScore: 0, label: '기대값 없음', detail: '기대값을 계산하지 못해 억까/상쇄 점수에 반영하지 않습니다.', ratio: null, direction: 'none' };
  }
  const ratio = actualAttempts / expectedAttempts;
  const p = 1 / expectedAttempts;
  const cdf = 1 - Math.pow(1 - p, actualAttempts);
  const cdfPercent = cdf * 100;
  const base = { ratio, cdf, cdfPercent };
  if (cdf < 0.5) {
    const offsetScore = Math.round(clamp(((0.5 - cdf) / 0.5) * 15, 1, 15));
    return { ...base, score: 0, offsetScore, label: '잘 나온 편', detail: `같은 목표 기준 ${number(actualAttempts, 0)}${unit} 안에 성공할 누적확률은 약 ${number(cdfPercent, 1)}%입니다. 평균보다 빠른 편이라 억까가 아니라 상쇄 단서로 봅니다.`, direction: 'good' };
  }
  if (cdf < 0.75) return { ...base, score: 5, offsetScore: 0, label: '평균 근처', detail: `같은 목표 기준 누적확률 약 ${number(cdfPercent, 1)}% 지점입니다. 평균 근처라 약한 단서로만 봅니다.`, direction: 'bad' };
  if (cdf < 0.90) return { ...base, score: 15, offsetScore: 0, label: '늦은 편', detail: `같은 목표 기준 누적확률 약 ${number(cdfPercent, 1)}% 지점입니다. 보통보다 늦은 편입니다.`, direction: 'bad' };
  if (cdf < 0.95) return { ...base, score: 25, offsetScore: 0, label: '억까 의심', detail: `같은 목표 기준 누적확률 약 ${number(cdfPercent, 1)}% 지점입니다. 억까 의심 단서로 봅니다.`, direction: 'bad' };
  if (cdf < 0.99) return { ...base, score: 35, offsetScore: 0, label: '강한 억까', detail: `같은 목표 기준 누적확률 약 ${number(cdfPercent, 1)}% 지점입니다. 강한 억까 단서로 봅니다.`, direction: 'bad' };
  const suspiciousInput = ratio >= 100;
  const detail = suspiciousInput
    ? `입력값이 매우 큽니다. 그래도 입력한 ${number(actualAttempts, 0)}${unit}가 사실이라면 누적확률 약 ${number(cdfPercent, 3)}% 지점의 극단적 억까입니다.`
    : `같은 목표 기준 누적확률 약 ${number(cdfPercent, 2)}% 지점입니다. 입력값이 사실이라면 이 항목만으로도 접을 만한 수준입니다.`;
  return { ...base, score: 45, offsetScore: 0, label: '극단적 억까', detail, direction: 'bad', extreme: true, suspiciousInput };
}

function hasMemoryEvidence(memoryHints, result) {
  const modules = result?.modules || {};
  const records = validPityRecords(memoryHints);
  const attempts = memoryNumber(memoryHints?.stoneAttempts);
  return (Boolean(modules.equipment) && records.length > 0) || (Boolean(modules.abilityStone) && attempts !== null && attempts > 0);
}

function buildMemoryReport(result, memoryHints = {}) {
  const expected = result?.expectedValues || {};
  const modules = result?.modules || {};
  const equipmentEnabled = Boolean(modules.equipment);
  const stoneEnabled = Boolean(modules.abilityStone);
  const stoneExpected = Number(expected.abilityStone?.expectedStones || 0);
  const stoneAttempts = memoryNumber(memoryHints?.stoneAttempts);
  const evidence = hasMemoryEvidence(memoryHints, result);

  const equipmentAnalysis = buildEquipmentMemoryAnalysis(memoryHints, equipmentEnabled, result?.character);
  const equipment = clamp(equipmentAnalysis.score, 0, 42);

  const stoneAnalysis = attemptComparisonAnalysis({ actualAttempts: stoneAttempts, expectedAttempts: stoneExpected, itemName: '스톤 시도', unit: '개', enabled: stoneEnabled });
  const stone = clamp(stoneAnalysis.score, 0, 100);

  const parts = [
    { key: 'equipment', name: '장비 재련', score: Math.round(equipment), kind: equipmentAnalysis.label, detail: equipmentAnalysis.detail },
    { key: 'abilityStone', name: '어빌리티 스톤', score: Math.round(stone), kind: stoneAnalysis.label, detail: stoneAnalysis.detail }
  ];

  const offsetParts = [];
  if (stoneAnalysis.offsetScore > 0) {
    offsetParts.push({ key: 'abilityStone', name: '어빌리티 스톤', score: Math.round(stoneAnalysis.offsetScore), kind: stoneAnalysis.label, detail: stoneAnalysis.detail });
  }

  const rawTotal = equipment + stone;
  const offsetTotal = offsetParts.reduce((sum, part) => sum + part.score, 0);
  let total = Math.round(clamp(rawTotal - offsetTotal, 0, 100));
  if (stoneAnalysis.extreme) total = Math.max(total, 80);
  const strongest = [...parts].filter((part) => part.score > 0).sort((a, b) => b.score - a.score)[0] || null;

  if (!evidence) {
    return {
      total,
      offsetTotal,
      scoreLabel: '보류',
      verdict: '판정 보류',
      tone: 'stable',
      oneLine: '기억 기반 단서가 없어 실제 억까 여부는 단정하지 않습니다. 현재 결과물의 재현 난이도만 참고하세요.',
      strongest: null,
      parts,
      offsetParts,
      evidence,
      stoneAnalysis,
      equipmentAnalysis
    };
  }

  let verdict = '억까 단서 약함';
  let tone = 'stable';
  let oneLine = '입력한 기억만 보면 접을 만큼의 억까라고 단정하기는 어렵습니다.';
  if (stoneAnalysis.extreme || total >= 90) {
    verdict = '극단적 억까';
    tone = 'danger';
    oneLine = stoneAnalysis.extreme
      ? '어빌리티 스톤에서 극단적 초과 시도 단서가 감지되었습니다. 입력값이 사실이라면 이 구간만으로도 접을 만한 수준입니다.'
      : '입력한 기억 기준으로 극단적인 억까 단서가 있습니다.';
  } else if (total >= 70) {
    verdict = '접을 만했음';
    tone = 'danger';
    oneLine = '입력한 장기백 구간과 시도 수 기준으로 억까 체감이 매우 컸을 가능성이 높습니다.';
  } else if (total >= 45) {
    verdict = '억까 의심 높음';
    tone = 'warning';
    oneLine = '기억 기반 단서상 평균보다 강한 성장 스트레스가 있었을 가능성이 큽니다.';
  } else if (total >= 20) {
    verdict = '억까 가능성 있음';
    tone = 'caution';
    oneLine = '일부 구간에서 억까 체감이 있었을 가능성이 있습니다.';
  }

  if (offsetTotal > 0 && total < 45) {
    oneLine += ' 다만 기대보다 잘 나온 구간이 있어 일부 체감은 상쇄될 수 있습니다.';
  }

  return { total, offsetTotal, scoreLabel: `${total}/100`, verdict, tone, oneLine, strongest, parts, offsetParts, evidence, stoneAnalysis, equipmentAnalysis };
}

function detectedAreaNamesFromReport(memoryReport) {
  const detected = (memoryReport?.parts || []).filter((part) => part.score > 0);
  return detected.length ? detected.map((part) => part.name).join(', ') : '없음';
}

function PityRecordSummary({ records, disconnectedRecords = [] }) {
  if (!records.length) return <span>장기백 기록: <strong>입력 안 함</strong></span>;
  return (
    <span className="memory-record-span">
      <span>장기백 기록:</span>
      <strong>{records.map((record) => `${partLabel(record.part)} · ${targetLabel(record.target)}${record.disconnected ? ' (현재 장비와 직접 연결 안 됨)' : ''}`).join(' / ')}</strong>
      {disconnectedRecords.length > 0 && <small>현재 캐릭터 장비 단계보다 높은 구간은 점수에 강하게 반영하지 않았습니다.</small>}
    </span>
  );
}

function MemoryInterpretation({ memoryHints, memoryReport }) {
  const stoneAttempts = memoryNumber(memoryHints?.stoneAttempts);
  const records = memoryReport.equipmentAnalysis.records || [];
  return (
    <div className="ekka-memory-card compact-report-card">
      <h3>기억 입력 해석</h3>
      <div className="memory-list">
        <PityRecordSummary records={records} disconnectedRecords={memoryReport.equipmentAnalysis.disconnectedRecords || []} />
        <span>스톤 시도 개수: <strong>{stoneAttempts === null ? '입력 안 함' : `${stoneAttempts.toLocaleString('ko-KR')}개`}</strong></span>
        <span>숫자 입력으로 감지된 의심 구간: <strong>{detectedAreaNamesFromReport(memoryReport)}</strong></span>
      </div>
      <p className="hint">장기백은 부위와 강화 구간을 기준으로 봅니다. 현재 캐릭터와 직접 연결되지 않는 구간은 참고 기록으로만 표시합니다.</p>
    </div>
  );
}
function EffectTagList({ items, empty = '-' }) {
  if (!items?.length) return <span>{empty}</span>;
  return <div className="effect-tag-list">{items.map((item, idx) => <span className="effect-tag" key={`${item}-${idx}`}>{item}</span>)}</div>;
}

function ReportList({ title, items, empty, className = '' }) {
  return (
    <div className={`report-card ${className}`}>
      <h3>{title}</h3>
      {items?.length ? (
        <div className="report-item-list">
          {items.map((item) => (
            <div className="report-item" key={item.key}>
              <div className="report-item-head"><strong>{item.name}</strong><span>{item.score}점</span></div>
              <p>{item.kind}</p>
              <small>{item.detail}</small>
            </div>
          ))}
        </div>
      ) : (
        <p className="hint">{empty}</p>
      )}
    </div>
  );
}

function DifficultyCards({ difficulty }) {
  return (
    <div className="difficulty-card-grid compact-difficulty-grid">
      {difficulty.parts.map((part) => (
        <div className={`difficulty-card ${part.enabled ? '' : 'muted-card'}`} key={part.key}>
          <div><strong>{part.name}</strong><span>{part.kind}</span></div>
          <b>{part.enabled ? `${part.score}점` : '제외'}</b>
          <p>{part.detail}</p>
        </div>
      ))}
    </div>
  );
}

function ExpectedValuePanel({ expectedValues }) {
  if (!expectedValues) return null;
  const stone = expectedValues.abilityStone || {};
  const acc = expectedValues.accessoryPolishing || {};
  const bracelet = expectedValues.braceletT4 || {};
  const combo = acc.combination || {};
  const comboTargets = combo.comboTargets || {};
  const keyCombos = ['상상', '상중 이상', '중중 이상', '하하 이상'];
  const braceletAttempts = bracelet.attemptsForAtLeastOnce || {};
  return (
    <div className="expected-panel">
      <h3>계산 근거</h3>
      <div className="expectation-subgrid">
        <div className="table-wrap mini-table-wrap">
          <h4>어빌리티 스톤</h4>
          <table>
            <tbody>
              <tr><th>현재 활성 레벨</th><td>{stone.target || '-'} 활성</td></tr>
              <tr><th>성공 횟수 기준</th><td>{stone.successCountTarget || '-'} 이상</td></tr>
              <tr><th>한 돌 성공확률</th><td>{probPercent(stone.successProbabilityPerStone)}</td></tr>
              <tr><th>기대 스톤 개수</th><td>{number(stone.expectedStones)}개</td></tr>
              <tr><th>9/7 검증값</th><td>{number(stone.reference97ExpectedStones)}개 · {stone.verified ? '정상 범위' : '확인 필요'}</td></tr>
            </tbody>
          </table>
        </div>
        <div className="table-wrap mini-table-wrap">
          <h4>장신구 조합 기대값</h4>
          <table>
            <thead><tr><th>목표 조합</th><th>1회 확률</th><th>기대 횟수</th></tr></thead>
            <tbody>
              {keyCombos.map((name) => {
                const row = comboTargets[name] || {};
                return (
                  <tr key={name}>
                    <td>{name}</td>
                    <td>{probPercent(row.probability)}</td>
                    <td>{number(row.expectedAttempts)}회</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="hint">공식 장신구 연마 확률표는 로컬 데이터로 포함했습니다. 직접 연마 시도 수 입력은 아직 화면에 넣지 않았기 때문에 억까 지수에는 반영하지 않습니다.</p>
        </div>
        <div className="table-wrap mini-table-wrap">
          <h4>팔찌 유효 특수효과</h4>
          <table>
            <tbody>
              <tr><th>역할 프리셋</th><td>{bracelet.role === 'support' ? '서포터' : '딜러'}</td></tr>
              <tr><th>1회 확률</th><td>{probPercent(bracelet.targetProbabilityOneOrMoreValidSpecial)}</td></tr>
              <tr><th>기대 시도 수</th><td>{number(bracelet.expectedAttemptsForValidSpecial)}회</td></tr>
              <tr><th>90% 도달</th><td>{number(braceletAttempts['90%'])}회</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function MainInterpretation({ memoryReport, difficulty, biggestModule }) {
  const lines = [];
  if (memoryReport.strongest) lines.push(`${memoryReport.strongest.name} 쪽에 기억 기반 억까 단서가 있습니다.`);
  else lines.push('기억 입력만으로는 특정 억까 구간을 강하게 지목하지 않습니다.');
  if (memoryReport.offsetParts.length) lines.push(`${memoryReport.offsetParts.map((x) => x.name).join(', ')}은 기대보다 잘 나온 구간으로 입력되어 상쇄 단서로 봅니다.`);
  if (biggestModule) lines.push(`선택 항목 중 평균 비용이 가장 큰 항목은 ${moduleName(biggestModule.module)}입니다.`);
  if (biggestModule) lines.push('계산 근거와 비용 분포는 세부 분석에서 확인할 수 있습니다.');
  return (
    <div className="interpretation-box">
      <h3>한눈에 보기</h3>
      <ul>{lines.map((line, idx) => <li key={idx}>{line}</li>)}</ul>
    </div>
  );
}

export default function ResultPanel({ result, memoryHints }) {
  if (!result) return null;
  const memoryReport = buildMemoryReport(result, memoryHints);
  const difficulty = buildDifficultyReport(result);
  const total = result.total;
  const rows = distributionRows(total);
  const krwPerGold = krwRateFromSummary(total?.summary);
  const krwPer100Gold = krwPerGold * 100;
  const expected = result.expectedValues || {};
  const stone = expected.abilityStone || {};
  const acc = expected.accessoryPolishing?.combination || {};
  const bracelet = expected.braceletT4 || {};
  const classPreset = expected.classEngravingPreset || result.character?.class_engraving_preset || acc.classPreset || bracelet.classPreset || {};
  const moduleValues = Object.values(result.modules || {});
  const biggestModule = moduleValues.length ? moduleValues.sort((a, b) => (b.summary?.avgGold || 0) - (a.summary?.avgGold || 0))[0] : null;
  const ekkaItems = memoryReport.parts.filter((part) => part.score > 0);

  return (
    <section className={`card result-section ekka-result ${memoryReport.tone}`}>
      <div className="ekka-result-head">
        <div>
          <p className="eyebrow">억까 판정 리포트</p>
          <h2>억까 판정: {memoryReport.verdict}</h2>
          <p>{memoryReport.oneLine}</p>
        </div>
        <div className="ekka-score-ring">
          <span className={memoryReport.evidence ? '' : 'score-pending'}>{memoryReport.evidence ? memoryReport.total : '보류'}</span>
          <small>{memoryReport.evidence ? '/100' : '기억 필요'}</small>
        </div>
      </div>

      <div className="summary-grid ekka-summary-grid compact-summary-grid v38-summary-grid">
        <SummaryCard title="억까 단서" value={memoryReport.scoreLabel} sub="기억 입력 기반" />
        <SummaryCard title="상쇄 단서" value={memoryReport.offsetTotal ? `${memoryReport.offsetTotal}/100` : '없음'} sub="기대보다 잘 나온 구간" />
        <SummaryCard title="가장 큰 평균 비용" value={biggestModule ? moduleName(biggestModule.module) : '분석 없음'} sub={biggestModule ? `${money(biggestModule.summary?.avgGold)} G · 선택 항목 기준` : '선택된 항목 없음'} />
      </div>

      <MainInterpretation memoryReport={memoryReport} difficulty={difficulty} biggestModule={biggestModule} />

      {classPreset.engravingName && (
        <div className="preset-line-box compact-preset-line">
          적용 프리셋: <strong>{classPreset.className} · {classPreset.engravingName}</strong>
          <span>{classPreset.role || '-'}</span>
        </div>
      )}

      <div className="report-two-col v38-report-two-col">
        <ReportList title="억까 단서" items={ekkaItems} empty="입력된 기억만으로는 억까 단서가 잡히지 않았습니다." className="bad-report" />
        <ReportList title="잘 나온 구간" items={memoryReport.offsetParts} empty="기대보다 뚜렷하게 잘 나온 구간 입력은 없습니다." className="good-report" />
      </div>

      <details className="detail-section" key={`${result.character?.character_name || 'result'}-${memoryReport.total}-${memoryReport.offsetTotal}-${total?.summary?.avgGold || 0}`}> 
        <summary>세부 분석 보기</summary>

        <div className="report-card difficulty-report-card compact-report-card">
          <h3>현재 결과물 재현 난이도</h3>
          <p className="hint">억까 판정이 아니라, 현재 캐릭터 결과물이 다시 만들기 얼마나 부담스러운지 보여줍니다.</p>
          <DifficultyCards difficulty={difficulty} />
        </div>

        <MemoryInterpretation memoryHints={memoryHints} memoryReport={memoryReport} />

        <div className="ekka-module-grid">
          <div className="ekka-module-card danger-line">
            <div className="module-title-row"><strong>장비 재련</strong><span>{result.modules?.equipment ? '장기백 구간 기반' : '분석 제외'}</span></div>
            <p>{result.modules?.equipment ? '현재 장비 강화 단계까지 새로 올린다고 가정한 비용 분포입니다.' : '비교 설정에서 장비 재련이 선택되지 않아 장비 재현 비용과 장기백 단서를 계산하지 않았습니다.'}</p>
            <ul>
              <li>재현 비용: {expectedCostLine(result.modules?.equipment?.summary, Boolean(result.modules?.equipment))}</li>
              <li>장기백 해석: {memoryReport.equipmentAnalysis.label}</li>
              <li>{memoryReport.equipmentAnalysis.detail}</li>
              <li>입력 기록: {memoryReport.equipmentAnalysis.records.length ? memoryReport.equipmentAnalysis.records.map((record) => `${partLabel(record.part)} ${targetLabel(record.target)}${record.disconnected ? ' (현재 장비와 직접 연결 안 됨)' : ''}`).join(' / ') : '입력 안 함'}</li>
            </ul>
          </div>
          <div className="ekka-module-card purple-line">
            <div className="module-title-row"><strong>어빌리티 스톤</strong><span>{memoryReport.stoneAnalysis?.direction === 'good' ? '상쇄 단서' : result.modules?.abilityStone ? '시도 수 비교' : '분석 제외'}</span></div>
            <p>{result.modules?.abilityStone ? '현재 스톤 활성 레벨을 성공 횟수 기준으로 변환해 기대 시도 수를 계산합니다.' : '비교 설정에서 어빌리티 스톤이 선택되지 않았습니다.'}</p>
            <ul>
              <li>현재 목표: {stone.target || '-'} 활성 · 성공 {stone.successCountTarget || '-'} 이상</li>
              <li>한 돌 성공확률: {probPercent(stone.successProbabilityPerStone)}</li>
              <li>기대 스톤 개수: {number(stone.expectedStones)}개</li>
              <li>입력 시도 수: {memoryNumber(memoryHints?.stoneAttempts) === null ? '입력 안 함' : `${number(memoryNumber(memoryHints?.stoneAttempts), 0)}개`}</li>
              <li>시도 수 해석: {memoryReport.stoneAnalysis?.label || '-'}</li>
              <li>{memoryReport.stoneAnalysis?.detail || '스톤 시도 수를 입력하면 기대값 대비 초과/상쇄 여부를 판단합니다.'}</li>
            </ul>
          </div>
          <div className="ekka-module-card orange-line">
            <div className="module-title-row"><strong>장신구 연마</strong><span>{result.modules?.accessory ? '유효 옵션 분리' : '분석 제외'}</span></div>
            <p>{result.modules?.accessory ? '총 파싱 효과를 핵심 유효 / 보조 유효 / 비핵심으로 나눠 표시합니다. v43에서는 직접 연마 시도 수를 받지 않으므로 억까 지수에는 넣지 않습니다.' : '비교 설정에서 장신구/팔찌가 선택되지 않았습니다.'}</p>
            <ul>
              <li>프리셋: {classPreset.engravingName ? `${classPreset.className} · ${classPreset.engravingName}` : (acc.role === 'support' ? '서포터' : '딜러')}</li>
              <li>파싱 효과 줄: {acc.currentParsedEffectCount ?? (acc.currentParsedEffects || []).length}개 <span className="muted-small">/ 고유 {acc.currentParsedUniqueEffectCount ?? (acc.currentParsedEffects || []).length}개</span></li>
              <li>핵심 유효 종류: {acc.currentCoreTypeCount ?? acc.currentCoreCount ?? (acc.currentCoreEffects || acc.currentValidLikeEffects || []).length}종</li>
              <li>핵심 유효 효과: {acc.currentCoreEffectLineCount ?? (acc.currentCoreEffects || acc.currentValidLikeEffects || []).length}개</li>
              <li>보조 유효 종류: {acc.currentSecondaryTypeCount ?? acc.currentSecondaryCount ?? (acc.currentSecondaryEffects || []).length}종</li>
              <li>보조 유효 효과: {acc.currentSecondaryEffectLineCount ?? (acc.currentSecondaryEffects || []).length}개</li>
              <li>비핵심 효과: {acc.currentNonCoreCount ?? (acc.currentNonCoreEffects || []).length}개</li>
              <li>핵심 옵션: <EffectTagList items={(acc.currentCoreEffects || acc.currentValidLikeEffects || []).slice(0, 12)} /></li>
              <li>보조 옵션: <EffectTagList items={(acc.currentSecondaryEffects || []).slice(0, 12)} /></li>
            </ul>
          </div>
          <div className="ekka-module-card blue-line">
            <div className="module-title-row"><strong>팔찌</strong><span>{result.modules?.accessory ? '핵심/보조/조건부 분리' : '분석 제외'}</span></div>
            <p>{result.modules?.accessory ? '직업/역할 프리셋에 따라 팔찌 효과를 핵심 유효·보조 유효·조건부 옵션으로 나눠 표시합니다. v43에서는 획득 방식/시도 수를 받지 않으므로 억까 지수에는 넣지 않습니다.' : '비교 설정에서 장신구/팔찌가 선택되지 않았습니다.'}</p>
            <ul>
              <li>프리셋: {classPreset.engravingName ? `${classPreset.className} · ${classPreset.engravingName}` : (bracelet.role === 'support' ? '서포터' : '딜러')} · 등급 {bracelet.grade || '-'}</li>
              <li>핵심 유효 옵션: <EffectTagList items={bracelet.currentValidEffects || []} /></li>
              <li>보조 옵션: <EffectTagList items={bracelet.currentSecondaryEffects || []} /></li>
              <li>조건부 옵션: <EffectTagList items={bracelet.currentConditionalEffects || []} /></li>
              <li>핵심/보조/조건부 합계: {(bracelet.currentValidLikeEffects || []).length}개</li>
              <li>유효 특수 1개 이상 기대: {number(bracelet.expectedAttemptsForValidSpecial)}회</li>
            </ul>
          </div>
        </div>

        <div className="table-wrap percentile-table-wrap">
          <h3>선택 항목 재현 비용 분포</h3>
          <table>
            <thead><tr><th>구간</th><th>골드 비용</th><th>원화 환산</th><th>의미</th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.name}>
                  <td><strong>{row.name}</strong><br /><span className="muted-small">{row.userLabel}</span></td>
                  <td>{money(row.gold)} G</td>
                  <td>{money(row.krw)} 원</td>
                  <td>{row.meaning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <ExpectedValuePanel expectedValues={result.expectedValues} />

        <h3>모듈별 원자료</h3>
        <div className="module-grid">
          {Object.values(result.modules || {}).map((m) => (
            <div className="module-card" key={m.module}>
              <strong>{moduleName(m.module)}</strong>
              <div>평균 재현 비용: {money(m.summary.avgGold)} G</div>
              <div>보통 유저 기준: {money(m.summary.p50Gold)} G</div>
              <div>상위 10% 고비용선: {money(m.summary.p90Gold)} G</div>
              <div>상위 1% 극단선: {money(m.summary.p99Gold)} G</div>
            </div>
          ))}
        </div>

        <details className="assumptions">
          <summary>가정 및 저장 경로</summary>
          <ul>{result.assumptions?.map((a, idx) => <li key={idx}>{a}</li>)}</ul>
          <pre>{JSON.stringify(result.artifactPaths, null, 2)}</pre>
        </details>
      </details>
    </section>
  );
}
