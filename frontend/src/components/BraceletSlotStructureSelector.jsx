import React from 'react';

export function braceletOptionCount(item) {
  const candidates = [
    item?.accessory_effects,
    item?.accessoryEffects,
    item?.effects,
    item?.parsedEffects,
    item?.rawEffects
  ];
  const effects = candidates.find((value) => Array.isArray(value));
  return effects ? effects.length : 0;
}

export function braceletStructureOptions(item) {
  const total = braceletOptionCount(item);
  const byTotal = {
    3: [{ fixedOptionCount: '1', randomOptionSlotCount: '2', label: '고정 1개 / 랜덤 2개' }],
    4: [
      { fixedOptionCount: '2', randomOptionSlotCount: '2', label: '고정 2개 / 랜덤 2개' },
      { fixedOptionCount: '1', randomOptionSlotCount: '3', label: '고정 1개 / 랜덤 3개' }
    ],
    5: [{ fixedOptionCount: '2', randomOptionSlotCount: '3', label: '고정 2개 / 랜덤 3개' }]
  };

  return [
    { value: '', fixedOptionCount: '', randomOptionSlotCount: '', label: '자동 추정 사용' },
    ...(byTotal[total] || [])
      .map((option) => ({ ...option, value: `${option.fixedOptionCount}:${option.randomOptionSlotCount}` }))
  ];
}

export function normalizeBraceletSlotStructure(source, item) {
  const fixedOptionCount = source?.fixedOptionCount === null || source?.fixedOptionCount === undefined ? '' : String(source.fixedOptionCount);
  const randomOptionSlotCount = source?.randomOptionSlotCount === null || source?.randomOptionSlotCount === undefined ? '' : String(source.randomOptionSlotCount);
  if (!fixedOptionCount && !randomOptionSlotCount) return { fixedOptionCount: '', randomOptionSlotCount: '' };

  const value = `${fixedOptionCount}:${randomOptionSlotCount}`;
  const allowed = braceletStructureOptions(item).some((option) => option.value === value);
  if (!allowed) return { fixedOptionCount: '', randomOptionSlotCount: '' };
  return { fixedOptionCount, randomOptionSlotCount };
}

export default function BraceletSlotStructureSelector({ item, value, disabled = false, onChange }) {
  const options = braceletStructureOptions(item);
  const total = braceletOptionCount(item);
  const fixedOptionCount = value?.fixedOptionCount || '';
  const randomOptionSlotCount = value?.randomOptionSlotCount || '';
  const selectedValue = fixedOptionCount && randomOptionSlotCount ? `${fixedOptionCount}:${randomOptionSlotCount}` : '';
  const safeValue = options.some((option) => option.value === selectedValue) ? selectedValue : '';

  return (
    <div className="accessory-acquisition-row" data-loa-hsi-bracelet-slot-inputs="true">
      <div className="accessory-acquisition-name">
        <strong>팔찌 구조 입력</strong>
        <small>
          {total ? `현재 팔찌 옵션 ${total}개 기준으로 가능한 조합만 선택합니다.` : '옵션 수를 확인하지 못하면 자동 추정을 사용합니다.'}
        </small>
      </div>
      <select
        data-loa-hsi-bracelet-structure
        disabled={disabled || options.length <= 1}
        value={safeValue}
        onChange={(event) => onChange?.(event.target.value)}
      >
        {options.map((option) => (
          <option value={option.value} key={option.value || 'auto'}>{option.label}</option>
        ))}
      </select>
      {total === 5 && (
        <small className="hint">옵션 5개 팔찌는 고정 2개 / 랜덤 3개 조합만 수동 선택할 수 있습니다.</small>
      )}
    </div>
  );
}
