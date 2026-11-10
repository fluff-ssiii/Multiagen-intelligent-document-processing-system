import { NavLink } from 'react-router-dom';
import { LayoutDashboard, UploadCloud, Files, Cpu, ScanText, ShieldCheck, UserCheck, BarChart3 } from 'lucide-react';
import Logo from '../common/Logo';

export const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/documents/upload', label: 'Upload Documents', icon: UploadCloud, cls: 'upload-tab' },
  { to: '/documents', label: 'All Documents', icon: Files, end: true },
  { to: '/processing', label: 'AI Processing', icon: Cpu, match: '/processing' },
  { to: '/results', label: 'Extraction Results', icon: ScanText, match: '/results' },
  { to: '/validation', label: 'Validation & Reports', icon: ShieldCheck, match: '/validation' },
  { to: '/reviews', label: 'Human Review', icon: UserCheck },
  { to: '/analytics', label: 'Analytics & Performance', icon: BarChart3 },
];

export default function Sidebar({ open, onNavigate }) {
  return (
    <>
      <aside className={`sidebar ${open ? 'open' : ''}`} aria-label="Main navigation">
        <div className="brand"><Logo />The Doxor</div>
        <div className="brand-tag">Intelligent Documents. Smarter Workflows.</div>
        <nav className="nav">
          {NAV.map(({ to, label, icon: Icon, cls, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => `${cls || ''} ${isActive ? 'active' : ''}`} onClick={onNavigate}>
              <Icon size={19} aria-hidden="true" />{label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className={`scrim ${open ? 'open' : ''}`} onClick={onNavigate} />
    </>
  );
}
