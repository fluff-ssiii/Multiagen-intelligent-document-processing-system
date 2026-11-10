// Single place for configuration. Verify the UPLOAD_FIELDS names against the FastAPI route (/docs).
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
export const MAX_FILE_MB = Number(import.meta.env.VITE_MAX_FILE_MB || 25);
export const ACCEPTED_EXTENSIONS = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'jpg', 'jpeg', 'png'];
export const DOCUMENT_TYPES = ['General Document', 'Invoice', 'Contract', 'Receipt', 'Report', 'Form', 'Letter'];
// Multipart form-field names. Set a metadata field to null to stop sending it AND hide its control.
// Visibility is null on purpose: do not show it until the backend accepts and enforces it.
export const UPLOAD_FIELDS = { file: 'file', documentType: 'document_type', tags: 'tags', description: 'description', visibility: null };
