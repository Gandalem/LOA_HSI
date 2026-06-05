import React from 'react';
function fmt(value) {
  if (value === null || value === undefined || value === '') return '-';
  return value;
}

function quality(value) {
  if (value === null || value === undefined || value === '') return '-';
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  if (n < 0 || n > 100) return '-';
  return `${n}`;
}


function effectList(effects, className = 'effects-list') {
  if (!effects?.length) return null;
  return (
    <ul className={className}>
      {effects.map((effect, idx) => <li key={idx}>{effect}</li>)}
    </ul>
  );
}

function braceletEffects(item) {
  const effects = item?.bracelet_effects || item?.braceletEffects || [];
  return effectList(effects, 'bracelet-effects-list');
}

function accessoryEffects(item) {
  const effects = item?.accessory_effects || item?.accessoryEffects || [];
  return effectList(effects, 'accessory-effects-list');
}

function effectLine(name, points, fallbackName) {
  const label = name || fallbackName;
  const value = points === null || points === undefined ? '-' : `+${points}`;
  return { label, value };
}

export default function CharacterPanel({ character }) {
  if (!character) return null;
  const stone = character.ability_stone;
  const preset = character.class_engraving_preset;
  const positive1 = effectLine(stone?.positive_1_name, stone?.positive_1_points, '활성 각인 1');
  const positive2 = effectLine(stone?.positive_2_name, stone?.positive_2_points, '활성 각인 2');
  const negative = effectLine(stone?.negative_name, stone?.negative_points, '감소 효과');

  return (
    <section className="card">
      <h2>캐릭터 스펙 요약</h2>
      <div className="character-grid">
        <div><strong>캐릭터</strong><span>{fmt(character.character_name)}</span></div>
        <div><strong>서버</strong><span>{fmt(character.server_name)}</span></div>
        <div><strong>직업</strong><span>{fmt(character.class_name)}</span></div>
        <div><strong>직업각인 프리셋</strong><span>{preset ? `${preset.engravingName} · ${preset.role}` : '자동 감지 대기'}</span></div>
        <div><strong>아이템 레벨</strong><span>{fmt(character.item_avg_level)}</span></div>
      </div>

      {character.warnings?.filter((w) => !w.includes('어빌리티 스톤 각인 포인트')).length > 0 && (
        <div className="warning-box">
          {character.warnings
            .filter((w) => !w.includes('어빌리티 스톤 각인 포인트'))
            .map((w, idx) => <div key={idx}>주의: {w}</div>)}
        </div>
      )}

      <h3>장비</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>부위</th><th>이름</th><th>등급</th><th>아이템 레벨</th><th>강화</th><th>품질</th></tr>
          </thead>
          <tbody>
            {character.equipment?.map((item, idx) => (
              <tr key={idx}>
                <td>{item.slot}</td>
                <td>{item.name || '-'}</td>
                <td>{item.grade || '-'}</td>
                <td>{item.item_level || '-'}</td>
                <td>{item.honing_level ? `+${item.honing_level}` : '-'}</td>
                <td>{quality(item.quality)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>어빌리티 스톤</h3>
      <div className="stone-box single-stone-box">
        {stone ? (
          <div className="stone-detail-layout">
            <div className="stone-title-line">
              <div>
                <strong>{stone.name || '어빌리티 스톤'}</strong>
                <span className="muted-small">{stone.grade || '-'}</span>
              </div>
            </div>
            <div className="stone-effect-grid">
              <div className="stone-effect positive">
                <span>활성 각인</span>
                <strong>{positive1.label}</strong>
                <em>{positive1.value}</em>
              </div>
              <div className="stone-effect positive">
                <span>활성 각인</span>
                <strong>{positive2.label}</strong>
                <em>{positive2.value}</em>
              </div>
              <div className="stone-effect negative">
                <span>감소 효과</span>
                <strong>{negative.label}</strong>
                <em>{negative.value}</em>
              </div>
            </div>
          </div>
        ) : (
          <div>스톤 정보를 찾지 못했습니다.</div>
        )}
      </div>

      <h3>장신구</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>부위</th><th>이름</th><th>등급</th><th>품질</th><th>연마/팔찌 효과</th></tr>
          </thead>
          <tbody>
            {character.accessories?.map((item, idx) => (
              <tr key={idx}>
                <td>{item.slot}</td>
                <td>{item.name || '-'}</td>
                <td>{item.grade || '-'}</td>
                <td>{quality(item.quality)}</td>
                <td className="accessory-effects-cell">{item.slot === '팔찌' ? (braceletEffects(item) || '-') : (accessoryEffects(item) || '-')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
