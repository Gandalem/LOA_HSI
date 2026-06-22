import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  collectMaterialPrices,
  compareCharacter,
  compareCharacterCohort,
  getCharacterSummary,
  ensureMaterialPrices,
} from './api/client.js';
import CharacterPanel from './components/CharacterPanel.jsx';
import ResultPanel from './components/ResultPanel.jsx';
import BraceletSlotStructureSelector, { normalizeBraceletSlotStructure } from './components/BraceletSlotStructureSelector.jsx';
import './styles/app.css';
import './styles/public-ui.css';

function App() {
  const [characterName, setCharacterName] = useState('');
  const [character, setCharacter] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [modules, setModules] = useState({ equipment: true, abilityStone: true, accessory: true });
  const [simulationCount, setSimulationCount] = useState(100000);
  const [krwPer100Gold, setKrwPer100Gold] = useState(12);
  const [materialPrices, setMaterialPrices] = useState(null);
  const [priceLoading, setPriceLoading] = useState(false);
  const [showMarketSection, setShowMarketSection] = useState(false);
  const [showMemorySection, setShowMemorySection] = useState(false);
  const [cohortComparison, setCohortComparison] = useState(null);
  const [cohortLoading, setCohortLoading] = useState(false);
  const [memoryHints, setMemoryHints] = useState({
    pityRecords: [{ part: 'unknown', target: 'unknown' }],
    stoneAttempts: '',
    accessoryAcquisitions: {},
    braceletAcquisition: { mode: 'unknown', attempts: '', fixedOptionCount: '', randomOptionSlotCount: '' },
  });

  useEffect(() => {
    loadMaterialPrices();
  }, []);

  useEffect(() => {
    if (!character) return;
    setMemoryHints((prev) => {
      const current = Array.isArray(prev.pityRecords) ? prev.pityRecords : [];
      let changed = false;
      const next = current.map((record) => {
        const allowedTargets = targetOptionsForPart(record.part || 'unknown');
        if (record.target && record.target !== 'unknown' && !allowedTargets.includes(record.target)) {
          changed = true;
          return { ...record, target: 'unknown' };
        }
        return record;
      });
      const currentAcq = prev.accessoryAcquisitions || {};
      const nextAcq = {};
      accessoryRows(character).forEach((row) => {
        nextAcq[row.key] = currentAcq[row.key] || { mode: 'unknown', attempts: '' };
      });
      const acqChanged = JSON.stringify(currentAcq) !== JSON.stringify(nextAcq);
      const hasBracelet = (character?.accessories || []).some((item) => item.slot === '팔찌');
      const currentBracelet = prev.braceletAcquisition || { mode: 'unknown', attempts: '', fixedOptionCount: '', randomOptionSlotCount: '' };
      const nextBracelet = hasBracelet
        ? normalizeBraceletAcquisition(currentBracelet, character)
        : { mode: 'unknown', attempts: '', fixedOptionCount: '', randomOptionSlotCount: '' };
      const braceletChanged = JSON.stringify(currentBracelet) !== JSON.stringify(nextBracelet);
      if (changed || acqChanged || braceletChanged) {
        return {
          ...prev,
          pityRecords: next,
          accessoryAcquisitions: nextAcq,
          braceletAcquisition: nextBracelet,
        };
      }
      return prev;
    });
  }, [character]);

  async function loadMaterialPrices() {
    setPriceLoading(true);
    setError('');
    try {
      const data = await ensureMaterialPrices();
      setMaterialPrices(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setPriceLoading(false);
    }
  }

  async function refreshMaterialPrices() {
    setPriceLoading(true);
    setError('');
    try {
      const data = await collectMaterialPrices();
      setMaterialPrices(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setPriceLoading(false);
    }
  }

  function materialPriceSummary() {
    const items = materialPrices?.items || [];
    const valid = items.filter((x) => x.unitPriceGold !== null && x.unitPriceGold !== undefined);
    if (priceLoading && !items.length) return '재련 재료 시세를 불러오는 중입니다.';
    if (!items.length) return '기본 시세 기준으로 계산합니다.';
    if (materialPrices?.cacheUsed) return '저장된 최신 시세를 적용했습니다.';
    if (materialPrices?.message) return '현재 시세를 적용했습니다.';
    return `시세 적용 ${valid.length}/${items.length}`;
  }

  function priceBadgeText() {
    const items = materialPrices?.items || [];
    if (priceLoading && !items.length) return '시세 확인 중';
    if (items.length) return '시세 적용';
    return '기본 시세';
  }

  function materialPriceChipText(item) {
    if (!item.unitPriceGold) return `${item.materialName}: 조회 실패`;
    const unit = `${Number(item.unitPriceGold).toFixed(2)}G/개`;
    const bundle = Number(item.bundleCount || 1);
    const raw = item.rawPriceGold ? `${Number(item.rawPriceGold).toLocaleString('ko-KR')}G` : null;
    if (bundle > 1 && raw) {
      return `${item.materialName}: ${unit} · ${bundle.toLocaleString('ko-KR')}개 묶음 ${raw}`;
    }
    return `${item.materialName}: ${unit}`;
  }

  async function loadCharacter(force = false) {
    if (!characterName.trim()) {
      setError('캐릭터명을 입력하세요.');
      return;
    }
    setLoading(true);
    setError('');
    setResult(null);
    setCohortComparison(null);
    try {
      const data = await getCharacterSummary(characterName.trim(), !force);
      setCharacter(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function normalizeBraceletAcquisition(source, sourceCharacter = character) {
    const current = source && typeof source === 'object' ? source : {};
    const braceletItem = braceletRow(sourceCharacter);
    const structure = normalizeBraceletSlotStructure(current, braceletItem);
    return {
      mode: ['unknown', 'base_purchased', 'self_obtained'].includes(current.mode) ? current.mode : 'unknown',
      attempts: current.attempts === null || current.attempts === undefined ? '' : String(current.attempts),
      fixedOptionCount: structure.fixedOptionCount,
      randomOptionSlotCount: structure.randomOptionSlotCount,
    };
  }

  async function runReport() {
    if (!characterName.trim()) {
      setError('먼저 캐릭터명을 입력하세요.');
      return;
    }
    setLoading(true);
    setError('');
    setCohortComparison(null);
    setCohortLoading(false);
    try {
      const selected = Object.entries(modules).filter(([, value]) => value).map(([key]) => key);
      const sanitizedMemoryHints = {
        ...memoryHints,
        braceletAcquisition: normalizeBraceletAcquisition(memoryHints.braceletAcquisition),
      };
      const data = await compareCharacter({
        characterName: characterName.trim(),
        compareModules: selected,
        actualCostGold: {
          equipment: 0,
          abilityStone: 0,
          accessory: 0,
        },
        memoryHints: sanitizedMemoryHints,
        simulationCount: Number(simulationCount),
        krwPer100Gold: Number(krwPer100Gold),
        seed: 42,
        useCachedCharacter: true,
      });
      setCharacter(data.character);
      setResult(data);
      setMemoryHints((prev) => ({ ...prev, braceletAcquisition: sanitizedMemoryHints.braceletAcquisition }));
      const cohortPayload = buildCohortPayload(data);
      if (cohortPayload) {
        setCohortLoading(true);
        compareCharacterCohort(cohortPayload)
          .then((payload) => setCohortComparison(payload))
          .catch((e) => setCohortComparison({
            available: false,
            reason: 'request_failed',
            errorMessage: e?.message || 'cohort comparison failed',
          }))
          .finally(() => setCohortLoading(false));
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function toggleModule(name) {
    setModules((prev) => ({ ...prev, [name]: !prev[name] }));
  }

  function buildCohortPayload(data) {
    const characterSummary = data?.character || {};
    const expectedValues = data?.expectedValues || {};
    const officialAccessory = expectedValues.officialAccessoryEffects || {};
    const officialBracelet = expectedValues.officialBraceletT4 || {};
    const marketCost = expectedValues.marketCost || {};
    const marketSummary = marketCost.summary || {};
    const totalSummary = data?.total?.summary || {};
    if (!characterSummary.class_name || !characterSummary.item_avg_level) {
      return null;
    }
    return {
      className: characterSummary.class_name,
      classPresetRole: characterSummary.class_engraving_preset?.role || null,
      itemAvgLevel: Number(characterSummary.item_avg_level || 0) || null,
      equipmentAvgGold: data?.modules?.equipment?.summary?.avgGold ?? null,
      marketReproductionGold: marketSummary.marketReproductionGold ?? null,
      stoneExpectedGold: expectedValues.abilityStone?.expectedGold ?? null,
      accessoryExpectedAttempts: officialAccessory.mostDifficultItem?.expectedAttempts ?? null,
      braceletExpectedAttempts: officialBracelet.randomOptionBasis?.expectedAttempts ?? null,
      totalSimulationAvgGold: totalSummary.avgGold ?? null,
    };
  }

  function setMemory(name, value) {
    setMemoryHints((prev) => ({ ...prev, [name]: value }));
  }

  const allHoningTargetOptions = Array.from({ length: 14 }, (_, idx) => {
    const from = 11 + idx;
    return `+${from} -> +${from + 1}`;
  });

  const partSlotMap = {
    weapon: '무기',
    helmet: '투구',
    chest: '상의',
    pants: '하의',
    gloves: '장갑',
    shoulder: '어깨',
  };

  function targetToLevel(value) {
    const match = String(value || '').match(/\+\s*(\d+)/);
    return match ? Number(match[1]) : null;
  }

  function currentMaxHoningByPart(part) {
    const equipment = character?.equipment || [];
    const isWeapon = (item) => String(item.slot || '').includes('무기');
    const rows = equipment.filter((item) => {
      const slot = String(item.slot || '');
      if (part === 'weapon') return isWeapon(item);
      if (part === 'armor_unknown') return !isWeapon(item);
      if (partSlotMap[part]) return slot.includes(partSlotMap[part]);
      return true;
    });
    const levels = rows.map((item) => Number(item.honing_level || 0)).filter((value) => value > 0);
    return levels.length ? Math.max(...levels) : null;
  }

  function targetOptionsForPart(part) {
    const maxLevel = currentMaxHoningByPart(part);
    if (!maxLevel) return allHoningTargetOptions;
    return allHoningTargetOptions.filter((target) => {
      const to = targetToLevel(target);
      return to !== null && to <= maxLevel;
    });
  }

  function updatePityRecord(index, field, value) {
    setMemoryHints((prev) => {
      const current = Array.isArray(prev.pityRecords) ? prev.pityRecords : [];
      const next = current.map((record, i) => {
        if (i !== index) return record;
        if (field === 'part') {
          const allowedTargets = targetOptionsForPart(value);
          const nextTarget = allowedTargets.includes(record.target) ? record.target : 'unknown';
          return { ...record, part: value, target: nextTarget };
        }
        return { ...record, [field]: value };
      });
      return { ...prev, pityRecords: next.length ? next : [{ part: 'unknown', target: 'unknown' }] };
    });
  }

  function addPityRecord() {
    setMemoryHints((prev) => ({
      ...prev,
      pityRecords: [...(Array.isArray(prev.pityRecords) ? prev.pityRecords : []), { part: 'unknown', target: 'unknown' }],
    }));
  }

  function removePityRecord(index) {
    setMemoryHints((prev) => {
      const current = Array.isArray(prev.pityRecords) ? prev.pityRecords : [];
      const next = current.filter((_, i) => i !== index);
      return { ...prev, pityRecords: next.length ? next : [{ part: 'unknown', target: 'unknown' }] };
    });
  }

  function accessoryRows(sourceCharacter = character) {
    const accessories = sourceCharacter?.accessories || [];
    return accessories
      .map((item, index) => ({ ...item, index, key: `${item.slot || '장신구'}-${index}` }))
      .filter((item) => item.slot !== '팔찌');
  }

  function braceletRow(sourceCharacter = character) {
    const accessories = sourceCharacter?.accessories || [];
    const item = accessories.find((row) => row.slot === '팔찌');
    return item ? { ...item, key: 'bracelet' } : null;
  }

  function updateBraceletAcquisition(field, value) {
    setMemoryHints((prev) => {
      const before = prev.braceletAcquisition || { mode: 'unknown', attempts: '', fixedOptionCount: '', randomOptionSlotCount: '' };
      const next = field === 'mode' && !['base_purchased', 'self_obtained'].includes(value)
        ? { ...before, [field]: value, attempts: '', fixedOptionCount: '', randomOptionSlotCount: '' }
        : { ...before, [field]: value };
      return { ...prev, braceletAcquisition: normalizeBraceletAcquisition(next) };
    });
  }

  function updateBraceletStructure(value) {
    setMemoryHints((prev) => {
      const before = prev.braceletAcquisition || { mode: 'unknown', attempts: '', fixedOptionCount: '', randomOptionSlotCount: '' };
      const [fixedOptionCount = '', randomOptionSlotCount = ''] = value ? value.split(':') : ['', ''];
      return {
        ...prev,
        braceletAcquisition: normalizeBraceletAcquisition({ ...before, fixedOptionCount, randomOptionSlotCount }),
      };
    });
  }

  function updateAccessoryAcquisition(key, field, value) {
    setMemoryHints((prev) => {
      const current = prev.accessoryAcquisitions || {};
      const before = current[key] || { mode: 'unknown', attempts: '' };
      const nextValue = field === 'mode' && value !== 'polished'
        ? { ...before, [field]: value, attempts: '' }
        : { ...before, [field]: value };
      return { ...prev, accessoryAcquisitions: { ...current, [key]: nextValue } };
    });
  }

  const memoryCount = [
    memoryHints.stoneAttempts !== '' && memoryHints.stoneAttempts !== undefined ? 1 : 0,
    Array.isArray(memoryHints.pityRecords)
      ? memoryHints.pityRecords.filter((row) => row?.part !== 'unknown' || row?.target !== 'unknown').length
      : 0,
    Object.values(memoryHints.accessoryAcquisitions || {}).filter((row) => row?.mode && row.mode !== 'unknown').length,
    memoryHints.braceletAcquisition?.mode && memoryHints.braceletAcquisition.mode !== 'unknown' ? 1 : 0,
  ].reduce((sum, value) => sum + value, 0);

  return (
    <main className="container">
      <header className="hero ekka-hero">
        <div className="hero-copy-block">
          <p className="eyebrow">LOA-HSI v60.2</p>
          <h1>로스트아크 성장 비용을 실제 데이터와 확률표로 다시 계산합니다</h1>
          <p className="hero-copy">
            현재 캐릭터 상태를 불러와 장비 재련, 어빌리티 스톤, 장신구, 팔찌 비용을 재현하고
            시뮬레이션 분포와 수집된 유사 유저 표본을 함께 비교하는 분석 화면입니다.
          </p>
        </div>
        <div className="hero-side-panel">
          <span className="hero-side-kicker">Current Focus</span>
          <strong>가상 시뮬레이션 + 실측 코호트 비교</strong>
          <p>운이 좋았는지 나빴는지를 “내 캐릭터 재현 분포”와 “비슷한 유저 위치”로 분리해서 보여줍니다.</p>
        </div>
      </header>

      <section className="card input-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Step 1</p>
            <h2>캐릭터 불러오기</h2>
            <p className="section-copy">공식 API 기준 현재 세팅을 조회합니다.</p>
          </div>
        </div>
        <div className="row">
          <input value={characterName} onChange={(e) => setCharacterName(e.target.value)} placeholder="캐릭터명을 입력하세요" />
          <button onClick={() => loadCharacter(false)} disabled={loading}>조회</button>
          <button className="ghost" onClick={() => loadCharacter(true)} disabled={loading}>강제 새로고침</button>
        </div>
      </section>

      <CharacterPanel character={character} />

      <section className="card input-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Step 2</p>
            <h2>분석 기준 설정</h2>
            <p className="section-copy">시뮬레이션 모듈, 기억 기반 보조 정보, 재련 재료 시세를 정리합니다.</p>
          </div>
        </div>

        <div className={`collapsible-block ${showMarketSection ? 'open' : 'closed'}`}>
          <button
            type="button"
            className="collapsible-toggle"
            onClick={() => setShowMarketSection((value) => !value)}
          >
            <span className="collapsible-copy">
              <strong>시세 · 재료</strong>
              <small>{materialPriceSummary()}</small>
            </span>
            <span className="collapsible-state">
              {priceBadgeText()}
              <b>{showMarketSection ? '접기' : '펼치기'}</b>
            </span>
          </button>

          {showMarketSection ? (
            <>
        <div className="price-panel">
          <div>
            <strong>재련 재료 시세</strong>
            <p className="hint">{materialPriceSummary()}</p>
          </div>
          <div className="price-actions">
            <span className="auto-loaded-badge">{priceBadgeText()}</span>
            <button className="ghost" onClick={refreshMaterialPrices} disabled={loading || priceLoading}>
              {priceLoading ? '갱신 중..' : '시세 강제 갱신'}
            </button>
          </div>
        </div>

        {materialPrices?.items?.length > 0 ? (
          <div className="material-chip-row">
            {materialPrices.items.map((item) => (
              <span
                className={item.unitPriceGold ? 'material-chip' : 'material-chip muted-chip'}
                key={item.materialKey}
                title={item.note || ''}
              >
                {materialPriceChipText(item)}
              </span>
            ))}
          </div>
        ) : null}
            </>
          ) : null}
        </div>

        <div className="module-toggle-grid">
          <label className={`module-toggle ${modules.equipment ? 'checked' : ''}`}>
            <input type="checkbox" checked={modules.equipment} onChange={() => toggleModule('equipment')} />
            <span className="module-toggle-icon">E</span>
            <span><strong>장비 재련</strong><small>현재 장비 단계 재현 비용</small></span>
          </label>
          <label className={`module-toggle ${modules.abilityStone ? 'checked' : ''}`}>
            <input type="checkbox" checked={modules.abilityStone} onChange={() => toggleModule('abilityStone')} />
            <span className="module-toggle-icon">S</span>
            <span><strong>어빌리티 스톤</strong><small>목표 활성 결과물 기대 비용</small></span>
          </label>
          <label className={`module-toggle ${modules.accessory ? 'checked' : ''}`}>
            <input type="checkbox" checked={modules.accessory} onChange={() => toggleModule('accessory')} />
            <span className="module-toggle-icon">A</span>
            <span><strong>장신구 · 팔찌</strong><small>핵심 옵션과 고정 효과 기준 난도</small></span>
          </label>
        </div>

        <div className={`collapsible-block ${showMemorySection ? 'open' : 'closed'}`}>
          <button
            type="button"
            className="collapsible-toggle memory-toggle"
            onClick={() => setShowMemorySection((value) => !value)}
          >
            <span className="collapsible-copy">
              <strong>기억 입력</strong>
              <small>천장, 스톤 시도, 장신구/팔찌 직접 시도 수 입력</small>
            </span>
            <span className="collapsible-state">
              {memoryCount}건
              <b>{showMemorySection ? '접기' : '펼치기'}</b>
            </span>
          </button>

          {showMemorySection ? (
            <div className="memory-panel">
          <div>
            <h3>기억 기반 보조 입력</h3>
            <p className="hint">기억나는 실패 구간이나 직접 시도 횟수가 있으면 입력하고, 없으면 비워둬도 됩니다.</p>
          </div>

          <div className={`pity-record-panel ${modules.equipment ? '' : 'disabled-panel'}`}>
            <div className="pity-record-header">
              <strong>재련 천장 기록</strong>
              <button type="button" className="ghost tiny-button" onClick={addPityRecord} disabled={!modules.equipment}>
                기록 추가
              </button>
            </div>
            <p className="hint">기억나는 천장 구간만 추가해도 됩니다.</p>
            <div className="pity-record-list">
              {(memoryHints.pityRecords || []).map((record, index) => (
                <div className="pity-record-row" key={index}>
                  <select disabled={!modules.equipment} value={record.part || 'unknown'} onChange={(e) => updatePityRecord(index, 'part', e.target.value)}>
                    <option value="unknown">부위 미지정</option>
                    <option value="weapon">무기</option>
                    <option value="helmet">투구</option>
                    <option value="chest">상의</option>
                    <option value="pants">하의</option>
                    <option value="gloves">장갑</option>
                    <option value="shoulder">어깨</option>
                    <option value="armor_unknown">방어구 중 하나</option>
                  </select>
                  <select disabled={!modules.equipment} value={targetOptionsForPart(record.part || 'unknown').includes(record.target) ? record.target : 'unknown'} onChange={(e) => updatePityRecord(index, 'target', e.target.value)}>
                    <option value="unknown">강화 구간 미지정</option>
                    {targetOptionsForPart(record.part || 'unknown').map((target) => (
                      <option value={target} key={target}>{target}</option>
                    ))}
                  </select>
                  <button type="button" className="ghost tiny-button" onClick={() => removePityRecord(index)} disabled={!modules.equipment}>
                    삭제
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="form-grid memory-grid numeric-memory-grid v36-memory-grid">
            <label>
              스톤 총 시도 수
              <span>
                <input type="number" min="0" step="1" value={memoryHints.stoneAttempts} onChange={(e) => setMemory('stoneAttempts', e.target.value)} placeholder="예: 120" />
                회
              </span>
            </label>
            <label>
              가상 성장 샘플 수
              <span>
                <select value={simulationCount} onChange={(e) => setSimulationCount(e.target.value)}>
                  <option value="10000">1만 회 시뮬레이션</option>
                  <option value="100000">10만 회 시뮬레이션</option>
                  <option value="300000">30만 회 시뮬레이션</option>
                </select>
              </span>
            </label>
            <label>
              100골드 원화 환산
              <span>
                <input type="number" step="1" value={krwPer100Gold} onChange={(e) => setKrwPer100Gold(e.target.value)} />
                원
              </span>
            </label>
          </div>

          <div className={`accessory-acquisition-panel ${modules.accessory ? '' : 'disabled-panel'}`}>
            <div>
              <h3>장신구 획득 방식</h3>
              <p className="hint">직접 연마했던 장신구만 시도 횟수를 입력하면 됩니다.</p>
            </div>
            <div className="accessory-acquisition-list">
              {accessoryRows().map((item) => {
                const current = memoryHints.accessoryAcquisitions?.[item.key] || { mode: 'unknown', attempts: '' };
                return (
                  <div className="accessory-acquisition-row" key={item.key}>
                    <div className="accessory-acquisition-name">
                      <strong>{item.slot}</strong>
                      <small>{item.name || '장신구'} · 품질 {item.quality ?? '-'}</small>
                    </div>
                    <select disabled={!modules.accessory} value={current.mode || 'unknown'} onChange={(e) => updateAccessoryAcquisition(item.key, 'mode', e.target.value)}>
                      <option value="unknown">기억 안 남</option>
                      <option value="purchased">구매함</option>
                      <option value="polished">직접 연마함</option>
                    </select>
                    {current.mode === 'polished' ? (
                      <label className="inline-attempt-input">
                        <input type="number" min="0" step="1" disabled={!modules.accessory} value={current.attempts || ''} onChange={(e) => updateAccessoryAcquisition(item.key, 'attempts', e.target.value)} placeholder="시도 수" />
                        <span>회</span>
                      </label>
                    ) : null}
                  </div>
                );
              })}
              {!accessoryRows().length ? <p className="hint">조회된 장신구가 없습니다.</p> : null}
            </div>
          </div>

          <div className={`accessory-acquisition-panel ${modules.accessory ? '' : 'disabled-panel'}`}>
            <div>
              <h3>팔찌 랜덤 옵션 시도</h3>
              <p className="hint">직접 돌린 팔찌만 시도 횟수를 입력하면 됩니다.</p>
            </div>
            {braceletRow() ? (
              <>
                <div className="accessory-acquisition-row">
                  <div className="accessory-acquisition-name">
                    <strong>팔찌</strong>
                    <small>{braceletRow()?.name || '팔찌'} · {braceletRow()?.grade || '-'}</small>
                  </div>
                  <select disabled={!modules.accessory} value={memoryHints.braceletAcquisition?.mode || 'unknown'} onChange={(e) => updateBraceletAcquisition('mode', e.target.value)}>
                    <option value="unknown">기억 안 남</option>
                    <option value="base_purchased">베이스 팔찌 구매 후 직접 돌림</option>
                    <option value="self_obtained">직접 획득한 팔찌를 돌림</option>
                  </select>
                  {['base_purchased', 'self_obtained'].includes(memoryHints.braceletAcquisition?.mode) ? (
                    <label className="inline-attempt-input">
                      <input type="number" min="0" step="1" disabled={!modules.accessory} value={memoryHints.braceletAcquisition?.attempts || ''} onChange={(e) => updateBraceletAcquisition('attempts', e.target.value)} placeholder="시도 수" />
                      <span>회</span>
                    </label>
                  ) : null}
                </div>
                <BraceletSlotStructureSelector
                  item={braceletRow()}
                  disabled={!modules.accessory}
                  value={memoryHints.braceletAcquisition || {}}
                  onChange={updateBraceletStructure}
                />
              </>
            ) : (
              <p className="hint">조회된 팔찌가 없습니다.</p>
            )}
          </div>
            </div>
          ) : null}
        </div>

        <button className="primary" onClick={runReport} disabled={loading}>
          {loading ? '분석 중..' : '비용 분석 실행'}
        </button>
      </section>

      {error ? <div className="error-box">{error}</div> : null}
      <ResultPanel
        result={result}
        memoryHints={memoryHints}
        cohortComparison={cohortComparison}
        cohortLoading={cohortLoading}
      />
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
