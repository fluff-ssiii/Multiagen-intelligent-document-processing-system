import { useMemo } from 'react';
import { useAsync } from './useAsync';
import { listDocuments } from '../services/documentApi';
import { listFrom, normalizeDoc } from '../services/adapters';

export function useDocuments() {
  const q = useAsync((s) => listDocuments(s));
  const docs = useMemo(() => listFrom(q.data).map(normalizeDoc), [q.data]);
  return { ...q, docs };
}
