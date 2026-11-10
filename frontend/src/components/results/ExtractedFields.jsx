import { pick } from '../../services/adapters';

const isObj = (v) => v && typeof v === 'object' && !Array.isArray(v);
const label = (k) => String(k).replace(/_/g, ' ');

// Renders any JSON shape. Text is rendered through React (escaped), never as HTML.
function Value({ v }) {
  if (v === null || v === undefined || v === '') return <span className="null">Missing</span>;
  if (typeof v === 'boolean') return <>{v ? 'Yes' : 'No'}</>;
  if (Array.isArray(v)) return v.length === 0 ? <span className="muted">Empty list</span> : (
    <div>{v.map((it, i) => <div className="items" key={i}>{isObj(it) ? <Fields data={it} /> : <Value v={it} />}</div>)}</div>
  );
  if (isObj(v)) {
    const conf = pick(v, ['confidence', 'score']);
    const val = pick(v, ['value', 'text']);
    if (val !== undefined && Object.keys(v).every((k) => ['value', 'text', 'confidence', 'score', 'bbox', 'page'].includes(k)))
      return <><Value v={val} />{typeof conf === 'number' && <span className="badge gray" style={{ marginLeft: 8 }}>confidence {conf <= 1 ? `${(conf * 100).toFixed(1)}%` : conf}</span>}</>;
    return <Fields data={v} />;
  }
  return <>{String(v)}</>;
}

function Fields({ data }) {
  return (
    <dl className="kv">
      {Object.entries(data).map(([k, v]) => {
        const complex = Array.isArray(v) || (isObj(v) && !('value' in v));
        return complex ? (
          <div className="nested" key={k} style={{ gridColumn: '1/-1' }}><b style={{ textTransform: 'capitalize' }}>{label(k)}</b><Value v={v} /></div>
        ) : (<div style={{ display: 'contents' }} key={k}><dt style={{ textTransform: 'capitalize' }}>{label(k)}</dt><dd><Value v={v} /></dd></div>);
      })}
    </dl>
  );
}

export default function ExtractedFields({ data }) {
  if (data === null || data === undefined) return <p className="muted">The results contain no extracted data.</p>;
  if (!isObj(data)) return <Value v={data} />;
  return Object.keys(data).length ? <Fields data={data} /> : <p className="muted">No fields were extracted.</p>;
}
