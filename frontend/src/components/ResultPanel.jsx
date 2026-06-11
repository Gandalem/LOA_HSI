import React from 'react';
import BraceletOfficialPanel from './BraceletOfficialPanel.jsx';
import MarketCostPanel from './MarketCostPanel.jsx';
import LegacyResultPanel from './ResultPanelLegacy.jsx';

export default function ResultPanel(props) {
  const expectedValues = props.result?.expectedValues || {};
  const officialBracelet = expectedValues.officialBraceletT4;
  const marketCost = expectedValues.marketCost;

  return (
    <>
      <LegacyResultPanel {...props} />
      <BraceletOfficialPanel officialBracelet={officialBracelet} />
      <MarketCostPanel marketCost={marketCost} />
    </>
  );
}
