import { request, upload } from './apiClient';
import { UPLOAD_FIELDS as F } from '../config';
const enc = encodeURIComponent;

export const listDocuments = (signal) => request('/api/documents', { signal });
export const getDocument = (id, signal) => request(`/api/documents/${enc(id)}`, { signal });
export const getResults = (id, signal) => request(`/api/documents/${enc(id)}/results`, { signal });
export const processDocument = (id) => request(`/api/documents/${enc(id)}/process`, { method: 'POST' });

export function uploadDocument(file, meta = {}, onProgress) {
  const fd = new FormData();
  fd.append(F.file, file);
  if (F.documentType && meta.documentType) fd.append(F.documentType, meta.documentType);
  if (F.tags && meta.tags) fd.append(F.tags, meta.tags);
  if (F.description && meta.description) fd.append(F.description, meta.description);
  if (F.visibility && meta.visibility) fd.append(F.visibility, meta.visibility);
  return upload('/api/documents/upload', fd, onProgress);
}
