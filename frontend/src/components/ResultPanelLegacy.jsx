import React, { useEffect } from 'react';
import ResultPanelLegacyBase from './ResultPanelLegacyBase.jsx';

function simplifyResultDetailsForPublicUi() {
  const detailSection = document.querySelector('.detail-section');
  if (!detailSection) return;

  detailSection.querySelectorAll('h3').forEach((heading) => {
    const text = (heading.textContent || '').trim();
    if (text === '모듈별 원자료') {
      const moduleGrid = heading.nextElementSibling;
      heading.remove();
      if (moduleGrid?.classList?.contains('module-grid')) moduleGrid.remove();
    }
  });

  detailSection.querySelectorAll('details.assumptions').forEach((node) => node.remove());
}

export default function ResultPanelLegacy(props) {
  useEffect(() => {
    simplifyResultDetailsForPublicUi();
    const timer = window.setTimeout(simplifyResultDetailsForPublicUi, 120);
    return () => window.clearTimeout(timer);
  }, [props.result, props.memoryHints]);

  return <ResultPanelLegacyBase {...props} />;
}
