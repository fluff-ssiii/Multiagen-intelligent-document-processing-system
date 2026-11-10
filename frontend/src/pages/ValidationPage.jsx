import { Link, useParams } from 'react-router-dom';
import { FileSearch } from 'lucide-react';
import PageHead from '../components/common/PageHead';
import { LoadingState, ErrorState, EmptyState } from '../components/common/States';
import ValidationIssues from '../components/validation/ValidationIssues';
import { useAsync } from '../hooks/useAsync';
import { getDocument, getResults } from '../services/documentApi';
import { normalizeDoc, splitResults, normalizeValidation } from '../services/adapters';

export default function ValidationPage() {
  const { documentId } = useParams();
  const doc = useAsync((s) => getDocument(documentId, s), [documentId]);
  const res = useAsync((s) => getResults(documentId, s), [documentId]);
  if (res.loading && !res.data) return <LoadingState label="Loading validation report" />;
  const noResults = res.error?.status === 404 || res.error?.status === 409;
  if (res.error && !noResults) return <ErrorState error={res.error} onRetry={res.reload} />;
  const d = doc.data ? normalizeDoc(doc.data) : null; const base = `/documents/${encodeURIComponent(documentId)}`;
  if (noResults) return <><PageHead title="Validation & Reports" subtitle={d?.filename} /><EmptyState icon={FileSearch} title="No validation report yet" text={res.error.message} to={`${base}/processing`} cta="Go to AI Processing" /></>;
  const { validation } = splitResults(res.data); const v = normalizeValidation(validation);
  return (
    <>
      <PageHead title="Validation & Reports" subtitle={d?.filename}>
        <Link className="btn" to={`${base}/results`}>Extraction results</Link>
        {d?.status === 'needs_review' && <Link className="btn primary" to={`/reviews?doc=${encodeURIComponent(documentId)}`}>Go to Human Review</Link>}
      </PageHead>
      {d?.reason && <div className="alert warn"><div><b>Review reason:</b> {String(d.reason)}</div></div>}
      <ValidationIssues validation={v} raw={validation} />
    </>
  );
}
