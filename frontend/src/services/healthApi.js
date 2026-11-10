import { request } from './apiClient';
export const getHealth = (signal) => request('/api/health', { signal });
