import { useEffect, useRef } from 'react';
export default function ConfirmDialog({ title, children, confirmLabel, tone = 'primary', busy, onConfirm, onCancel }) {
  const ref = useRef(null);
  useEffect(() => { ref.current?.focus(); const k = (e) => e.key === 'Escape' && !busy && onCancel(); window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k); }, [busy, onCancel]);
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && !busy && onCancel()}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="dlg-t">
        <h2 id="dlg-t">{title}</h2><div className="muted" style={{ marginTop: 8 }}>{children}</div>
        <div className="actions">
          <button ref={ref} className="btn" onClick={onCancel} disabled={busy}>Cancel</button>
          <button className={`btn ${tone}`} onClick={onConfirm} disabled={busy}>{busy ? 'Working…' : confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}
