import { createContext, useCallback, useContext, useState } from 'react';
const Ctx = createContext(() => {});
export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((message, kind = 'info') => {
    const id = Math.random().toString(36).slice(2);
    setItems((p) => [...p, { id, message, kind }]);
    setTimeout(() => setItems((p) => p.filter((t) => t.id !== id)), 5000);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">{items.map((t) => <div key={t.id} className={`toast ${t.kind}`}>{t.message}</div>)}</div>
    </Ctx.Provider>
  );
}
