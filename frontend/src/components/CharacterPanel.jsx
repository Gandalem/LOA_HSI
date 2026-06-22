import React from 'react';
import '../styles/v48-mobile.css';

function fmt(value) {
  if (value === null || value === undefined || value === '') return '-';
  return value;
}

function quality(value) {
  if (value === null || value === undefined || value === '') return '-';
  const n = Number(value);
  if (Number.isNaN(n) || n < 0 || n > 100) return '-';
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

function SnapshotCard({ label, value }) {
  return (
    <div className="snapshot-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function GearMobileCards({ items = [] }) {
  if (!items.length) return <p className="hint mobile-card-only">조회된 장비가 없습니다.</p>;
  return (
    <div className="mobile-card-list mobile-card-only">
      {items.map((item, idx) => (
        <article className="spec-mobile-card" key={`${item.slot}-${item.name}-${idx}`}>
          <div className="spec-card-head">
            <strong>{item.slot}</strong>
            <span>{item.honing_level ? `+${item.honing_level}` : '강화 정보 없음'}</span>
          </div>
          <p>{item.name || '-'}</p>
          <div className="spec-card-meta">
            <span>{item.grade || '-'}</span>
            <span>아이템 레벨 {item.item_level || '-'}</span>
            <span>품질 {quality(item.quality)}</span>
          </div>
        </article>
      ))}
    </div>
  );
}

function AccessoryMobileCards({ items = [] }) {
  if (!items.length) return <p className="hint mobile-card-only">조회된 장신구가 없습니다.</p>;
  return (
    <div className="mobile-card-list mobile-card-only">
      {items.map((item, idx) => (
        <article className="spec-mobile-card accessory-mobile-card" key={`${item.slot}-${item.name}-${idx}`}>
          <div className="spec-card-head">
            <strong>{item.slot}</strong>
            <span>품질 {quality(item.quality)}</span>
          </div>
          <p>{item.name || '-'}</p>
          <div className="spec-card-meta">
            <span>{item.grade || '-'}</span>
          </div>
          <div className="spec-card-effects">
            {item.slot === '팔찌' ? (braceletEffects(item) || <span>-</span>) : (accessoryEffects(item) || <span>-</span>)}
          </div>
        </article>
      ))}
    </div>
  );
}

export default function CharacterPanel({ character }) {
  if (!character) return null;

  const stone = character.ability_stone;
  const preset = character.class_engraving_preset;
  const positive1 = effectLine(stone?.positive_1_name, stone?.positive_1_points, '긍정 각인 1');
  const positive2 = effectLine(stone?.positive_2_name, stone?.positive_2_points, '긍정 각인 2');
  const negative = effectLine(stone?.negative_name, stone?.negative_points, '감소 각인');
  const warnings = character.warnings?.filter((warning) => !warning.includes('어빌리티 스톤 각인 확인')) || [];

  return (
    <section className="card character-shell">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Character Snapshot</p>
          <h2>캐릭터 현재 상태</h2>
          <p className="section-copy">공식 API에서 읽은 현재 세팅 기준 요약입니다.</p>
        </div>
      </div>

      <div className="snapshot-grid">
        <SnapshotCard label="캐릭터" value={fmt(character.character_name)} />
        <SnapshotCard label="서버" value={fmt(character.server_name)} />
        <SnapshotCard label="직업" value={fmt(character.class_name)} />
        <SnapshotCard
          label="직업 각인 프리셋"
          value={preset ? `${preset.engravingName} · ${preset.role}` : '자동 판별 대기'}
        />
        <SnapshotCard label="아이템 레벨" value={fmt(character.item_avg_level)} />
      </div>

      {warnings.length > 0 ? (
        <div className="warning-box">
          {warnings.map((warning, idx) => <div key={idx}>주의: {warning}</div>)}
        </div>
      ) : null}

      <div className="character-section-block">
        <div className="subsection-heading">
          <h3>장비</h3>
          <span>재련 시뮬레이션 기준</span>
        </div>
        <div className="table-wrap desktop-table-wrap">
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
        <GearMobileCards items={character.equipment || []} />
      </div>

      <div className="character-section-block">
        <div className="subsection-heading">
          <h3>어빌리티 스톤</h3>
          <span>경매장 베이스 + 기대 시도 수 기준</span>
        </div>
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
                  <span>긍정 각인</span>
                  <strong>{positive1.label}</strong>
                  <em>{positive1.value}</em>
                </div>
                <div className="stone-effect positive">
                  <span>긍정 각인</span>
                  <strong>{positive2.label}</strong>
                  <em>{positive2.value}</em>
                </div>
                <div className="stone-effect negative">
                  <span>감소 각인</span>
                  <strong>{negative.label}</strong>
                  <em>{negative.value}</em>
                </div>
              </div>
            </div>
          ) : (
            <div>스톤 정보를 찾지 못했습니다.</div>
          )}
        </div>
      </div>

      <div className="character-section-block">
        <div className="subsection-heading">
          <h3>장신구 · 팔찌</h3>
          <span>핵심 옵션, 품질, 고정 효과 기준</span>
        </div>
        <div className="table-wrap desktop-table-wrap">
          <table>
            <thead>
              <tr><th>부위</th><th>이름</th><th>등급</th><th>품질</th><th>효과</th></tr>
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
        <AccessoryMobileCards items={character.accessories || []} />
      </div>
    </section>
  );
}
