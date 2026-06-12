import React, { useEffect } from 'react';
import ResultPanelLegacyBase from './ResultPanelLegacyBase.jsx';

function clarifyLegacyAccessoryCostWording() {
  const detailSection = document.querySelector('.detail-section');
  if (!detailSection) return;

  detailSection.querySelectorAll('.module-card').forEach((card) => {
    const title = card.querySelector('strong');
    if ((title?.textContent || '').trim() !== '장신구') return;

    title.textContent = '장신구 연마 확률 모델';

    card.querySelectorAll('div').forEach((line) => {
      const text = line.textContent || '';
      if (text.startsWith('평균 재현 비용:')) {
        line.textContent = text.replace('평균 재현 비용:', '연마 확률 모델 평균:');
      } else if (text.startsWith('보통 유저 기준:')) {
        line.textContent = text.replace('보통 유저 기준:', '연마 확률 모델 중간값:');
      } else if (text.startsWith('상위 10% 고비용선:')) {
        line.textContent = text.replace('상위 10% 고비용선:', '연마 확률 모델 상위 10%:');
      } else if (text.startsWith('상위 1% 극단선:')) {
        line.textContent = text.replace('상위 1% 극단선:', '연마 확률 모델 상위 1%:');
      }
    });

    if (!card.querySelector('[data-loa-hsi-legacy-accessory-cost-note="true"]')) {
      const note = document.createElement('small');
      note.className = 'hint';
      note.dataset.loaHsiLegacyAccessoryCostNote = 'true';
      note.textContent = '이 값은 직접 연마/공식 확률표 기반 참고값입니다. 구매 기준 재현 비용은 v60.1 시장 재현 비용 카드의 장신구 시장가를 우선해서 봅니다.';
      card.appendChild(note);
    }
  });
}

export default function ResultPanelLegacy(props) {
  useEffect(() => {
    clarifyLegacyAccessoryCostWording();
    const timer = window.setTimeout(clarifyLegacyAccessoryCostWording, 120);
    return () => window.clearTimeout(timer);
  }, [props.result, props.memoryHints]);

  return <ResultPanelLegacyBase {...props} />;
}
