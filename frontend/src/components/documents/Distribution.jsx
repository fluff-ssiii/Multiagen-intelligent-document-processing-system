import { STATUS_META } from '../../services/adapters';

// Real share of documents per status. Counts only — this is not an accuracy metric.
export default function Distribution({ docs }) {
  const total = docs.length;
  const counts = {}; docs.forEach((d) => { counts[d.status] = (counts[d.status] || 0) + 1; });
  const rows = Object.keys(STATUS_META).filter((k) => counts[k]);
  return (
    <div className="bars" role="list" aria-label="Documents by status">
      {rows.map((k) => (
        <div className="bar-row" role="listitem" key={k}>
          <span>{STATUS_META[k].label}</span>
          <div className="bar" aria-hidden="true"><i style={{ width: `${(counts[k] / total) * 100}%` }} /></div>
          <span className="small">{counts[k]} of {total} ({Math.round((counts[k] / total) * 100)}%)</span>
        </div>
      ))}
    </div>
  );
}
