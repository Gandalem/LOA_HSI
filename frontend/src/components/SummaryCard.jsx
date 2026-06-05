import React from 'react';
export default function SummaryCard({ title, value, sub }) {
  return (
    <div className="card summary-card">
      <div className="card-title">{title}</div>
      <div className="card-value">{value}</div>
      {sub && <div className="card-sub">{sub}</div>}
    </div>
  );
}
