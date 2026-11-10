import { useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Play } from 'lucide-react';
import PageHead from '../components/common/PageHead';
import { LoadingState, ErrorState, InlineAlert } from '../components/common/States';
import StatusBadge from '../components/common/StatusBadge';
import AgentPipeline from '../components/processing/AgentPipeline';
import { useAsync } from '../hooks/useAsync';
import { useToast } from '../components/common/Toast';
import { getDocument, processDocument } from '../services/documentApi';
import { normalizeDoc, isActive, hasResults, pick } from '../services/adapters';
import { formatDate, elapsed } from '../utils/formatDate';

export default function ProcessingPage() {
  const { documentId } = useParams(); const toast = useToast();
  const started = useRef(false); const [busy, setBusy] = useState(false); const [err, setErr] = useState('');
  const { data, loading, error, reload } = useAsync((s) => getDocument(documentId, s), [documentId], {
    poll: 3000,
    stopWhen: (d) => { const k = normalizeDoc(d).status; if (k !== 'uploaded') started.current = false; return !isActive(k) && !(started.current && k === 'uploaded'); },
  });
  if (loading && !data) return <LoadingState label="Loading processing status" />;
  if (error && !data) return <ErrorState error={error} onRetry={reload} />;
  const d = normalizeDoc(data); const active = isActive(d.status);
  const t0 = pick(d.raw, ['started_at', 'processing_started_at']); const t1 = pick(d.raw, ['completed_at', 'finished_at']);
  const start = async () => {
    if (busy || active) return; setBusy(true); setErr('');
    try { await processDocument(documentId); started.current = true; toast('Processing request accepted', 'success'); reload(); }
    catch (e) { setErr(e.message); if (e.status === 409) reload(); } finally { setBusy(false); }
  };
  const base = `/documents/${encodeURIComponent(documentId)}`;
  return (
    <>
      <PageHead title="AI Processing" subtitle={d.filename}>
        <StatusBadge status={d.status} raw={d.rawStatus} />
        <button className="btn primary" onClick={start} disabled={busy || active}><Play size={16} />{busy ? 'Starting…' : active ? 'In progress' : d.status === 'uploaded' ? 'Start processing' : 'Process again'}</button>
      </PageHead>
      {err && <InlineAlert>{err}</InlineAlert>}
      {error && <InlineAlert kind="warn">Could not refresh status: {error.message}</InlineAlert>}
      {d.status === 'failed' && <InlineAlert>Processing failed{d.stage ? ` at “${d.stage}”` : ''}. {d.error ? String(typeof d.error === 'string' ? d.error : JSON.stringify(d.error)) : 'No error details were returned.'}</InlineAlert>}
      {d.status === 'needs_review' && <InlineAlert kind="warn">A human decision is required. <Link to={`/reviews?doc=${encodeURIComponent(documentId)}`}>Open Human Review</Link></InlineAlert>}
      <div className="grid two">
        <div className="card"><div className="card-head"><h2>Pipeline</h2></div>
          {active && <div className="progress indet" role="progressbar" aria-label="Processing in progress" style={{ marginBottom: 12 }}><i /></div>}
          <div aria-live="polite"><AgentPipeline doc={d} /></div></div>
        <div className="card"><h2 style={{ marginBottom: 14 }}>Status details</h2>
          <dl className="kv"><dt>Backend status</dt><dd>{String(d.rawStatus ?? '—')}</dd><dt>Current stage</dt><dd>{d.stage || 'Not reported'}</dd>
            <dt>Uploaded</dt><dd>{formatDate(d.uploadedAt)}</dd><dt>Last updated</dt><dd>{formatDate(d.updatedAt)}</dd>
            {t0 && <><dt>Started</dt><dd>{formatDate(t0)}</dd><dt>Elapsed</dt><dd>{elapsed(t0, active ? Date.now() : t1 || Date.now())}</dd></>}</dl>
          <div className="row-actions" style={{ marginTop: 16 }}>
            {hasResults(d.status) && <><Link className="btn" to={`${base}/results`}>Extraction results</Link><Link className="btn" to={`${base}/validation`}>Validation</Link></>}
            <Link className="btn" to={base}>Document details</Link></div>
          {active && <p className="muted small" style={{ marginTop: 12 }}>Status refreshes every 3 seconds until processing finishes.</p>}</div>
      </div>
    </>
  );
}
