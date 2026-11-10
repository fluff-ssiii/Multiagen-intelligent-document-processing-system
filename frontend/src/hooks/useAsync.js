import { useEffect, useRef, useState } from 'react';

// Fetch with AbortController cleanup. Optional polling that stops when stopWhen(data) is true,
// on error, or when the component unmounts.
export function useAsync(fn, deps = [], { poll = 0, stopWhen } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);
  const fnRef = useRef(fn); fnRef.current = fn;
  const stopRef = useRef(stopWhen); stopRef.current = stopWhen;
  useEffect(() => {
    const ac = new AbortController(); let timer;
    const run = async () => {
      try {
        const data = await fnRef.current(ac.signal);
        setState({ data, error: null, loading: false });
        if (poll && !(stopRef.current && stopRef.current(data))) timer = setTimeout(run, poll);
      } catch (e) {
        if (e.name === 'AbortError') return;
        setState((p) => ({ ...p, error: e, loading: false }));
      }
    };
    setState((p) => ({ ...p, loading: true, error: null }));
    run();
    return () => { ac.abort(); clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, poll, ...deps]);
  return { ...state, reload: () => setTick((t) => t + 1) };
}
