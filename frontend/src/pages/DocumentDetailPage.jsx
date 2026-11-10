import { Link, useParams } from 'react-router-dom';
import PageHead from '../components/common/PageHead';
import { LoadingState, ErrorState } from '../components/common/States';
import StatusBadge from '../components/common/StatusBadge';
import DocumentPreview from '../components/documents/DocumentPreview';
import { useAsync } from '../hooks/useAsync';
import { getDocument } from '../services/documentApi';
import { normalizeDoc, isActive, hasResults } from '../services/adapters';
import { formatDate } from '../utils/formatDate';

export default function DocumentDetailPage() {
  const { documentId } = useParams();
  const { data, loading, error, reload } = useAsync((s) => getDocument(documentId, s), [documentId], { poll: 4000, stopWhen: (d) => !isActive(normalizeDoc(d).status) });
  if (loading && !data) return <LoadingState label="Loading document" />;
  if (error && !data) return <ErrorState error={error} onRetry={reload} />;
  const d = normalizeDoc(data); const base = `/documents/${encodeURIComponent(documentId)}`;
  const rows = [['File name', d.filename], ['Document ID', <span className="mono" key="i">{d.id || documentId}</span>], ['File type', d.fileType || '—'], ['Document type', d.type || '—'],
    ['Uploaded', formatDate(d.uploadedAt)], ['Last updated', formatDate(d.updatedAt)], ['Description', d.description || '—'], ['Tags', d.tags.length ? d.tags.join(', ') : '—']];
  return (
    <>
      <PageHead title={d.filename} subtitle="Document details"><StatusBadge status={d.status} raw={d.rawStatus} /></PageHead>
      <div className="grid split">
        <div className="card"><h2 style={{ marginBottom: 14 }}>Details</h2><dl className="kv">{rows.map(([k, v]) => <div style={{ display: 'contents' }} key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
          {d.error && <div className="alert error" style={{ marginTop: 14 }}><div>{String(typeof d.error === 'string' ? d.error : JSON.stringify(d.error))}</div></div>}
          <div className="row-actions" style={{ marginTop: 18 }}>
            <Link className="btn primary" to={`${base}/processing`}>{d.status === 'uploaded' ? 'Start processing' : 'View processing'}</Link>
            {hasResults(d.status) && <><Link className="btn" to={`${base}/results`}>Extraction results</Link><Link className="btn" to={`${base}/validation`}>Validation</Link></>}
            {d.status === 'needs_review' && <Link className="btn" to={`/reviews?doc=${encodeURIComponent(documentId)}`}>Open review</Link>}
          </div></div>
        <div className="card"><h2 style={{ marginBottom: 14 }}>Source document</h2><DocumentPreview doc={d} /></div>
      </div>
    </>
  );
}
