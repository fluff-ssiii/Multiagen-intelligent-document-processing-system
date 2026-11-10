export function formatDate(v, withTime = true) {
  if (!v) return '—';
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return String(v);
  return withTime ? d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : d.toLocaleDateString([], { dateStyle: 'medium' });
}
export function elapsed(from, to = Date.now()) {
  const a = new Date(from).getTime(); if (!a) return null;
  const s = Math.max(0, Math.round((new Date(to).getTime() - a) / 1000));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}
