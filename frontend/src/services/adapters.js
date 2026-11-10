// Tolerant adapters. The backend schema was not supplied, so every field-name guess lives here.
// TODO: after checking /openapi.json, tighten the key lists below to the real field names.
export const pick = (o, keys) => {
  if (!o || typeof o !== 'object') return undefined;
  for (const k of keys) if (o[k] !== undefined && o[k] !== null) return o[k];
  return undefined;
};

export function listFrom(d) {
  if (Array.isArray(d)) return d;
  const inner = pick(d, ['documents', 'items', 'reviews', 'pending', 'results', 'data']);
  return Array.isArray(inner) ? inner : [];
}

// Maps whatever status string the backend returns to a display bucket. Stored values are never altered.
export function statusKey(s) {
  const v = String(s ?? '').toLowerCase();
  if (!v) return 'unknown';
  if (/fail|error/.test(v)) return 'failed';
  if (/reject/.test(v)) return 'rejected';
  if (/approv/.test(v)) return 'approved';
  if (/review/.test(v)) return 'needs_review';
  if (/queue|pending/.test(v)) return 'queued';
  if (/processed|complete|done|success/.test(v)) return 'processed';
  if (/process|running|progress/.test(v)) return 'processing';
  if (/upload/.test(v)) return 'uploaded';
  return 'unknown';
}

export const STATUS_META = {
  uploaded: { label: 'Uploaded', tone: 'gray' },
  queued: { label: 'Queued', tone: 'blue' },
  processing: { label: 'Processing', tone: 'blue' },
  processed: { label: 'Processed', tone: 'green' },
  needs_review: { label: 'Needs review', tone: 'amber' },
  approved: { label: 'Approved', tone: 'green' },
  rejected: { label: 'Rejected', tone: 'red' },
  failed: { label: 'Failed', tone: 'red' },
  unknown: { label: 'Unknown', tone: 'gray' },
};
export const isActive = (key) => key === 'queued' || key === 'processing';
export const hasResults = (key) => ['processed', 'needs_review', 'approved', 'rejected'].includes(key);

export function normalizeDoc(raw) {
  const r = raw && typeof raw === 'object' ? raw : { document_id: raw };
  const rawStatus = pick(r, ['status', 'processing_status', 'state']);
  const reason = pick(r, ['review_reason', 'reason', 'reasons', 'message']);
  const tags = pick(r, ['tags']);
  return {
    id: String(pick(r, ['document_id', 'id', '_id']) ?? ''),
    filename: pick(r, ['filename', 'file_name', 'original_filename', 'name']) ?? '(unnamed)',
    type: pick(r, ['document_type', 'doc_type', 'type']),
    fileType: pick(r, ['content_type', 'file_type', 'mime_type']),
    uploadedAt: pick(r, ['uploaded_at', 'created_at', 'upload_date', 'created']),
    updatedAt: pick(r, ['updated_at', 'last_updated', 'processed_at', 'modified_at']),
    rawStatus, status: statusKey(rawStatus),
    stage: pick(r, ['current_stage', 'stage', 'current_agent']),
    error: pick(r, ['error', 'error_message', 'failure_reason']),
    reason: Array.isArray(reason) ? reason.join('; ') : reason,
    description: pick(r, ['description']),
    tags: Array.isArray(tags) ? tags : typeof tags === 'string' && tags ? tags.split(',') : [],
    fileUrl: pick(r, ['file_url', 'url', 'download_url']),
    raw: r,
  };
}

const VALIDATION_KEYS = ['validation', 'validation_result', 'validation_results', 'validation_report'];
export function splitResults(r) {
  if (!r || typeof r !== 'object') return { extraction: r ?? null, validation: null };
  const validation = pick(r, VALIDATION_KEYS) ?? null;
  let extraction = pick(r, ['extraction', 'extracted_data', 'extracted_fields', 'extracted', 'fields']);
  if (extraction === undefined) {
    const rest = { ...r };
    VALIDATION_KEYS.forEach((k) => delete rest[k]);
    extraction = Object.keys(rest).length ? rest : null;
  }
  return { extraction, validation };
}

export function normalizeValidation(v) {
  if (v === null || v === undefined) return null;
  const issues = [];
  const add = (arr, sev) => (Array.isArray(arr) ? arr : []).forEach((i) => {
    if (typeof i === 'string') return issues.push({ message: i, severity: sev });
    if (!i || typeof i !== 'object') return;
    if (i.passed === true || i.valid === true || /^(pass|ok|valid)/i.test(String(i.status ?? ''))) return;
    issues.push({
      field: pick(i, ['field', 'field_name', 'name', 'check']),
      message: pick(i, ['message', 'issue', 'detail', 'description', 'error']) ?? JSON.stringify(i),
      severity: String(pick(i, ['severity', 'level']) ?? sev).toLowerCase(),
      expected: i.expected, actual: i.actual ?? i.found,
    });
  });
  if (Array.isArray(v)) add(v, 'error');
  else if (typeof v === 'object') {
    add(v.errors, 'error'); add(v.warnings, 'warning'); add(v.issues, 'error');
    add(v.checks, 'error'); add(v.failed_checks, 'error');
  }
  issues.forEach((i) => { i.blocking = /error|critical|fail|block|high/.test(i.severity); });
  let status = pick(v, ['status', 'validation_status', 'result', 'is_valid', 'valid']);
  if (typeof status === 'boolean') status = status ? 'valid' : 'invalid';
  return { status: status === undefined ? null : String(status), issues };
}
