export default function PageHead({ title, subtitle, children }) {
  return <div className="page-head"><div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div><div className="row-actions">{children}</div></div>;
}
