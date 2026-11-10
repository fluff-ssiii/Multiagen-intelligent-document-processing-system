import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { WifiOff } from 'lucide-react';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import { useApiHealth } from '../../hooks/useApiHealth';

export default function AppShell() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const { state, retry } = useApiHealth();
  useEffect(() => setOpen(false), [pathname]);
  return (
    <div className="shell">
      <Sidebar open={open} onNavigate={() => setOpen(false)} />
      <div className="main">
        <Topbar onMenu={() => setOpen(true)} />
        <main className="content">
          {state === 'disconnected' && (
            <div className="alert warn" role="status"><WifiOff size={18} /><div className="grow">The backend is not reachable. Actions that need the API will fail until it is back.</div><button className="btn sm" onClick={retry}>Retry</button></div>
          )}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
