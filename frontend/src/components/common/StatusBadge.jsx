import { CheckCircle2, Clock, Loader2, AlertTriangle, XCircle, CircleDot, HelpCircle } from 'lucide-react';
import { STATUS_META } from '../../services/adapters';
const ICONS = { green: CheckCircle2, amber: AlertTriangle, red: XCircle, blue: Loader2, gray: CircleDot };

export default function StatusBadge({ status, raw }) {
  const m = STATUS_META[status] || STATUS_META.unknown;
  const Icon = status === 'queued' ? Clock : status === 'unknown' ? HelpCircle : ICONS[m.tone];
  return (
    <span className={`badge ${m.tone}`} title={raw ? `Backend status: ${raw}` : undefined}>
      <Icon size={14} aria-hidden="true" />{status === 'unknown' && raw ? String(raw) : m.label}
    </span>
  );
}
