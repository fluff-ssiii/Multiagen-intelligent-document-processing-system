import { Link } from 'react-router-dom';
import { AlertCircle, Inbox, SearchX, WifiOff, RefreshCw } from 'lucide-react';

export function LoadingState({ label = 'Loading…', rows = 4 }) {
  return (
    <div className="card" role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }).map((_, i) => <div key={i} className="skeleton" style={{ width: `${95 - i * 9}%` }} />)}
    </div>
  );
}

export function ErrorState({ error, onRetry, title = 'Something went wrong' }) {
  if (error?.status === 404) return <NotFound />;
  const Icon = error?.network ? WifiOff : AlertCircle;
  return (
    <div className="card state" role="alert">
      <Icon size={36} color="#b4232f" aria-hidden="true" />
      <h3>{error?.network ? 'Backend unreachable' : title}</h3>
      <p>{error?.message || 'Unknown error.'}</p>
      {onRetry && <button className="btn" onClick={onRetry}><RefreshCw size={16} />Try again</button>}
    </div>
  );
}

export function EmptyState({ title, text, to, cta, icon: Icon = Inbox }) {
  return (
    <div className="card state">
      <Icon size={36} aria-hidden="true" /><h3>{title}</h3>{text && <p>{text}</p>}
      {to && <Link className="btn primary" to={to}>{cta}</Link>}
    </div>
  );
}

export function NotFound({ what = 'document' }) {
  return <EmptyState icon={SearchX} title={`That ${what} was not found`} text="It may have been removed, or the ID is wrong." to="/documents" cta="Back to All Documents" />;
}

export function InlineAlert({ kind = 'error', children, action }) {
  return <div className={`alert ${kind}`} role={kind === 'error' ? 'alert' : 'status'}><div className="grow">{children}</div>{action}</div>;
}
