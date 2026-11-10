import { Menu } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { useApiHealth } from '../../hooks/useApiHealth';

const TITLES = [['/documents/upload', 'Upload Documents'], ['/processing', 'AI Processing'], ['/results', 'Extraction Results'], ['/validation', 'Validation & Reports'],
  ['/reviews', 'Human Review'], ['/analytics', 'Analytics & Performance'], ['/dashboard', 'Dashboard']];

function titleFor(p) {
  const hit = TITLES.find(([k]) => p.startsWith(k));
  if (hit) return hit[1];
  const m = p.match(/^\/documents\/[^/]+\/(processing|results|validation)$/);
  if (m) return `All Documents / Document / ${{ processing: 'AI Processing', results: 'Extraction Results', validation: 'Validation & Reports' }[m[1]]}`;
  return p.startsWith('/documents/') ? 'All Documents / Document details' : 'All Documents';
}

export default function Topbar({ onMenu }) {
  const { pathname } = useLocation();
  const { state, checkedAt, retry, detail } = useApiHealth();
  const label = { connected: 'Connected', disconnected: 'Disconnected', checking: 'Checking' }[state];
  return (
    <header className="topbar">
      <button className="btn ghost menu-btn" onClick={onMenu} aria-label="Open navigation"><Menu size={22} /></button>
      <div className="title">{titleFor(pathname)}</div>
      <button className="health" onClick={retry} title={`${detail || 'API health'}${checkedAt ? ` — last checked ${checkedAt.toLocaleTimeString()}` : ''}. Click to re-check.`} aria-label={`API ${label}. Re-check`}>
        <span className={`dot ${state}`} />API {label}
      </button>
    </header>
  );
}
