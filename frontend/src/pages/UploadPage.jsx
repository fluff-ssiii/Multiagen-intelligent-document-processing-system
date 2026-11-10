import { useState } from 'react';
import { Link } from 'react-router-dom';
import { FileText, Trash2, CheckCircle2 } from 'lucide-react';
import PageHead from '../components/common/PageHead';
import { InlineAlert } from '../components/common/States';
import DocumentDropzone from '../components/documents/DocumentDropzone';
import { useToast } from '../components/common/Toast';
import { uploadDocument } from '../services/documentApi';
import { normalizeDoc } from '../services/adapters';
import { ACCEPTED_EXTENSIONS, DOCUMENT_TYPES, MAX_FILE_MB, UPLOAD_FIELDS as F } from '../config';
import { formatFileSize } from '../utils/formatFileSize';

export default function UploadPage() {
  const toast = useToast();
  const [file, setFile] = useState(null);
  const [problem, setProblem] = useState('');
  const [meta, setMeta] = useState({ documentType: DOCUMENT_TYPES[0], visibility: 'Private', tags: '', description: '' });
  const [progress, setProgress] = useState(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);
  const set = (k) => (e) => setMeta((m) => ({ ...m, [k]: e.target.value }));

  const choose = (f, multi) => {
    setDone(null); setProblem('');
    const ext = f.name.split('.').pop().toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(ext)) return setProblem(`“.${ext}” files are not supported. Use: ${ACCEPTED_EXTENSIONS.join(', ')}.`);
    if (f.size === 0) return setProblem('That file is empty.');
    if (f.size > MAX_FILE_MB * 1048576) return setProblem(`File is ${formatFileSize(f.size)}; the limit is ${MAX_FILE_MB} MB.`);
    setFile(f);
    if (multi) setProblem('Only one file can be uploaded at a time. Using the first file.');
  };

  const submit = async () => {
    if (!file) return setProblem('Choose a file to upload.');
    setBusy(true); setProblem(''); setProgress(0);
    try {
      const res = await uploadDocument(file, meta, setProgress);
      const doc = normalizeDoc(res?.document ?? res);
      setDone({ id: doc.id, name: file.name, message: res?.message });
      setFile(null); toast('Upload confirmed by server', 'success');
    } catch (e) { setProblem(e.message); } finally { setBusy(false); setProgress(null); }
  };

  return (
    <>
      <PageHead title="Upload Documents" subtitle="Add a document, then start AI processing when you’re ready." />
      <div className="grid two">
        <div className="card">
          {done && (
            <InlineAlert kind="ok">
              <b><CheckCircle2 size={16} style={{ verticalAlign: -3 }} /> “{done.name}” uploaded.</b>
              {done.message && <p>{String(done.message)}</p>}
              {done.id ? <div className="row-actions" style={{ marginTop: 10 }}>
                <Link className="btn sm" to={`/documents/${encodeURIComponent(done.id)}`}>View document</Link>
                <Link className="btn sm primary" to={`/documents/${encodeURIComponent(done.id)}/processing`}>Start processing</Link></div>
                : <p>The response had no document ID. <Link to="/documents">Open All Documents</Link> to find it.</p>}
            </InlineAlert>
          )}
          {problem && <InlineAlert kind="error">{problem}</InlineAlert>}
          <DocumentDropzone onFile={choose} disabled={busy} />
          {file && (
            <div className="file-row">
              <FileText size={28} color="#5546e8" aria-hidden="true" />
              <div className="meta"><div className="name">{file.name}</div><div className="muted small">{formatFileSize(file.size)} · {file.type || file.name.split('.').pop().toUpperCase()}</div>
                {busy && <div className="progress" role="progressbar" aria-valuenow={progress ?? 0} aria-valuemin="0" aria-valuemax="100"><i style={{ width: `${progress ?? 0}%` }} /></div>}
                {busy && <div className="small muted" aria-live="polite">Uploading… {progress}%</div>}</div>
              <button className="btn ghost sm" onClick={() => setFile(null)} disabled={busy} aria-label="Remove selected file"><Trash2 size={16} />Remove</button>
            </div>
          )}
        </div>
        <div>
          <div className="card">
            <h2 style={{ marginBottom: 14 }}>Document details</h2>
            {F.documentType && <div className="field"><label htmlFor="dt">Document type</label>
              <select id="dt" className="input" value={meta.documentType} onChange={set('documentType')} disabled={busy}>{DOCUMENT_TYPES.map((t) => <option key={t}>{t}</option>)}</select></div>}
            {F.visibility && <fieldset className="field" style={{ border: 0, padding: 0 }}><legend>Visibility</legend>
              <div className="radio-row">{['Private', 'Team Only', 'Public'].map((v) => <label key={v}><input type="radio" name="vis" checked={meta.visibility === v} onChange={() => setMeta((m) => ({ ...m, visibility: v }))} />{v}</label>)}</div></fieldset>}
            {F.tags && <div className="field"><label htmlFor="tg">Tags</label><input id="tg" className="input" placeholder="e.g. finance, Q3" value={meta.tags} onChange={set('tags')} disabled={busy} /></div>}
            {F.description && <div className="field"><label htmlFor="ds">Description</label><textarea id="ds" className="input" value={meta.description} onChange={set('description')} disabled={busy} /></div>}
            <button className="btn primary" style={{ width: '100%' }} onClick={submit} disabled={busy || !file}>{busy ? 'Uploading…' : 'Upload Document'}</button>
          </div>
          <div className="card"><h3>Before you upload</h3>
            <p className="muted small" style={{ marginTop: 6 }}>One file at a time, up to {MAX_FILE_MB} MB. Uploading does not start processing — you start it separately. Documents may contain sensitive information; they are sent only to your configured backend.</p></div>
        </div>
      </div>
    </>
  );
}
