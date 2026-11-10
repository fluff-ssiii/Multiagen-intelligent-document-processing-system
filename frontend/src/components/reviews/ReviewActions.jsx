import { useState } from 'react';
import { Check, X } from 'lucide-react';
import ConfirmDialog from '../common/ConfirmDialog';

export default function ReviewActions({ filename, busy, onApprove, onReject }) {
  const [confirm, setConfirm] = useState(null);
  const run = async () => { const fn = confirm === 'approve' ? onApprove : onReject; const ok = await fn(); if (ok !== false) setConfirm(null); else setConfirm(null); };
  return (
    <>
      <div className="row-actions">
        <button className="btn success" disabled={busy} onClick={() => setConfirm('approve')}><Check size={18} />Approve</button>
        <button className="btn danger" disabled={busy} onClick={() => setConfirm('reject')}><X size={18} />Reject</button>
      </div>
      {confirm && (
        <ConfirmDialog title={confirm === 'approve' ? 'Approve this document?' : 'Reject this document?'} confirmLabel={confirm === 'approve' ? 'Approve' : 'Reject'} tone={confirm === 'approve' ? 'success' : 'danger'} busy={busy} onConfirm={run} onCancel={() => setConfirm(null)}>
          “{filename}” will be {confirm === 'approve' ? 'approved' : 'rejected'}. This decision is sent to the backend and cannot be undone from here.
        </ConfirmDialog>
      )}
    </>
  );
}
