export default function Logo({ size = 32 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#5546E8" />
      <path d="M10 7h8l5 5v13H10z" fill="#fff" /><path d="M18 7v5h5" fill="#c9c4ff" />
      <circle cx="16" cy="19" r="2.2" fill="#5546E8" /><path d="M16 15v2M12.8 19h1M18.2 19h1" stroke="#5546E8" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}
