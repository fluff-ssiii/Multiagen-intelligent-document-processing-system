import { API_BASE_URL } from '../config';

export class ApiError extends Error {
  constructor(message, { status, detail, network } = {}) {
    super(message);
    this.status = status; this.detail = detail; this.network = !!network;
  }
}

function describe(status, d) {
  const text = typeof d === 'string' ? d : Array.isArray(d)
    ? d.map((e) => `${(e.loc || []).filter((x) => x !== 'body').join('.') || 'request'}: ${e.msg}`).join('; ')
    : d && typeof d === 'object' ? (d.message || d.error || JSON.stringify(d)) : '';
  if (status === 404) return text || 'Not found.';
  if (status === 409) return text || 'Conflict: the document may already be processing or reviewed.';
  if (status === 422) return text ? `Validation failed — ${text}` : 'The server rejected the request data.';
  if (status >= 500) return `Server error (${status}). ${typeof d === 'string' && d.length < 200 ? d : 'Please try again.'}`;
  return text || `Request failed (${status}).`;
}

async function parse(res) {
  const text = await res.text();
  if (!text) return null;
  try { return JSON.parse(text); } catch { return text; }
}

// JSON / FormData requests. For FormData we never set Content-Type (the browser adds the boundary).
export async function request(path, { method = 'GET', body, signal } = {}) {
  const init = { method, signal, headers: { Accept: 'application/json' } };
  if (body instanceof FormData) init.body = body;
  else if (body !== undefined) { init.body = JSON.stringify(body); init.headers['Content-Type'] = 'application/json'; }
  let res;
  try { res = await fetch(API_BASE_URL + path, init); }
  catch (e) {
    if (e.name === 'AbortError') throw e;
    throw new ApiError(`Cannot reach the API at ${API_BASE_URL}. Check that the backend is running and CORS allows this origin.`, { network: true });
  }
  const data = await parse(res);
  if (!res.ok) {
    const detail = data && typeof data === 'object' && data.detail !== undefined ? data.detail : data;
    throw new ApiError(describe(res.status, detail), { status: res.status, detail });
  }
  return data;
}

// Multipart upload with real progress events (fetch cannot report upload progress).
export function upload(path, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', API_BASE_URL + path);
    xhr.setRequestHeader('Accept', 'application/json');
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(Math.round((e.loaded / e.total) * 100));
    xhr.onerror = () => reject(new ApiError(`Cannot reach the API at ${API_BASE_URL}.`, { network: true }));
    xhr.onload = () => {
      let data = null;
      try { data = xhr.responseText ? JSON.parse(xhr.responseText) : null; } catch { data = xhr.responseText; }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(data);
      const detail = data && typeof data === 'object' && data.detail !== undefined ? data.detail : data;
      reject(new ApiError(describe(xhr.status, detail), { status: xhr.status, detail }));
    };
    xhr.send(formData);
  });
}
