import { Link } from 'react-router-dom';
import { Files, CheckCircle2, UserCheck, XCircle, UploadCloud, RefreshCw } from 'lucide-react';
import PageHead from '../components/common/PageHead';
import { LoadingState, ErrorState, EmptyState } from '../components/common/States';
import DocumentTable from '../components/documents/DocumentTable';
import Distribution from '../components/documents/Distribution';
import { useDocuments } from '../hooks/useDocuments';

export default function DashboardPage() {
  const { docs, loading, error, reload } = useDocuments();
  const count = (...k) => docs.filter((d) => k.includes(d.status)).length;
  const cards = [
    ['Total documents', docs.length, Files], ['Processed', count('processed', 'approved'), CheckCircle2],
    ['Pending review', count('needs_review'), UserCheck], ['Failed', count('failed'), XCircle],
  ];
  const recent = [...docs].sort((a, b) => new Date(b.uploadedAt || 0) - new Date(a.uploadedAt || 0)).slice(0, 6);
  return (
    <>
      <PageHead title="Dashboard" subtitle="Intelligent Documents. Smarter Workflows.">
        <button className="btn" onClick={reload}><RefreshCw size={16} />Refresh</button>
        <Link className="btn primary" to="/documents/upload"><UploadCloud size={16} />Upload document</Link>
        <Link className="btn" to="/reviews"><UserCheck size={16} />Open pending reviews</Link>
      </PageHead>
      {loading && !docs.length ? <LoadingState label="Loading documents" /> : error ? <ErrorState error={error} onRetry={reload} /> : docs.length === 0 ? (
        <EmptyState title="No documents yet" text="Upload your first document to see counts and activity here." to="/documents/upload" cta="Upload Documents" />
      ) : (
        <>
          <div className="grid cols-4">{cards.map(([l, n, Icon]) => <div className="card stat" key={l}><span className="lbl"><Icon size={18} aria-hidden="true" />{l}</span><span className="num">{n}</span></div>)}</div>
          <div className="grid two" style={{ marginTop: 16 }}>
            <div className="card"><div className="card-head"><h2>Recent documents</h2><Link to="/documents">View all</Link></div><DocumentTable docs={recent} compact /></div>
            <div className="card"><div className="card-head"><h2>Processing distribution</h2></div><Distribution docs={docs} /></div>
          </div>
        </>
      )}
    </>
  );
}
