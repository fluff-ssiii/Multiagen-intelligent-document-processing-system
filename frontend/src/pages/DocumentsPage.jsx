import { useMemo, useState } from 'react';
import { RefreshCw, Search } from 'lucide-react';
import PageHead from '../components/common/PageHead';
import { LoadingState, ErrorState, EmptyState, InlineAlert } from '../components/common/States';
import DocumentTable from '../components/documents/DocumentTable';
import { useDocuments } from '../hooks/useDocuments';
import { useDebounce } from '../hooks/useDebounce';
import { useToast } from '../components/common/Toast';
import { processDocument } from '../services/documentApi';
import { STATUS_META } from '../services/adapters';
import { SearchX } from 'lucide-react';

export default function DocumentsPage() {
  const { docs, loading, error, reload } = useDocuments();
  const toast = useToast();
  const [q, setQ] = useState(''); const [status, setStatus] = useState(''); const [type, setType] = useState('');
  const [sort, setSort] = useState('new'); const [busyId, setBusyId] = useState(null); const [actionError, setActionError] = useState('');
  const dq = useDebounce(q).trim().toLowerCase();
  const types = useMemo(() => [...new Set(docs.map((d) => d.type).filter(Boolean))], [docs]);
  const rows = useMemo(() => docs
    .filter((d) => (!dq || d.filename.toLowerCase().includes(dq) || d.id.toLowerCase().includes(dq)) && (!status || d.status === status) && (!type || d.type === type))
    .sort((a, b) => sort === 'name' ? a.filename.localeCompare(b.filename) : (new Date(b.uploadedAt || 0) - new Date(a.uploadedAt || 0)) * (sort === 'old' ? -1 : 1)), [docs, dq, status, type, sort]);

  const start = async (d) => {
    setBusyId(d.id); setActionError('');
    try { await processDocument(d.id); toast(`Processing requested for ${d.filename}`, 'success'); reload(); }
    catch (e) { setActionError(`${d.filename}: ${e.message}`); if (e.status === 409) reload(); } finally { setBusyId(null); }
  };

  return (
    <>
      <PageHead title="All Documents" subtitle="Search, filter and open any uploaded document."><button className="btn" onClick={reload}><RefreshCw size={16} />Refresh</button></PageHead>
      {actionError && <InlineAlert>{actionError}</InlineAlert>}
      {loading && !docs.length ? <LoadingState /> : error ? <ErrorState error={error} onRetry={reload} /> : docs.length === 0 ? (
        <EmptyState title="No documents uploaded" text="Upload a document to get started." to="/documents/upload" cta="Upload Documents" />
      ) : (
        <div className="card">
          <div className="toolbar">
            <div style={{ position: 'relative', flex: 2, minWidth: 200 }}><Search size={16} style={{ position: 'absolute', left: 12, top: 13 }} aria-hidden="true" />
              <input className="input" style={{ paddingLeft: 36, width: '100%' }} placeholder="Search by file name or ID" aria-label="Search documents" value={q} onChange={(e) => setQ(e.target.value)} /></div>
            <select className="input" aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option>{Object.entries(STATUS_META).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}</select>
            {types.length > 0 && <select className="input" aria-label="Filter by type" value={type} onChange={(e) => setType(e.target.value)}><option value="">All types</option>{types.map((t) => <option key={t}>{t}</option>)}</select>}
            <select className="input" aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value)}><option value="new">Newest first</option><option value="old">Oldest first</option><option value="name">Name A–Z</option></select>
          </div>
          {rows.length ? <DocumentTable docs={rows} onProcess={start} busyId={busyId} /> : <div className="state"><SearchX size={30} /><h3>No matching documents</h3><p>Try a different search or clear the filters.</p></div>}
          <p className="muted small" style={{ marginTop: 10 }}>Showing {rows.length} of {docs.length}</p>
        </div>
      )}
    </>
  );
}
