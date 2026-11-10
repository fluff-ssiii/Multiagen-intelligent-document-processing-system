import { Link } from 'react-router-dom';
import PageHead from '../components/common/PageHead';
import { LoadingState, ErrorState, EmptyState } from '../components/common/States';
import StatusBadge from '../components/common/StatusBadge';
import { useDocuments } from '../hooks/useDocuments';
import { formatDate } from '../utils/formatDate';

// Sidebar tabs for per-document views land here first so the user chooses which document to inspect.
export default function DocumentPickerPage({ section, title, subtitle }) {
  const { docs, loading, error, reload } = useDocuments();
  return (
    <>
      <PageHead title={title} subtitle={subtitle} />
      {loading && !docs.length ? <LoadingState /> : error ? <ErrorState error={error} onRetry={reload} /> : !docs.length ? (
        <EmptyState title="No documents yet" text="Upload a document first." to="/documents/upload" cta="Upload Documents" />
      ) : (
        <div className="card"><h2 style={{ marginBottom: 10 }}>Choose a document</h2>
          <div className="table-wrap"><table><thead><tr><th>File name</th><th>Uploaded</th><th>Status</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>
            {docs.map((d) => <tr key={d.id}><td><b>{d.filename}</b></td><td>{formatDate(d.uploadedAt)}</td><td><StatusBadge status={d.status} raw={d.rawStatus} /></td>
              <td><Link className="btn sm primary" to={`/documents/${encodeURIComponent(d.id)}/${section}`}>Open</Link></td></tr>)}
          </tbody></table></div></div>
      )}
    </>
  );
}
