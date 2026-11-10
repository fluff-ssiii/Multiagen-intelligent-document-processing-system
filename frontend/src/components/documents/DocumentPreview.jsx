import { FileQuestion } from 'lucide-react';

// Only previews when the backend returns an absolute http(s) file URL on the document.
// No file endpoint exists in the API contract, so otherwise we show an honest fallback.
export default function DocumentPreview({ doc }) {
  const url = doc?.fileUrl;
  const safe = typeof url === 'string' && /^https?:\/\//i.test(url);
  if (!safe) return <div className="preview"><div><FileQuestion size={32} aria-hidden="true" /><p><b>Preview not available</b></p><p className="muted small">The API contract has no file endpoint and this document has no file URL.</p></div></div>;
  const isImg = /\.(png|jpe?g|gif|webp)(\?|$)/i.test(url);
  return <div className="preview">{isImg ? <img src={url} alt={`Preview of ${doc.filename}`} loading="lazy" /> : <iframe src={url} title={`Preview of ${doc.filename}`} loading="lazy" sandbox="" />}</div>;
}
