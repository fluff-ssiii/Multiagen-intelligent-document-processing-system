import { AlertTriangle, XCircle, CheckCircle2 } from 'lucide-react';

function Group({ title, items, blocking }) {
  if (!items.length) return null;
  const Icon = blocking ? XCircle : AlertTriangle;
  return (
    <section className="card" aria-label={title}>
      <div className="card-head"><h2>{title} ({items.length})</h2></div>
      {items.map((i, n) => (
        <div className="issue" key={n}>
          <Icon size={20} color={blocking ? '#b4232f' : '#9a5b00'} aria-hidden="true" />
          <div>
            <b>{i.field ? String(i.field).replace(/_/g, ' ') : blocking ? 'Blocking error' : 'Warning'}</b>
            <span className="badge gray" style={{ marginLeft: 8 }}>{i.severity}</span>
            <p>{String(i.message)}</p>
            {(i.expected !== undefined || i.actual !== undefined) && <p className="muted small">Expected: <span className="mono">{JSON.stringify(i.expected) ?? '—'}</span> · Actual: <span className="mono">{JSON.stringify(i.actual) ?? '—'}</span></p>}
          </div>
        </div>
      ))}
    </section>
  );
}

export default function ValidationIssues({ validation, raw }) {
  if (!validation) return <div className="card"><p className="muted">The results do not include a validation payload.</p></div>;
  const blockers = validation.issues.filter((i) => i.blocking), warnings = validation.issues.filter((i) => !i.blocking);
  return (
    <>
      <div className="card"><div className="card-head"><h2>Validation status</h2>
        <span className={`badge ${/invalid|fail|error/i.test(validation.status || '') || blockers.length ? 'red' : /warn|review/i.test(validation.status || '') || warnings.length ? 'amber' : validation.status ? 'green' : 'gray'}`}>
          {validation.status ? validation.status.replace(/_/g, ' ') : 'Status not reported'}</span></div>
        <p className="muted">{blockers.length} blocking error(s) · {warnings.length} warning(s)</p>
      </div>
      <Group title="Blocking errors" items={blockers} blocking />
      <Group title="Warnings" items={warnings} />
      {!validation.issues.length && (
        <div className="card state"><CheckCircle2 size={30} aria-hidden="true" /><h3>No issues reported</h3><p>The backend listed no errors or warnings for this document.</p>
          <details style={{ marginTop: 12, textAlign: 'left' }}><summary>Raw validation payload</summary><pre className="json">{JSON.stringify(raw, null, 2)}</pre></details></div>
      )}
    </>
  );
}
