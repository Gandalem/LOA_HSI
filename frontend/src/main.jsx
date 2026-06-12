import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { collectMaterialPrices, compareCharacter, getCharacterSummary, ensureMaterialPrices, getHoningTable, getMaterialPriceAutoStatus } from './api/client.js';
import CharacterPanel from './components/CharacterPanel.jsx';
import ResultPanel from './components/ResultPanel.jsx';
import HoningTablePanel from './components/HoningTablePanel.jsx';
import MemoryPersistencePanel from './components/MemoryPersistencePanel.jsx';
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
  const [honingTable, setHoningTable] = useState(null);
  const [honingTableLoading, setHoningTableLoading] = useState(false);
  const [autoPriceStatus, setAutoPriceStatus] = useState(null);
  const [priceAutoLoaded, setPriceAutoLoaded] = useState(false);
  const [saveMemoryRequest, setSaveMemoryRequest] = useState(null);
  const [memoryHints, setMemoryHints] = useState({
    pityRecords: [{ part: 'unknown', target: 'unknown' }],
    stoneAttempts: '',
    accessoryAcquisitions: {},
    braceletAcquisition: { mode: 'unknown', attempts: '', fixedOptionCount: '', randomOptionSlotCount: '' }
  });

  useEffect(() => {
    loadMaterialPrices();
    getMaterialPriceAutoStatus().then(setAutoPriceStatus).catch(() => null);
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
      if (changed || acqChanged || braceletChanged) return { ...prev, pityRecords: next, accessoryAcquisitions: nextAcq, braceletAcquisition: nextBracelet };
      return prev;
    });
  }, [character]);

  function valueOrEmpty(value) {
    return value === null || value === undefined ? '' : String(value);
  }

  function normalizePityRecords(records) {
    const current = Array.isArray(records) && records.length
      ? records
      : [{ part: 'unknown', target: 'unknown' }];

    return current.map((record) => {
      const part = record?.part || 'unknown';
      const target = record?.target || 'unknown';
      const allowedTargets = targetOptionsForPart(part);

      return {
        part,
        target: target === 'unknown' || allowedTargets.includes(target) ? target : 'unknown'
      };
    });
  }

  function normalizeAccessoryAcquisitions(acquisitions, sourceCharacter) {
    const source = acquisitions && typeof acquisitions === 'object' ? acquisitions : {};
    const rows = accessoryRows(sourceCharacter || character);
    const normalizeEntry = (entry) => ({
      mode: ['unknown', 'purchased', 'polished'].includes(entry?.mode) ? entry.mode : 'unknown',
      attempts: valueOrEmpty(entry?.attempts)
    });

    if (!rows.length) {
      return Object.fromEntries(
        Object.entries(source).map(([key, entry]) => [key, normalizeEntry(entry)])
      );
    }

    const next = {};
    rows.forEach((row) => {
      next[row.key] = normalizeEntry(source[row.key]);
    });
    return next;
  }

  function applyLoadedMemoryHints(loaded, sourceCharacter = character) {
    if (!loaded || typeof loaded !== 'object') return;
    setMemoryHints((prev) => ({
      ...prev,
      ...loaded,
      pityRecords: normalizePityRecords(loaded.pityRecords),
      stoneAttempts: valueOrEmpty(loaded.stoneAttempts),
      accessoryAcquisitions: normalizeAccessoryAcquisitions(loaded.accessoryAcquisitions, sourceCharacter),
      braceletAcquisition: normalizeBraceletAcquisition(loaded.braceletAcquisition, sourceCharacter)
    }));
  }

  async function loadHoningTable() {
    setHoningTableLoading(true);
    setError('');
    try {
      const data = await getHoningTable();
      setHoningTable(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setHoningTableLoading(false);
    }
  }

  async function loadMaterialPrices() {
    setPriceLoading(true);
    setError('');
    try {
      // v35: 첫 접속 시 DB 확인 버튼을 누르지 않아도 서버가 최신/저장 시세를 보장합니다.
      // DB가 비어 있거나 TTL이 지난 경우에만 백엔드에서 수집하고, 유효한 DB가 있으면 API를 다시 호출하지 않습니다.
      const data = await ensureMaterialPrices();
      setMaterialPrices(data);
      setPriceAutoLoaded(true);
      getMaterialPriceAutoStatus().then(setAutoPriceStatus).catch(() => null);
    } catch (e) {
      setError(e.message);
      setPriceAutoLoaded(false);
    } finally {
      setPriceLoading(false);
      loadHoningTable();
    }
  }

  async function refreshMaterialPrices() {
    setPriceLoading(true);
    setError('');
    try {
      const data = await collectMaterialPrices();
      setMaterialPrices(data);
      getMaterialPriceAutoStatus().then(setAutoPriceStatus).catch(() => null);
    } catch (e) {
      setError(e.message);
    } finally {
      setPriceLoading(false);
      loadHoningTable();
    }
  }

  function materialPriceSummary() {
    const items = materialPrices?.items || [];
    const valid = items.filter((x) => x.unitPriceGold !== null && x.unitPriceGold !== undefined);
    if (priceLoading && !items.length) return '재련 재료 시세를 불러오는 중입니다.';
    if (!items.length) return '기본 시세로 계산합니다.';
    if (materialPrices?.cacheUsed) return '저장된 시세를 적용했습니다.';
    if (materialPrices?.message) return '시세를 적용했습니다.';
    return `시세 적용 ${valid.length}/${items.length}`;
  }

  function priceBadgeText() {
    const items = materialPrices?.items || [];
    if (priceLoading && !items.length) return '시세 확인 중';
    if (items.length) return '시세 적용';
    return '기본 시세';
  }

  function materialPriceChipText(item) {
    if (!item.unitPriceGold) return `${item.materialName}: 실패`;
    const unit = `${Number(item.unitPriceGold).toFixed(2)}G/개`;
    const bundle = Number(item.bundleCount || 1);
    const raw = item.rawPriceGold ? `${Number(item.rawPriceGold).toLocaleString('ko-KR')}G` : null;
    if (bundle > 1 && raw) return `${item.materialName}: ${unit} · ${bundle.toLocaleString('ko-KR')}개 묶음 ${raw}`;
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
      randomOptionSlotCount: structure.randomOptionSlotCount
    };
  }

  async function runReport() {
    if (!characterName.trim()) {
      setError('먼저 캐릭터명을 입력하세요.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const selected = Object.entries(modules).filter(([, v]) => v).map(([k]) => k);
      const sanitizedMemoryHints = {
        ...memoryHints,
        braceletAcquisition: normalizeBraceletAcquisition(memoryHints.braceletAcquisition)
      };
      const data = await compareCharacter({
        characterName: characterName.trim(),
        compareModules: selected,
        // v29: 기본 모드는 실제 사용 골드를 요구하지 않습니다.
        // 캐릭터 현재 결과물의 재현 비용/희귀도/증언 기반 보조 판정으로 억까 가능성을 계산합니다.
        actualCostGold: {
          equipment: 0,
          abilityStone: 0,
          accessory: 0
        },
        memoryHints: sanitizedMemoryHints,
        simulationCount: Number(simulationCount),
        krwPer100Gold: Number(krwPer100Gold),
        seed: 42,
        useCachedCharacter: true
      });
      setCharacter(data.character);
      setResult(data);
      setMemoryHints((prev) => ({ ...prev, braceletAcquisition: sanitizedMemoryHints.braceletAcquisition }));
      setSaveMemoryRequest({ id: Date.now(), character: data.character, memoryHints: sanitizedMemoryHints });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function toggleModule(name) {
    setModules((prev) => ({ ...prev, [name]: !prev[name] }));
  }

  function setMemory(name, value) {
    setMemoryHints((prev) => ({ ...prev, [name]: value }));
  }

  const allHoningTargetOptions = Array.from({ length: 14 }, (_, idx) => {
    const from = 11 + idx;
    return `+${from} → +${from + 1}`;
  });

  const partSlotMap = {
    weapon: '무기',
    helmet: '투구',
    chest: '상의',
    pants: '하의',
    gloves: '장갑',
    shoulder: '어깨'
  };

  function targetToLevel(value) {
    const match = String(value || '').match(/→\s*\+(\d+)/);
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
    const levels = rows.map((item) => Number(item.honing_level || 0)).filter((n) => n > 0);
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
      pityRecords: [...(Array.isArray(prev.pityRecords) ? prev.pityRecords : []), { part: 'unknown', target: 'unknown' }]
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
        braceletAcquisition: normalizeBraceletAcquisition({ ...before, fixedOptionCount, randomOptionSlotCount })
      };
    });
  }

  function updateAccessoryAcquisition(key, field, value) {
    setMemoryHints((prev) => {
      const current = prev.accessoryAcquisitions || {};
      const before = current[key] || { mode: 'unknown', attempts: '' };
      const nextValue = field === 'mode' && value !== 'polished' ? { ...before, [field]: value, attempts: '' } : { ...before, [field]: value };
      return { ...prev, accessoryAcquisitions: { ...current, [key]: nextValue } };
    });
  }

  return (
    <main className="container">
      <header className="hero ekka-hero">
        <div>
          <p className="eyebrow">LOA-HSI v60.2</p>
          <h1>내가 접을 만했나? 로스트아크 성장 억까 리포트</h1>
          <p className="hero-copy">핵심 결론만 먼저 보여주고, 자세한 계산은 필요할 때 펼쳐보는 리포트입니다.</p>
        </div>
      </header>

      <section className="card input-card">
        <h2>1. 캐릭터 검색</h2>
        <div className="row">
          <input value={characterName} onChange={(e) => setCharacterName(e.target.value)} placeholder="캐릭터명 입력" />
          <button onClick={() => loadCharacter(false)} disabled={loading}>검색</button>
          <button className="ghost" onClick={() => loadCharacter(true)} disabled={loading}>새로고침</button>
        </div>
      </section>

      <CharacterPanel character={character} />

      <section className="card input-card">
        <h2>2. 억까 판정 설정</h2>
        <div className="price-panel">
          <div>
            <strong>재련 재료 시세</strong>
            <p className="hint">{materialPriceSummary()}</p>
          </div>
          <div className="price-actions">
            <span className="auto-loaded-badge">{priceBadgeText()}</span>
            <button className="ghost" onClick={refreshMaterialPrices} disabled={loading || priceLoading}>{priceLoading ? '갱신 중...' : '강제 새로고침'}</button>
          </div>
        </div>
        {autoPriceStatus && (
          <p className="hint auto-price-status">자동 시세 수집: {autoPriceStatus.ok === false ? `실패 · ${autoPriceStatus.error || ''}` : `${autoPriceStatus.reason || 'startup'} · ${autoPriceStatus.message || '상태 확인됨'}`}</p>
        )}
        {materialPrices?.items?.length > 0 && (
          <div className="material-chip-row">
            {materialPrices.items.map((item) => (
              <span className={item.unitPriceGold ? 'material-chip' : 'material-chip muted-chip'} key={item.materialKey} title={item.note || ''}>
                {materialPriceChipText(item)}
              </span>
            ))}
          </div>
        )}
        <HoningTablePanel data={honingTable} loading={honingTableLoading} onReload={loadHoningTable} character={character} />

        <div className="module-toggle-grid">
          <label className={`module-toggle ${modules.equipment ? 'checked' : ''}`}>
            <input type="checkbox" checked={modules.equipment} onChange={() => toggleModule('equipment')} />
            <span className="module-toggle-icon">⚔</span>
            <span><strong>장비 재련</strong><small>현재 장비 단계 재현 비용</small></span>
          </label>
          <label className={`module-toggle ${modules.abilityStone ? 'checked' : ''}`}>
            <input type="checkbox" checked={modules.abilityStone} onChange={() => toggleModule('abilityStone')} />
            <span className="module-toggle-icon">◆</span>
            <span><strong>어빌리티 스톤</strong><small>활성 레벨 결과물 희귀도</small></span>
          </label>
          <label className={`module-toggle ${modules.accessory ? 'checked' : ''}`}>
            <input type="checkbox" checked={modules.accessory} onChange={() => toggleModule('accessory')} />
            <span className="module-toggle-icon">✦</span>
            <span><strong>장신구 / 팔찌</strong><small>효과·유효옵션 희귀도</small></span>
          </label>
        </div>

        <div className="memory-panel">
          <div>
            <h3>기억 기반 보조 판정</h3>
            <p className="hint">기억나는 실패 구간이 있으면 입력하세요. 없으면 비워둬도 됩니다.</p>
          </div>

          <MemoryPersistencePanel
            character={character}
            saveRequest={saveMemoryRequest}
            onLoadMemoryHints={applyLoadedMemoryHints}
          />

          <div className={`pity-record-panel ${modules.equipment ? '' : 'disabled-panel'}`}>
            <div className="pity-record-header">
              <strong>장기백 기록</strong>
              <button type="button" className="ghost tiny-button" onClick={addPityRecord} disabled={!modules.equipment}>기록 추가</button>
            </div>
            <p className="hint">기억나는 장기백 구간만 추가하세요.</p>
            <div className="pity-record-list">
              {(memoryHints.pityRecords || []).map((record, index) => (
                <div className="pity-record-row" key={index}>
                  <select disabled={!modules.equipment} value={record.part || 'unknown'} onChange={(e) => updatePityRecord(index, 'part', e.target.value)}>
                    <option value="unknown">부위 모름</option>
                    <option value="weapon">무기</option>
                    <option value="helmet">투구</option>
                    <option value="chest">상의</option>
                    <option value="pants">하의</option>
                    <option value="gloves">장갑</option>
                    <option value="shoulder">어깨</option>
                    <option value="armor_unknown">방어구 중 하나</option>
                  </select>
                  <select disabled={!modules.equipment} value={targetOptionsForPart(record.part || 'unknown').includes(record.target) ? record.target : 'unknown'} onChange={(e) => updatePityRecord(index, 'target', e.target.value)}>
                    <option value="unknown">강화 구간 모름</option>
                    {targetOptionsForPart(record.part || 'unknown').map((target) => (
                      <option value={target} key={target}>{target}</option>
                    ))}
                  </select>
                  <button type="button" className="ghost tiny-button" onClick={() => removePityRecord(index)} disabled={!modules.equipment}>삭제</button>
                </div>
              ))}
            </div>
          </div>

          <div className="form-grid memory-grid numeric-memory-grid v36-memory-grid">
            <label>스톤 시도 개수<span><input type="number" min="0" step="1" value={memoryHints.stoneAttempts} onChange={(e) => setMemory('stoneAttempts', e.target.value)} placeholder="예: 120" /> 개</span></label>
            <label>가상 성장 샘플 수<span><select value={simulationCount} onChange={(e) => setSimulationCount(e.target.value)}><option value="10000">1만 회 가상 성장</option><option value="100000">10만 회 가상 성장</option><option value="300000">30만 회 가상 성장</option></select></span></label>
            <label>100골드 원화 환산<span><input type="number" step="1" value={krwPer100Gold} onChange={(e) => setKrwPer100Gold(e.target.value)} /> 원</span></label>
          </div>

          <div className={`accessory-acquisition-panel ${modules.accessory ? '' : 'disabled-panel'}`}>
            <div>
              <h3>장신구 획득 방식</h3>
              <p className="hint">직접 옵션을 시도한 장신구만 입력하세요.</p>
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
                      <option value="polished">직접 옵션 시도함</option>
                    </select>
                    {current.mode === 'polished' && (
                      <label className="inline-attempt-input">
                        <input type="number" min="0" step="1" disabled={!modules.accessory} value={current.attempts || ''} onChange={(e) => updateAccessoryAcquisition(item.key, 'attempts', e.target.value)} placeholder="시도 수" />
                        <span>회</span>
                      </label>
                    )}
                  </div>
                );
              })}
              {!accessoryRows().length && <p className="hint">조회된 장신구가 없습니다.</p>}
            </div>
          </div>

          <div className={`accessory-acquisition-panel ${modules.accessory ? '' : 'disabled-panel'}`}>
            <div>
              <h3>팔찌 랜덤 옵션 시도</h3>
              <p className="hint">직접 돌린 팔찌만 시도 수를 입력하세요.</p>
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
                  {['base_purchased', 'self_obtained'].includes(memoryHints.braceletAcquisition?.mode) && (
                    <label className="inline-attempt-input">
                      <input type="number" min="0" step="1" disabled={!modules.accessory} value={memoryHints.braceletAcquisition?.attempts || ''} onChange={(e) => updateBraceletAcquisition('attempts', e.target.value)} placeholder="시도 수" />
                      <span>개</span>
                    </label>
                  )}
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

        <button className="primary" onClick={runReport} disabled={loading}>{loading ? '분석 중...' : '억까 리포트 생성'}</button>
      </section>

      {error && <div className="error-box">{error}</div>}
      <ResultPanel result={result} memoryHints={memoryHints} />
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
