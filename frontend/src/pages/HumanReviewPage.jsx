import { useMemo, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { RefreshCw, UserCheck } from 'lucide-react';
import PageHead from '../components/common/PageHead';
import { LoadingState, ErrorState, EmptyState, InlineAlert } from '../components/common/States';
import StatusBadge from '../components/common/StatusBadge';
import ExtractedFields from '../components/results/ExtractedFields';
import ValidationIssues from '../components/validation/ValidationIssues';
import DocumentPreview from '../components/documents/DocumentPreview';
import ReviewActions from '../components/reviews/ReviewActions';
import { useAsync } from '../hooks/useAsync';
import { useToast } from '../components/common/Toast';
import { getPendingReviews, approveDocument, rejectDocument } from '../services/reviewApi';
import { getResults } from '../services/documentApi';
import { listFrom, normalizeDoc, splitResults, normalizeValidation } from '../services/adapters';
import { formatDate } from '../utils/formatDate';

function Detail({ item, onDecide }) {
  const toast = useToast(); const [busy, setBusy] = useState(false); const [err, setErr] = useState('');
  const { data, loading, error, reload } = useAsync((s) => getResults(item.id, s), [item.id]);
  const decide = (fn, verb) => async () => {
    if (busy) return false; setBusy(true); setErr('');
    try { await fn(item.id); toast(`Document ${verb}`, 'success'); await onDecide(); return true; }
    catch (e) { setErr(`Could not ${verb === 'approved' ? 'approve' : 'reject'}: ${e.message}`); return false; }
    finally { setBusy(false); }
  };
  const { extraction, validation } = splitResults(data);
  return (
    <div className="card">
      <div className="card-head"><div><h2>{item.filename}</h2><p className="muted small mono">{item.id}</p></div>
        <ReviewActions filename={item.filename} busy={busy} onApprove={decide(approveDocument, 'approved')} onReject={decide(rejectDocument, 'rejected')} /></div>
      {err && <InlineAlert action={<button className="btn sm" onClick={() => setErr('')}>Dismiss</button>}>{err}</InlineAlert>}
      {item.reason && <InlineAlert kind="warn"><b>Reason for review:</b> {String(item.reason)}</InlineAlert>}
      {loading && !data ? <LoadingState rows={3} /> : error ? <ErrorState error={error} onRetry={reload} title="Could not load results" /> : (
        <>
          <h3 style={{ margin: '8px 0' }}>Source document</h3><DocumentPreview doc={item} />
          <h3 style={{ margin: '18px 0 8px' }}>Extracted fields</h3><ExtractedFields data={extraction} />
          <h3 style={{ margin: '18px 0 8px' }}>Validation</h3><ValidationIssues validation={normalizeValidation(validation)} raw={validation} />
        </>
      )}
    </div>
  );
}

export default function HumanReviewPage() {
  const [params, setParams] = useSearchParams();
  const { data, loading, error, reload } = useAsync((s) => getPendingReviews(s));
  const items = useMemo(() => listFrom(data).map(normalizeDoc), [data]);
  const selected = items.find((i) => i.id === params.get('doc'));
  const onDecide = async () => { setParams({}); reload(); };
  return (
    <>
      <PageHead title="Human Review" subtitle="Documents that need a person to approve or reject them."><button className="btn" onClick={reload}><RefreshCw size={16} />Refresh</button></PageHead>
      {loading && !data ? <LoadingState /> : error ? <ErrorState error={error} onRetry={reload} /> : items.length === 0 ? (
        <EmptyState icon={UserCheck} title="No documents are waiting for review." text="Documents the pipeline is unsure about will appear here." />
      ) : (
        <div className="grid" style={{ gridTemplateColumns: 'minmax(260px,340px) 1fr' }}>
          <div>{items.map((i) => (
            <button key={i.id} className="queue-item" aria-current={selected?.id === i.id} onClick={() => setParams({ doc: i.id })}>
              <b>{i.filename}</b><div className="muted small">{formatDate(i.updatedAt || i.uploadedAt)}</div>
              {i.reason && <div className="small" style={{ margin: '4px 0' }}>{String(i.reason)}</div>}<StatusBadge status={i.status} raw={i.rawStatus} />
            </button>))}</div>
          <div>{selected ? <Detail key={selected.id} item={selected} onDecide={onDecide} /> : <div className="card state"><h3>Select a document</h3><p>Choose an item from the queue to review it. <Link to="/documents">All documents</Link></p></div>}</div>
        </div>
      )}
    </>
  );
}
