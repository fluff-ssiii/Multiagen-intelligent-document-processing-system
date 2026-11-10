import { Link } from 'react-router-dom';
import { Copy } from 'lucide-react';
import StatusBadge from '../common/StatusBadge';
import { formatDate } from '../../utils/formatDate';
import { hasResults, isActive } from '../../services/adapters';
import { useToast } from '../common/Toast';

export default function DocumentTable({ docs, onProcess, busyId, compact }) {
  const toast = useToast();
  const copy = (id) => navigator.clipboard?.writeText(id).then(() => toast('Document ID copied', 'success'), () => toast('Could not copy', 'error'));
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>File name</th>{!compact && <th>Document ID</th>}<th>Type</th><th>Uploaded</th>{!compact && <th>Updated</th>}<th>Status</th><th>Actions</th></tr></thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.id}>
              <td><Link to={`/documents/${encodeURIComponent(d.id)}`}><b>{d.filename}</b></Link></td>
              {!compact && <td><span className="mono">{d.id.length > 14 ? `${d.id.slice(0, 12)}…` : d.id}</span> <button className="btn ghost sm" aria-label={`Copy ID of ${d.filename}`} onClick={() => copy(d.id)}><Copy size={14} /></button></td>}
              <td>{d.type || '—'}</td><td>{formatDate(d.uploadedAt)}</td>{!compact && <td>{formatDate(d.updatedAt)}</td>}
              <td><StatusBadge status={d.status} raw={d.rawStatus} /></td>
              <td><div className="row-actions">
                <Link className="btn sm" to={`/documents/${encodeURIComponent(d.id)}`}>View</Link>
                {!compact && d.status === 'uploaded' && onProcess && <button className="btn sm primary" disabled={busyId === d.id} onClick={() => onProcess(d)}>{busyId === d.id ? 'Starting…' : 'Start processing'}</button>}
                {!compact && isActive(d.status) && <Link className="btn sm" to={`/documents/${encodeURIComponent(d.id)}/processing`}>Track</Link>}
                {!compact && hasResults(d.status) && <Link className="btn sm" to={`/documents/${encodeURIComponent(d.id)}/results`}>Results</Link>}
                {!compact && d.status === 'needs_review' && <Link className="btn sm" to={`/reviews?doc=${encodeURIComponent(d.id)}`}>Review</Link>}
              </div></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
