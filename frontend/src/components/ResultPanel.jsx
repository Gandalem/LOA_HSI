import React from 'react';
import MarketCostPanel from './MarketCostPanel.jsx';
import LegacyResultPanel from './ResultPanelLegacy.jsx';

export default function ResultPanel(props) {
  const marketCost = props.result?.expectedValues?.marketCost;

  return (
    <>
      <LegacyResultPanel {...props} />
      <MarketCostPanel marketCost={marketCost} />
    </>
  );
}
