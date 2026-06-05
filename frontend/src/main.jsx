import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { collectMaterialPrices, compareCharacter, getCharacterSummary, ensureMaterialPrices, getHoningTable, getMaterialPriceAutoStatus } from './api/client.js';
import CharacterPanel from './components/CharacterPanel.jsx';
import ResultPanel from './components/ResultPanel.jsx';
import HoningTablePanel from './components/HoningTablePanel.jsx';
import './styles/app.css';

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
  const [memoryHints, setMemoryHints] = useState({
    pityRecords: [{ part: 'unknown', target: 'unknown' }],
    stoneAttempts: ''
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
      return changed ? { ...prev, pityRecords: next } : prev;
    });
  }, [character]);

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
    if (priceLoading && !items.length) return '재련 재료 시세를 자동으로 불러오는 중입니다.';
    if (!items.length) {
      if (autoPriceStatus?.ok === false) return `시세 자동 수집 실패 · 기본값으로 계산 중 (${autoPriceStatus.error || '원인 미상'})`;
      return '저장된 시세가 아직 없습니다. 기본값으로 먼저 계산하고, 서버가 자동 수집을 시도합니다.';
    }
    if (materialPrices?.cacheUsed) return materialPrices.message || '저장된 DB 시세를 재사용했습니다.';
    if (materialPrices?.message) return materialPrices.message;
    const last = items.map((x) => x.collectedAt).filter(Boolean).sort().at(-1);
    return `${valid.length}/${items.length}개 재료 가격 적용${last ? ` · 기준 ${last}` : ''}`;
  }

  function priceBadgeText() {
    const items = materialPrices?.items || [];
    if (priceLoading && !items.length) return '자동 로드 중';
    if (items.length) return materialPrices?.cacheUsed ? 'DB 시세 적용' : '시세 적용됨';
    if (autoPriceStatus?.ok === false || priceAutoLoaded === false) return '기본값 계산 중';
    return '자동 로드 대기';
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

  async function runReport() {
    if (!characterName.trim()) {
      setError('먼저 캐릭터명을 입력하세요.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const selected = Object.entries(modules).filter(([, v]) => v).map(([k]) => k);
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
        simulationCount: Number(simulationCount),
        krwPer100Gold: Number(krwPer100Gold),
        seed: 42,
        useCachedCharacter: true
      });
      setCharacter(data.character);
      setResult(data);
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

  return (
    <main className="container">
      <header className="hero ekka-hero">
        <div>
          <p className="eyebrow">LOA-HSI v41</p>
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
            <span><strong>장신구 / 팔찌</strong><small>연마·유효옵션 희귀도</small></span>
          </label>
        </div>

        <div className="memory-panel">
          <div>
            <h3>기억 기반 보조 판정</h3>
            <p className="hint">실제 사용 골드는 묻지 않습니다. 현재 캐릭터의 장비 성장 중 기억나는 장기백 구간만 입력합니다. 구간이 애매하면 “모름”으로 두면 참고 단서로만 봅니다.</p>
          </div>

          <div className={`pity-record-panel ${modules.equipment ? '' : 'disabled-panel'}`}>
            <div className="pity-record-header">
              <strong>장기백 기록</strong>
              <button type="button" className="ghost tiny-button" onClick={addPityRecord} disabled={!modules.equipment}>기록 추가</button>
            </div>
            <p className="hint">예: 무기 · +17 → +18. 같은 장기백을 여러 번 겪었다면 기록을 여러 줄 추가하세요. 현재 캐릭터가 도달한 강화 구간만 선택지에 표시합니다.</p>
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
            <label>시뮬레이션 수<span><select value={simulationCount} onChange={(e) => setSimulationCount(e.target.value)}><option value="10000">1만 명</option><option value="100000">10만 명</option><option value="300000">30만 명</option></select></span></label>
            <label>100골드 원화 환산<span><input type="number" step="1" value={krwPer100Gold} onChange={(e) => setKrwPer100Gold(e.target.value)} /> 원</span></label>
          </div>
        </div>

        <button className="primary" onClick={runReport} disabled={loading}>{loading ? '분석 중...' : '억까 리포트 생성'}</button>
      </section>

      {error && <div className="error-box">{error}</div>}
      <ResultPanel result={result} memoryHints={memoryHints} />

        <details className="notice-panel footer-notice-panel">
          <summary>공지사항 / 업데이트 내역</summary>
          <div className="notice-list version-history-list">
            <p><strong>v41</strong> 장기백 입력에서 횟수와 시점 선택을 제거하고, 기록을 부위+강화구간 단위로 단순화했습니다. 강화 구간은 +11부터 현재 강화 단계까지 표시합니다.</p>
            <p><strong>v40</strong> 에기르 장비와 운명의 전율 장비의 재련표 라벨을 분리하고, 캐릭터 장비 이름 기준으로 재련표 구간을 자동 선택하도록 수정했습니다. 백엔드 준비 전 API 502가 보이는 문제를 줄이기 위해 재시도와 헬스체크를 추가했습니다.</p>
            <p><strong>v39</strong> 장기백 횟수 입력을 0~20회로 제한하고, 현재 캐릭터가 도달한 강화 구간만 선택지에 표시하도록 정리했습니다. 세부 분석은 결과 생성 시 기본 접힘 상태로 유지합니다.</p>
            <p><strong>v38</strong> 결과 화면을 더 압축하고, 현재 캐릭터와 맞지 않는 장기백 기록은 강한 점수로 반영하지 않도록 보정했습니다. 공지사항을 하단으로 이동했습니다.</p>
            <p><strong>v37</strong> 결과 화면을 간소화하고, 세부 계산은 접기 영역으로 이동했습니다. 체감 구간 선택을 제거하고, 선택하지 않은 분석 항목은 “분석 제외”로 표시합니다.</p>
            <p><strong>v36</strong> 억까 단서와 재현 난이도를 분리하고, 장기백을 부위·강화 구간·시점 기반으로 입력하게 변경했습니다.</p>
            <p><strong>v35</strong> 첫 접속 시 DB 시세를 자동 로드하고, 유효한 시세가 있으면 거래소 API를 다시 호출하지 않게 했습니다.</p>
            <p><strong>v34</strong> 직업각인 프리셋을 캐릭터 조회 결과에 맞춰 자동 적용하고, 서버 시작 시 재련 재료 시세 자동 수집을 추가했습니다.</p>
            <p><strong>v33</strong> 장신구 핵심 유효 종류/효과 수를 분리하고, 팔찌 옵션을 핵심·보조·조건부로 정리했습니다.</p>
            <p><strong>v32</strong> 스톤 시도 수가 기대값보다 적으면 억까 점수를 주지 않고, 서포터 장신구/팔찌 판정을 강화했습니다.</p>
            <p><strong>v31</strong> 억까 지수와 재현 난이도를 분리하고, 기억 입력이 없으면 판정 보류로 표시했습니다.</p>
            <p><strong>v30</strong> 장기백 횟수와 스톤 시도 수를 직접 입력하게 하고, 여러 억까 구간 선택을 지원했습니다.</p>
            <p><strong>v29</strong> 실제 사용 골드 입력 중심에서 캐릭터 결과물 기반 억까 리포트 구조로 전환했습니다.</p>
            <p><strong>v28</strong> 어빌리티 스톤 3/1을 성공 횟수가 아니라 활성 레벨로 해석하도록 수정했습니다.</p>
            <p><strong>v27</strong> 재련 재료비의 파편 단가 환산 오류를 수정하고 보조재료 최적화 기능을 제거했습니다.</p>
            <p><strong>v26</strong> 묶음 단위 가격 환산과 재련비 최적화 계산을 시도했습니다.</p>
            <p><strong>v25</strong> 보조재료 시세 수집과 접이식 제련 확률표를 추가했습니다.</p>
            <p><strong>v24</strong> 제련 단계별 재료량과 성공 확률표를 추가했습니다.</p>
            <p><strong>v23</strong> 기대값 프리셋과 장비·스톤·장신구 계산 기준을 정리했습니다.</p>
            <p><strong>v22</strong> 비교 항목 체크박스와 장신구 연마 효과 표시를 개선했습니다.</p>
            <p><strong>v21</strong> 기대값 계산 결과를 DB/캐시에 저장해 반복 계산 시간을 줄였습니다.</p>
            <p><strong>v20</strong> 팔찌 효과 상세 파싱과 표시를 개선했습니다.</p>
            <p><strong>v19</strong> 프론트엔드 API 프록시 경로 문제를 수정했습니다.</p>
            <p><strong>v18</strong> Windows/Docker 환경의 nginx 실행 문제를 보완했습니다.</p>
            <p><strong>v17</strong> 어빌리티 스톤 슬롯/표시 문제를 수정했습니다.</p>
            <p><strong>v16</strong> 팔찌 특수효과 파싱을 개선했습니다.</p>
            <p><strong>v15</strong> nginx 기본 페이지가 보이는 문제를 수정했습니다.</p>
            <p><strong>v14</strong> 거래소 시세 수집 POST 요청 오류를 수정했습니다.</p>
            <p><strong>v13</strong> 재료 시세 API 500 오류와 프론트 예외를 수정했습니다.</p>
            <p><strong>v12</strong> Docker 빌드 중 npm install 문제를 보완했습니다.</p>
            <p><strong>v11</strong> 재련 재료 시세 수집 기능을 추가했습니다.</p>
            <p><strong>v10</strong> 팔찌와 스톤 표시를 함께 정리했습니다.</p>
            <p><strong>v9</strong> 어빌리티 스톤 효과 표시 방식을 개선했습니다.</p>
            <p><strong>v8</strong> 캐릭터 조회 실패 문제를 수정했습니다.</p>
            <p><strong>v7</strong> pyLoa 구조를 참고해 캐릭터 조회 방식을 보완했습니다.</p>
            <p><strong>v6</strong> 어빌리티 스톤을 한 개 기준으로 단순 표시하도록 변경했습니다.</p>
            <p><strong>v5</strong> 어빌리티 스톤 파싱 오류를 수정했습니다.</p>
            <p><strong>v4</strong> 사용자 친화적인 라벨과 표시 문구를 정리했습니다.</p>
            <p><strong>v3</strong> DB 캐시 구조를 추가했습니다.</p>
            <p><strong>v2</strong> 캐릭터 비교 화면의 기본 구조를 만들었습니다.</p>
            <p><strong>v1</strong> 로스트아크 성장 억까 판정기 아이디어와 초기 스타터 구조를 잡았습니다.</p>
          </div>
        </details>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
