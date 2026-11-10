import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { getHealth } from '../services/healthApi';

const Ctx = createContext({ state: 'checking', checkedAt: null, retry: () => {} });
export const useApiHealth = () => useContext(Ctx);

export function HealthProvider({ children }) {
  const [h, setH] = useState({ state: 'checking', checkedAt: null, detail: '' });
  const check = useCallback(async () => {
    setH((p) => ({ ...p, state: 'checking' }));
    try { await getHealth(); setH({ state: 'connected', checkedAt: new Date(), detail: '' }); }
    catch (e) { setH({ state: 'disconnected', checkedAt: new Date(), detail: e.message }); }
  }, []);
  useEffect(() => { check(); const t = setInterval(check, 30000); return () => clearInterval(t); }, [check]);
  return <Ctx.Provider value={{ ...h, retry: check }}>{children}</Ctx.Provider>;
}
