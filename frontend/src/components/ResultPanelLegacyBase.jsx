import React from 'react';
import SummaryCard from './SummaryCard.jsx';

function money(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Math.round(Number(value)).toLocaleString('ko-KR');
}

function number(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Number(value).toLocaleString('ko-KR', { maximumFractionDigits: digits });
}

function probPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return `${(Number(value) * 100).toFixed(4)}%`;
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
    { name: '억까 의심 비용선', gold: Math.round(s.p90Gold), meaning: '10%는 이보다 더 많이 사용할 수 있음', userLabel: '상위 10% 고비용선' },
    { name: '극단 비용선', gold: Math.round(s.p99Gold), meaning: '1%만 이보다 더 많이 사용할 수 있음', userLabel: '상위 1% 극단선' }
  ];
  return rows.map((row) => ({ ...row, krw: row.gold * krwPerGold }));
}

function accessoryKey(item, index) {
  return `${item?.slot || '장신구'}-${index}`;
}

function partKey(slot) {
  const text = String(slot || '');
  if (text.includes('목걸이')) return 'necklace';
  if (text.includes('귀걸이')) return 'earring';
  if (text.includes('반지')) return 'ring';
  return 'accessory';
}

function firstNumber(text) {
  const match = String(text || '').match(/[+＋-]?(\d+(?:\.\d+)?)/);
  return match ? Number(match[1]) : null;
}

function hasPercent(text) {
  return String(text || '').includes('%');
}

function gradeFromThreshold(value, thresholds) {
  if (value === null || value === undefined) return 1;
  for (const [min, level] of thresholds) {
    if (value >= min) return level;
  }
  return 1;
}

function gradeLabel(level) {
  if (level >= 3) return '상';
  if (level >= 2) return '중';
  return '하';
}

function singleGradeProbability(level) {
  if (level >= 3) return 0.007;
  if (level >= 2) return 0.030;
  return 0.063;
}

function effectGrade(effect, slot) {
  const e = String(effect || '');
  const v = firstNumber(e);
  const part = partKey(slot);

  if (part === 'necklace') {
    if (e.includes('추가 피해')) return { keyword: '추가 피해', level: gradeFromThreshold(v, [[2.6, 3], [1.6, 2], [0.6, 1]]) };
    if (e.includes('적에게 주는 피해')) return { keyword: '적에게 주는 피해', level: gradeFromThreshold(v, [[2.0, 3], [1.2, 2], [0.55, 1]]) };
    if (e.includes('무기 공격력') && !hasPercent(e)) return { keyword: '무기 공격력', level: gradeFromThreshold(v, [[960, 3], [480, 2], [195, 1]]) };
    if (e.includes('공격력') && !hasPercent(e)) return { keyword: '공격력', level: gradeFromThreshold(v, [[390, 3], [195, 2], [80, 1]]) };
    if (e.includes('낙인력')) return { keyword: '낙인력', level: gradeFromThreshold(v, [[8.0, 3], [4.8, 2], [2.15, 1]]) };
    if (e.includes('세레나데') || e.includes('신앙') || e.includes('조화 게이지') || e.includes('아덴')) return { keyword: '아덴 획득량', level: gradeFromThreshold(v, [[6.0, 3], [3.6, 2], [1.6, 1]]) };
  }

  if (part === 'earring') {
    if (e.includes('무기 공격력') && hasPercent(e)) return { keyword: '무기 공격력 %', level: gradeFromThreshold(v, [[3.0, 3], [1.8, 2], [0.8, 1]]) };
    if (e.includes('공격력') && hasPercent(e) && !e.includes('무기 공격력')) return { keyword: '공격력 %', level: gradeFromThreshold(v, [[1.55, 3], [0.95, 2], [0.4, 1]]) };
    if (e.includes('무기 공격력') && !hasPercent(e)) return { keyword: '무기 공격력', level: gradeFromThreshold(v, [[960, 3], [480, 2], [195, 1]]) };
    if (e.includes('공격력') && !hasPercent(e)) return { keyword: '공격력', level: gradeFromThreshold(v, [[390, 3], [195, 2], [80, 1]]) };
  }

  if (part === 'ring') {
    if (e.includes('치명타 적중률')) return { keyword: '치명타 적중률', level: gradeFromThreshold(v, [[1.55, 3], [0.95, 2], [0.4, 1]]) };
    if (e.includes('치명타 피해')) return { keyword: '치명타 피해', level: gradeFromThreshold(v, [[4.0, 3], [2.4, 2], [1.1, 1]]) };
    if (e.includes('아군 공격력 강화')) return { keyword: '아군 공격력 강화', level: gradeFromThreshold(v, [[5.0, 3], [3.0, 2], [1.35, 1]]) };
    if (e.includes('아군 피해량 강화')) return { keyword: '아군 피해량 강화', level: gradeFromThreshold(v, [[7.5, 3], [4.5, 2], [2.0, 1]]) };
    if (e.includes('무기 공격력') && !hasPercent(e)) return { keyword: '무기 공격력', level: gradeFromThreshold(v, [[960, 3], [480, 2], [195, 1]]) };
    if (e.includes('공격력') && !hasPercent(e) && !e.includes('아군 공격력')) return { keyword: '공격력', level: gradeFromThreshold(v, [[390, 3], [195, 2], [80, 1]]) };
  }

  return null;
}

function comboProbability(levelA, levelB, comboTargets = {}) {
  const a = Math.max(levelA, levelB);
  const b = Math.min(levelA, levelB);
  let targetName = '하하 이상';
  if (a >= 3 && b >= 3) targetName = '상상';
  else if (a >= 3 && b >= 2) targetName = '상중 이상';
  else if (a >= 2 && b >= 2) targetName = '중중 이상';
  else if (a >= 2 && b >= 1) targetName = '중하 이상';

  const fromServer = comboTargets[targetName];
  const fallback = { '상상': 0.0003, '상중 이상': 0.0028, '중중 이상': 0.02, '중하 이상': 0.083, '하하 이상': 0.294 };
  const probability = Number(fromServer?.probability || fallback[targetName] || 0) || null;
  return { targetName, probability, expectedAttempts: probability ? 1 / probability : null };
}

function accessoryTargetForItem(item, comboTargets = {}) {
  const effects = item?.accessory_effects || item?.accessoryEffects || [];
  const matched = effects
    .map((effect) => ({ effect, ...effectGrade(effect, item?.slot) }))
    .filter((row) => row.keyword);

  if (!matched.length) {
    return { probability: null, expectedAttempts: null, label: '유효 연마 없음', coreEffects: [], targetName: null };
  }

  const sorted = [...matched].sort((a, b) => b.level - a.level);
  if (sorted.length >= 2) {
    const [a, b] = sorted;
    const combo = comboProbability(a.level, b.level, comboTargets);
    return { ...combo, label: combo.targetName, coreEffects: sorted, targetName: combo.targetName };
  }

  const level = sorted[0].level;
  const probability = singleGradeProbability(level);
  return { probability, expectedAttempts: 1 / probability, label: `단일 ${gradeLabel(level)}급 유효 옵션`, coreEffects: sorted, targetName: null };
}

function attemptComparisonAnalysis({ actualAttempts, expectedAttempts, itemName = '시도', unit = '회', enabled = true }) {
  if (!enabled) return { score: 0, offsetScore: 0, label: '분석 제외', detail: `${itemName} 항목을 선택하지 않아 판정에 반영하지 않았습니다.`, direction: 'none' };
  if (actualAttempts === null || actualAttempts === undefined) return { score: 0, offsetScore: 0, label: '입력 안 함', detail: `${itemName} 수를 입력하면 기대값 대비 억까인지 판단합니다.`, direction: 'none' };
  if (!expectedAttempts || expectedAttempts <= 0) return { score: 0, offsetScore: 0, label: '기대값 없음', detail: '기대값을 계산하지 못해 반영하지 않습니다.', direction: 'none' };

  const ratio = actualAttempts / expectedAttempts;
  const p = 1 / expectedAttempts;
  const cdf = 1 - Math.pow(1 - p, actualAttempts);
  const cdfPercent = cdf * 100;
  const base = { ratio, cdf, cdfPercent };
  if (cdf < 0.5) {
    const offsetScore = Math.round(clamp(((0.5 - cdf) / 0.5) * 12, 1, 12));
    return { ...base, score: 0, offsetScore, label: '잘 나온 편', detail: `같은 목표 기준 ${number(actualAttempts, 0)}${unit} 안에 성공할 누적확률은 약 ${number(cdfPercent, 1)}%입니다. 평균보다 빠른 편이라 상쇄 단서로 봅니다.`, direction: 'good' };
  }
  if (cdf < 0.75) return { ...base, score: 4, offsetScore: 0, label: '평균 근처', detail: `같은 목표 기준 누적확률 약 ${number(cdfPercent, 1)}% 지점입니다.`, direction: 'bad' };
  if (cdf < 0.90) return { ...base, score: 12, offsetScore: 0, label: '늦은 편', detail: `같은 목표 기준 누적확률 약 ${number(cdfPercent, 1)}% 지점입니다. 보통보다 늦은 편입니다.`, direction: 'bad' };
  if (cdf < 0.95) return { ...base, score: 22, offsetScore: 0, label: '억까 의심', detail: `같은 목표 기준 누적확률 약 ${number(cdfPercent, 1)}% 지점입니다. 억까 의심 단서로 봅니다.`, direction: 'bad' };
  if (cdf < 0.99) return { ...base, score: 32, offsetScore: 0, label: '강한 억까', detail: `같은 목표 기준 누적확률 약 ${number(cdfPercent, 1)}% 지점입니다. 강한 억까 단서로 봅니다.`, direction: 'bad' };
  return { ...base, score: 42, offsetScore: 0, label: '극단적 억까', detail: `같은 목표 기준 누적확률 약 ${number(cdfPercent, 2)}% 지점입니다. 입력값이 사실이라면 강한 억까로 볼 수 있습니다.`, direction: 'bad', extreme: true };
}

function buildAccessoryMemoryAnalysis(result, memoryHints = {}, enabled = true) {
  if (!enabled) return { score: 0, offsetScore: 0, label: '분석 제외', detail: '장신구/팔찌 항목을 선택하지 않았습니다.', items: [], offsetItems: [] };
  const character = result?.character || {};
  const comboTargets = result?.expectedValues?.accessoryPolishing?.combination?.comboTargets || {};
  const acquisitions = memoryHints?.accessoryAcquisitions || {};
  const accessories = (character.accessories || []).filter((item) => item.slot !== '팔찌');
  const items = [];
  const offsetItems = [];
  let score = 0;
  let offsetScore = 0;
  let purchasedCount = 0;
  let unknownCount = 0;

  accessories.forEach((item, index) => {
    const key = accessoryKey(item, index);
    const input = acquisitions[key] || { mode: 'unknown', attempts: '' };
    const mode = input.mode || 'unknown';
    if (mode === 'purchased') {
      purchasedCount += 1;
      return;
    }
    if (mode !== 'polished') {
      unknownCount += 1;
      return;
    }
    const attempts = memoryNumber(input.attempts);
    const target = accessoryTargetForItem(item, comboTargets);
    const analysis = attemptComparisonAnalysis({ actualAttempts: attempts, expectedAttempts: target.expectedAttempts, itemName: `${item.slot || '장신구'} 직접 연마`, unit: '회', enabled: true });
    const row = {
      key,
      name: `${item.slot || '장신구'} · ${item.name || '이름 없음'}`,
      score: Math.round(analysis.score),
      offsetScore: Math.round(analysis.offsetScore),
      kind: analysis.label,
      detail: target.expectedAttempts
        ? `${target.label} 목표 기준 기대 ${number(target.expectedAttempts)}회와 입력 ${attempts === null ? '미입력' : `${number(attempts, 0)}회`}를 비교했습니다. ${analysis.detail}`
        : '현재 장신구에서 비교할 유효 연마 목표를 찾지 못했습니다.',
      target,
      attempts,
      analysis
    };
    if (row.score > 0) {
      items.push(row);
      score += row.score;
    }
    if (row.offsetScore > 0) {
      offsetItems.push({ ...row, score: row.offsetScore });
      offsetScore += row.offsetScore;
    }
  });

  score = Math.round(clamp(score, 0, 35));
  offsetScore = Math.round(clamp(offsetScore, 0, 18));
  let label = '입력 없음';
  let detail = '직접 연마한 장신구와 시도 수를 입력하면 표 기준으로 비교합니다.';
  if (items.length) {
    label = score >= 30 ? '강한 장신구 억까 단서' : score >= 15 ? '장신구 억까 단서 있음' : '약한 장신구 단서';
    detail = '직접 연마로 입력한 장신구의 실제 옵션 등급 조합과 시도 수를 비교했습니다.';
  } else if (offsetItems.length) {
    label = '잘 나온 장신구 기록 있음';
    detail = '직접 연마한 장신구 중 기대보다 적은 시도에 끝난 기록이 있습니다.';
  } else if (purchasedCount || unknownCount) {
    label = '점수 미반영';
    detail = '구매함/기억 안 남으로 선택한 장신구는 억까 점수에 넣지 않았습니다.';
  }
  return { score, offsetScore, label, detail, items, offsetItems, purchasedCount, unknownCount };
}

function buildDifficultyReport(result) {
  const modules = result?.modules || {};
  const equipmentAvg = Number(modules.equipment?.summary?.avgGold || 0);
  const stoneExpected = Number(result?.expectedValues?.abilityStone?.expectedStones || 0);
  const accessoryCount = Number(result?.expectedValues?.accessoryPolishing?.combination?.currentCoreEffectLineCount || 0);
  const braceletCount = Number((result?.expectedValues?.braceletT4?.currentValidEffects || []).length || 0);
  const parts = [
    { key: 'equipment', name: '장비 재련', enabled: Boolean(modules.equipment), score: equipmentAvg >= 8000000 ? 34 : equipmentAvg >= 3000000 ? 24 : equipmentAvg > 0 ? 8 : 0, kind: '재현 비용', detail: '현재 강화 단계까지 새로 올린다고 가정한 비용 부담입니다.' },
    { key: 'abilityStone', name: '어빌리티 스톤', enabled: Boolean(modules.abilityStone), score: stoneExpected >= 700 ? 30 : stoneExpected >= 150 ? 20 : stoneExpected >= 10 ? 8 : 0, kind: '결과물 희귀도', detail: '현재 활성 레벨 결과물이 나올 기대 시도 수 기준입니다.' },
    { key: 'accessory', name: '장신구 연마', enabled: Boolean(modules.accessory), score: accessoryCount >= 6 ? 12 : accessoryCount >= 3 ? 8 : accessoryCount >= 1 ? 4 : 0, kind: '유효 옵션', detail: '현재 장신구에 붙은 핵심 유효 옵션 기준입니다.' },
    { key: 'bracelet', name: '팔찌', enabled: Boolean(modules.accessory), score: braceletCount >= 5 ? 16 : braceletCount >= 3 ? 12 : braceletCount >= 1 ? 7 : 0, kind: '유효 옵션', detail: '현재 팔찌의 핵심 옵션 기준입니다.' }
  ];
  const total = Math.round(clamp(parts.reduce((sum, part) => sum + (part.enabled ? part.score : 0), 0), 0, 100));
  return { total, label: total >= 70 ? '높음' : total >= 45 ? '약간 높음' : '보통', parts, strongest: [...parts].filter((part) => part.enabled).sort((a, b) => b.score - a.score)[0] || null };
}

function buildMemoryReport(result, memoryHints = {}) {
  const modules = result?.modules || {};
  const accessoryAnalysis = buildAccessoryMemoryAnalysis(result, memoryHints, Boolean(modules.accessory));
  const rawTotal = accessoryAnalysis.score;
  const offsetTotal = accessoryAnalysis.offsetScore;
  const total = Math.round(clamp(rawTotal - offsetTotal, 0, 100));
  const parts = [
    { key: 'accessoryPolishing', name: '장신구 연마', score: Math.round(accessoryAnalysis.score), kind: accessoryAnalysis.label, detail: accessoryAnalysis.detail }
  ];
  const offsetParts = (accessoryAnalysis.offsetItems || []).map((item) => ({ key: item.key, name: '장신구 연마', score: Math.round(item.score), kind: item.kind, detail: item.detail }));
  const strongest = parts.filter((part) => part.score > 0).sort((a, b) => b.score - a.score)[0] || null;
  const evidence = Boolean((accessoryAnalysis.items || []).length || (accessoryAnalysis.offsetItems || []).length);
  let verdict = '판정 보류';
  let tone = 'stable';
  let oneLine = '직접 연마 기록이 없으면 억까 여부를 단정하지 않습니다.';
  if (evidence) {
    verdict = total >= 45 ? '억까 의심 높음' : total >= 20 ? '억까 가능성 있음' : '억까 단서 약함';
    tone = total >= 45 ? 'warning' : total >= 20 ? 'caution' : 'stable';
    oneLine = total > 0 ? '직접 연마 시도 수 기준으로 평균보다 늦은 구간이 있습니다.' : '입력한 장신구 직접 연마 기록은 평균보다 빠른 편이거나 큰 억까 단서가 아닙니다.';
  }
  return { total, offsetTotal, scoreLabel: evidence ? `${total}/100` : '보류', verdict, tone, oneLine, strongest, parts, offsetParts, evidence, accessoryAnalysis };
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
      ) : <p className="hint">{empty}</p>}
    </div>
  );
}

function DifficultyCards({ difficulty }) {
  return (
    <div className="difficulty-card-grid compact-difficulty-grid">
      {difficulty.parts.map((part) => (
        <div className={`difficulty-card ${part.enabled ? '' : 'muted-card'}`} key={part.key}>
          <div><strong>{part.name}</strong><span>{part.kind}</span></div>
          <b>{part.enabled ? `${Math.round(part.score)}점` : '제외'}</b>
          <p>{part.detail}</p>
        </div>
      ))}
    </div>
  );
}

function ExpectedValuePanel({ expectedValues }) {
  if (!expectedValues) return null;
  const stone = expectedValues.abilityStone || {};
  const comboTargets = expectedValues.accessoryPolishing?.combination?.comboTargets || {};
  const keyCombos = ['상상', '상중 이상', '중중 이상', '중하 이상', '하하 이상'];
  return (
    <div className="expected-panel evidence-panel">
      <h3>계산 근거</h3>
      <div className="evidence-card-grid">
        <section className="evidence-card">
          <div className="evidence-card-head"><strong>어빌리티 스톤</strong><span>활성 레벨 기준</span></div>
          <div className="evidence-line highlight"><span>현재 목표</span><strong>{stone.target || '-'} 활성</strong></div>
          <div className="evidence-line"><span>기대 스톤 개수</span><strong>{number(stone.expectedStones)}개</strong></div>
        </section>
        <section className="evidence-card wide-evidence-card">
          <div className="evidence-card-head"><strong>장신구 조합 기대값</strong><span>4티어 연마표 기준</span></div>
          <div className="combo-chip-grid">
            {keyCombos.map((name) => {
              const row = comboTargets[name] || {};
              return <div className="combo-chip" key={name}><span>{name}</span><strong>{probPercent(row.probability)}</strong><small>기대 {number(row.expectedAttempts)}회</small></div>;
            })}
          </div>
        </section>
      </div>
    </div>
  );
}

export default function ResultPanel({ result, memoryHints }) {
  if (!result) return null;
  const memoryReport = buildMemoryReport(result, memoryHints);
  const difficulty = buildDifficultyReport(result);
  const total = result.total;
  const rows = distributionRows(total);
  const expected = result.expectedValues || {};
  const acc = expected.accessoryPolishing?.combination || {};
  const ekkaItems = memoryReport.parts.filter((part) => part.score > 0);

  return (
    <section className={`card result-section ekka-result ${memoryReport.tone}`}>
      <div className="ekka-result-head">
        <div>
          <p className="eyebrow">억까 판정 리포트</p>
          <h2>억까 판정: {memoryReport.verdict}</h2>
          <p>{memoryReport.oneLine}</p>
        </div>
        <div className="ekka-score-ring"><span className={memoryReport.evidence ? '' : 'score-pending'}>{memoryReport.evidence ? memoryReport.total : '보류'}</span><small>{memoryReport.evidence ? '/100' : '기억 필요'}</small></div>
      </div>

      <div className="summary-grid ekka-summary-grid compact-summary-grid v38-summary-grid">
        <SummaryCard title="억까 단서" value={memoryReport.scoreLabel} sub="기억 입력 기반" />
        <SummaryCard title="상쇄 단서" value={memoryReport.offsetTotal ? `${memoryReport.offsetTotal}/100` : '없음'} sub="기대보다 잘 나온 구간" />
        <SummaryCard title="현재 결과물" value={difficulty.label} sub="재현 난이도" />
      </div>

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
        <div className="ekka-module-grid">
          <div className="ekka-module-card orange-line">
            <div className="module-title-row"><strong>장신구 연마</strong><span>4티어 표 기준</span></div>
            <p>총 파싱 효과를 4티어 상/중/하 수치표 기준으로 다시 판정합니다.</p>
            <ul>
              <li>핵심 유효 효과: {acc.currentCoreEffectLineCount ?? (acc.currentCoreEffects || acc.currentValidLikeEffects || []).length}개</li>
              <li>핵심 옵션: <EffectTagList items={(acc.currentCoreEffects || acc.currentValidLikeEffects || []).slice(0, 12)} /></li>
              <li>직접 연마 판정: {memoryReport.accessoryAnalysis?.items?.length ? <EffectTagList items={memoryReport.accessoryAnalysis.items.map((item) => `${item.name}: ${item.kind}`)} /> : '억까 기록 없음'}</li>
              <li>잘 나온 장신구: {memoryReport.accessoryAnalysis?.offsetItems?.length ? <EffectTagList items={memoryReport.accessoryAnalysis.offsetItems.map((item) => `${item.name}: ${item.kind}`)} /> : '없음'}</li>
            </ul>
          </div>
        </div>
        <div className="table-wrap percentile-table-wrap">
          <h3>선택 항목 재현 비용 분포</h3>
          <table>
            <thead><tr><th>구간</th><th>골드 비용</th><th>원화 환산</th><th>의미</th></tr></thead>
            <tbody>{rows.map((row) => <tr key={row.name}><td><strong>{row.name}</strong><br /><span className="muted-small">{row.userLabel}</span></td><td>{money(row.gold)} G</td><td>{money(row.krw)} 원</td><td>{row.meaning}</td></tr>)}</tbody>
          </table>
        </div>
        <ExpectedValuePanel expectedValues={result.expectedValues} />
      </details>
    </section>
  );
}
