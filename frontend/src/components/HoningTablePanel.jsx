import React, { useEffect, useMemo, useState } from 'react';

function money(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Number(value).toLocaleString('ko-KR', { maximumFractionDigits: 2 });
}

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return `${Number(value).toFixed(2)}%`;
}

function materialText(materials) {
  if (!materials || !materials.length) return '-';
  return materials.map((m) => `${m.name} ${Number(m.quantity).toLocaleString('ko-KR')}`).join(' / ');
}

function inferGradeKeyFromCharacter(character) {
  const equipment = character?.equipment || [];
  const names = equipment.map((item) => String(item.name || '')).join(' ');
  if (names.includes('운명의 전율')) return 't4_1730';
  if (names.includes('에기르')) return 't4_1590';
  const levels = equipment.map((item) => Number(item.item_level || 0)).filter((n) => n > 0);
  if (levels.some((n) => n >= 1730)) return 't4_1730';
  if (levels.some((n) => n >= 1590)) return 't4_1590';
  return 't4_1730';
}

function gradeLabel(key) {
  if (key === 't4_1590') return '에기르 장비 · T4 1590 계열';
  if (key === 't4_1730') return '운명의 전율 장비 · T4 1730 계열';
  return key;
}

export default function HoningTablePanel({ data, loading, onReload, character }) {
  const [gearKind, setGearKind] = useState('armor');
  const [gradeKey, setGradeKey] = useState(inferGradeKeyFromCharacter(character));
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setGradeKey(inferGradeKeyFromCharacter(character));
  }, [character?.character_name]);

  const rows = data?.rows || [];
  const filtered = useMemo(() => rows.filter((r) => r.gearKind === gearKind && r.gradeKey === gradeKey), [rows, gearKind, gradeKey]);

  return (
    <div className={`honing-table-panel ${open ? 'open' : 'collapsed'}`}>
      <div className="section-head-row honing-panel-header" role="button" tabIndex="0" onClick={() => setOpen((v) => !v)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setOpen((v) => !v); }}>
        <div>
          <h3>{open ? '▼' : '▶'} 제련 단계별 재료량 / 확률표</h3>
          <p className="hint">클릭하면 선택한 구간의 기본 재료량과 1회 재련 비용을 볼 수 있습니다.</p>
        </div>
        <div className="honing-header-actions" onClick={(e) => e.stopPropagation()}>
          <button className="ghost" onClick={onReload} disabled={loading}>{loading ? '불러오는 중...' : '표 새로고침'}</button>
        </div>
      </div>

      {open && (
        <>
          <div className="honing-filter-row compact">
            <label>장비 종류
              <select value={gearKind} onChange={(e) => setGearKind(e.target.value)}>
                <option value="armor">방어구</option>
                <option value="weapon">무기</option>
              </select>
            </label>
            <label>구간
              <select value={gradeKey} onChange={(e) => setGradeKey(e.target.value)}>
                <option value="t4_1590">에기르 장비 · T4 1590 계열</option>
                <option value="t4_1730">운명의 전율 장비 · T4 1730 계열</option>
              </select>
            </label>
            <div className="honing-mini-status">
              <strong>{gradeLabel(gradeKey)}</strong>
              <span>{data?.supportMaterialNote || '보조재료는 계산에서 제외했습니다.'}</span>
            </div>
          </div>

          <div className="table-wrap honing-table-wrap clean-honing-table">
            <table>
              <thead>
                <tr>
                  <th>목표 강화</th>
                  <th>기본 성공 확률</th>
                  <th>필요 재료</th>
                  <th>1회 재련 비용</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr key={`${row.gearKind}-${row.gradeKey}-${row.targetLevel}`}>
                    <td><strong>+{row.targetLevel}</strong></td>
                    <td>{pct(row.baseSuccessRatePercent)}</td>
                    <td className="honing-material-cell">{materialText(row.materials)}</td>
                    <td><strong>{money(row.attemptCostGold)} G</strong></td>
                  </tr>
                ))}
                {!filtered.length && (
                  <tr>
                    <td colSpan="4">선택한 장비 종류/구간의 표 데이터가 없습니다. 시세 수집 실패와는 별개이며, 다른 구간을 선택하거나 표 새로고침을 눌러 확인하세요.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
