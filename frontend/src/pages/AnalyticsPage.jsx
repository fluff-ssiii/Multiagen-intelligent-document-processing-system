import PageHead from '../components/common/PageHead';
import { LoadingState, ErrorState, EmptyState } from '../components/common/States';
import Distribution from '../components/documents/Distribution';
import { useDocuments } from '../hooks/useDocuments';
import { formatDate } from '../utils/formatDate';

export default function AnalyticsPage() {
  const { docs, loading, error, reload } = useDocuments();
  if (loading && !docs.length) return <><PageHead title="Analytics & Performance" /><LoadingState /></>;
  if (error) return <><PageHead title="Analytics & Performance" /><ErrorState error={error} onRetry={reload} /></>;
  if (!docs.length) return <><PageHead title="Analytics & Performance" /><EmptyState title="Nothing to analyze yet" text="Upload and process documents to see operational counts." to="/documents/upload" cta="Upload Documents" /></>;
  const n = docs.length; const c = (...k) => docs.filter((d) => k.includes(d.status)).length;
  const dates = docs.map((d) => new Date(d.uploadedAt).getTime()).filter(Number.isFinite);
  const range = dates.length ? `${formatDate(Math.min(...dates), false)} – ${formatDate(Math.max(...dates), false)}` : 'upload dates not reported';
  const rows = [['Total documents', n], ['Processed', c('processed', 'approved')], ['Pending review', c('needs_review')], ['Rejected', c('rejected')], ['Failed', c('failed')], ['Queued / processing', c('queued', 'processing')]];
  return (
    <>
      <PageHead title="Analytics & Performance" subtitle="Operational counts from your documents." />
      <div className="alert info" role="note"><div><b>Sample: {n} document{n === 1 ? '' : 's'} · {range}.</b>{n < 30 && ' This is a small sample; treat proportions with caution.'}</div></div>
      <div className="grid split">
        <div className="card"><h2 style={{ marginBottom: 14 }}>Operational counts</h2>
          <table><tbody>{rows.map(([l, v]) => <tr key={l}><td>{l}</td><td style={{ textAlign: 'right' }}><b>{v}</b> <span className="muted small">of {n}</span></td></tr>)}</tbody></table></div>
        <div className="card"><h2 style={{ marginBottom: 14 }}>Outcome distribution</h2><Distribution docs={docs} /></div>
      </div>
      <div className="card"><h2>Model evaluation metrics</h2>
        <p className="muted" style={{ marginTop: 6 }}>Field-extraction accuracy, validation accuracy and average processing time are not shown. They need ground-truth labels or an aggregate endpoint from the backend, and none is in the current API. The counts above describe workflow status, not model quality.</p></div>
    </>
  );
}
