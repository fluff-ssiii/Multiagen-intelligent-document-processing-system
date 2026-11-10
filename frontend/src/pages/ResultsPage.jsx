import { Link, useParams } from 'react-router-dom';
import { Copy, Download } from 'lucide-react';
import PageHead from '../components/common/PageHead';
import { LoadingState, ErrorState, EmptyState, InlineAlert } from '../components/common/States';
import ExtractedFields from '../components/results/ExtractedFields';
import DocumentPreview from '../components/documents/DocumentPreview';
import { useAsync } from '../hooks/useAsync';
import { useToast } from '../components/common/Toast';
import { getDocument, getResults } from '../services/documentApi';
import { normalizeDoc, splitResults } from '../services/adapters';
import { downloadJson } from '../utils/downloadJson';
import { FileSearch } from 'lucide-react';

export default function ResultsPage() {
  const { documentId } = useParams(); const toast = useToast();
  const doc = useAsync((s) => getDocument(documentId, s), [documentId]);
  const res = useAsync((s) => getResults(documentId, s), [documentId]);
  if (res.loading && !res.data) return <LoadingState label="Loading extraction results" />;
  const noResults = res.error?.status === 404 || res.error?.status === 409;
  if (res.error && !noResults) return <ErrorState error={res.error} onRetry={res.reload} />;
  const d = doc.data ? normalizeDoc(doc.data) : null;
  const base = `/documents/${encodeURIComponent(documentId)}`;
  if (noResults) return <><PageHead title="Extraction Results" subtitle={d?.filename} /><EmptyState icon={FileSearch} title="No results yet" text={res.error.message} to={`${base}/processing`} cta="Go to AI Processing" /></>;
  const { extraction } = splitResults(res.data);
  const copy = () => navigator.clipboard?.writeText(JSON.stringify(extraction, null, 2)).then(() => toast('JSON copied', 'success'), () => toast('Could not copy', 'error'));
  return (
    <>
      <PageHead title="Extraction Results" subtitle={d?.filename}>
        <button className="btn" onClick={copy}><Copy size={16} />Copy JSON</button>
        <button className="btn" onClick={() => downloadJson(extraction, `${(d?.filename || documentId).replace(/\.[^.]+$/, '')}-extraction.json`)}><Download size={16} />Download JSON</button>
        <Link className="btn" to={`${base}/validation`}>Validation</Link>
      </PageHead>
      {!doc.data && doc.error && <InlineAlert kind="warn">Document metadata could not be loaded: {doc.error.message}</InlineAlert>}
      <div className="grid split">
        <div className="card"><h2 style={{ marginBottom: 14 }}>Source document</h2><DocumentPreview doc={d} /></div>
        <div className="card"><h2 style={{ marginBottom: 14 }}>Extracted fields</h2><ExtractedFields data={extraction} />
          <details style={{ marginTop: 16 }}><summary>Raw JSON</summary><pre className="json">{JSON.stringify(extraction, null, 2)}</pre></details></div>
      </div>
    </>
  );
}
