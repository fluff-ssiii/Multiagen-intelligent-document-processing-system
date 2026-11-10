import { useRef, useState } from 'react';
import { UploadCloud } from 'lucide-react';
import { ACCEPTED_EXTENSIONS } from '../../config';

export default function DocumentDropzone({ onFile, disabled }) {
  const input = useRef(null); const [drag, setDrag] = useState(false);
  const pick = (files) => files?.[0] && onFile(files[0], files.length > 1);
  const open = () => !disabled && input.current?.click();
  return (
    <div className={`dropzone ${drag ? 'drag' : ''}`} role="button" tabIndex={0} aria-label="Drop a file here or press Enter to browse" aria-disabled={disabled}
      onClick={open} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), open())}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); !disabled && pick(e.dataTransfer.files); }}>
      <div className="ico"><UploadCloud size={30} aria-hidden="true" /></div>
      <h2>Drag and drop a document here</h2>
      <p className="muted">or</p>
      <span className="btn primary" aria-hidden="true">Browse files</span>
      <p className="muted small">Supported: {ACCEPTED_EXTENSIONS.map((e) => e.toUpperCase()).join(', ')}</p>
      <input ref={input} type="file" hidden accept={ACCEPTED_EXTENSIONS.map((e) => `.${e}`).join(',')} onChange={(e) => { pick(e.target.files); e.target.value = ''; }} />
    </div>
  );
}
