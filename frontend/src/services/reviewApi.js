import { request } from './apiClient';
const enc = encodeURIComponent;
export const getPendingReviews = (signal) => request('/api/reviews/pending', { signal });
// No request body: the brief does not define one. Add it here only if /openapi.json requires it.
export const approveDocument = (id) => request(`/api/reviews/${enc(id)}/approve`, { method: 'POST' });
export const rejectDocument = (id) => request(`/api/reviews/${enc(id)}/reject`, { method: 'POST' });
