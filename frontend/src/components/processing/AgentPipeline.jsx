import { Check, Loader2, X, Circle, UserCheck } from 'lucide-react';

export const STAGES = ['Document Ingestion', 'OCR / Text Recognition', 'Extraction Agent', 'Validation Agent', 'Decision Agent', 'Workflow Agent'];
const norm = (s) => String(s || '').toLowerCase().replace(/[^a-z]/g, '');

// Stage state is derived only from what the backend reports (overall status, and current stage if provided).
export default function AgentPipeline({ doc }) {
  const reported = STAGES.findIndex((s) => doc.stage && (norm(s).includes(norm(doc.stage)) || norm(doc.stage).includes(norm(s).replace('agent', ''))));
  const stateOf = (i) => {
    if (['processed', 'approved', 'rejected', 'needs_review'].includes(doc.status)) return 'done';
    if (doc.status === 'failed') return reported === i ? 'bad' : reported > i ? 'done' : 'idle';
    if (doc.status === 'processing') return reported === -1 ? 'idle' : i < reported ? 'done' : i === reported ? 'run' : 'idle';
    return 'idle';
  };
  const note = { done: 'Completed', run: 'Running', bad: 'Failed', idle: doc.status === 'processing' && reported === -1 ? 'Backend has not reported this stage' : 'Not started' };
  const icon = { done: <Check size={16} />, run: <Loader2 size={16} />, bad: <X size={16} />, idle: <Circle size={12} /> };
  const finalLabel = { processed: 'Completed', approved: 'Approved', rejected: 'Rejected', needs_review: 'Human review required', failed: 'Failed' }[doc.status];
  const finalCls = { processed: 'done', approved: 'done', rejected: 'bad', needs_review: 'warn', failed: 'bad' }[doc.status] || 'idle';
  return (
    <ol className="pipeline" aria-label="Processing pipeline">
      {STAGES.map((s, i) => { const st = stateOf(i); return (
        <li key={s} className={st === 'idle' ? '' : st}><span className="mark">{icon[st]}</span><span className="txt"><b>{s}</b><span className="muted small">{note[st]}</span></span></li>
      ); })}
      <li className={finalCls === 'idle' ? '' : finalCls}><span className="mark">{finalCls === 'warn' ? <UserCheck size={16} /> : finalCls === 'done' ? <Check size={16} /> : finalCls === 'bad' ? <X size={16} /> : <Circle size={12} />}</span>
        <span className="txt"><b>Completed / Human Review / Failed</b><span className="muted small">{finalLabel || 'Outcome not available yet'}</span></span></li>
    </ol>
  );
}
