export function LogoMark({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" aria-hidden>
      <defs>
        <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#5EEAD4" />
          <stop offset="1" stopColor="#14B8A6" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="14" fill="#0B0F16" stroke="rgba(148,163,184,0.18)" />
      <g fill="none" stroke="url(#lg)" strokeWidth="2.6" strokeLinecap="round">
        <path d="M32 14l14 8v16l-14 8-14-8V22z" />
        <ellipse cx="32" cy="30" rx="15" ry="5.5" opacity="0.75" transform="rotate(-18 32 30)" />
      </g>
      <circle cx="45" cy="24" r="3" fill="#5EEAD4" />
    </svg>
  )
}

export default function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <LogoMark />
      <span className="font-display text-lg font-600 tracking-tight text-white">
        Q-Pharm
        {!compact && (
          <span className="ml-2 hidden text-[10px] font-medium uppercase tracking-widest2 text-fog-500 lg:inline">
            Quantum Drug Repurposing
          </span>
        )}
      </span>
    </span>
  )
}
