/** Animated molecular motif used in the hero — pure SVG + CSS. */
export default function MoleculeHero() {
  return (
    <div className="relative mx-auto h-[420px] w-[420px] select-none md:h-[500px] md:w-[500px]" aria-hidden>
      {/* glow */}
      <div className="absolute inset-0 rounded-full bg-accent/5 blur-3xl" />

      {/* pulse rings */}
      <div className="absolute left-1/2 top-1/2 h-56 w-56 -translate-x-1/2 -translate-y-1/2 rounded-full border border-accent/20 animate-pulse-ring" />
      <div className="absolute left-1/2 top-1/2 h-56 w-56 -translate-x-1/2 -translate-y-1/2 rounded-full border border-quantum/20 animate-pulse-ring [animation-delay:1.5s]" />

      {/* orbit rings */}
      <svg viewBox="0 0 400 400" className="absolute inset-0 h-full w-full">
        <defs>
          <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#2DD4BF" stopOpacity="0.7" />
            <stop offset="0.5" stopColor="#8B7CF6" stopOpacity="0.35" />
            <stop offset="1" stopColor="#2DD4BF" stopOpacity="0.7" />
          </linearGradient>
        </defs>

        {/* static benzene cage */}
        <g transform="translate(200 200)" stroke="rgba(148,163,184,0.28)" strokeWidth="1">
          <path d="M0 -78 L67.5 -39 L67.5 39 L0 78 L-67.5 39 L-67.5 -39 Z" fill="rgba(13,18,28,0.85)" />
          <path d="M0 -78 L67.5 -39 L67.5 39 L0 78 L-67.5 39 L-67.5 -39 Z" stroke="url(#ringGrad)" strokeWidth="1.6" />
          <line x1="0" y1="-78" x2="0" y2="-38" />
          <line x1="67.5" y1="-39" x2="30" y2="-19" />
          <line x1="67.5" y1="39" x2="30" y2="19" />
          <line x1="0" y1="78" x2="0" y2="38" />
          <line x1="-67.5" y1="39" x2="-30" y2="19" />
          <line x1="-67.5" y1="-39" x2="-30" y2="-19" />
        </g>

        {/* inner hexagon vertices */}
        <g transform="translate(200 200)">
          {[
            [0, -78], [67.5, -39], [67.5, 39], [0, 78], [-67.5, 39], [-67.5, -39],
          ].map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r="4.5" fill="#0A0E16" stroke="#2DD4BF" strokeWidth="1.6" />
          ))}
        </g>

        {/* orbit 1 (electrons) */}
        <g className="animate-orbit-slow" style={{ transformOrigin: '200px 200px' }}>
          <ellipse cx="200" cy="200" rx="150" ry="56" fill="none" stroke="url(#ringGrad)" strokeWidth="1" transform="rotate(-16 200 200)" />
          <circle cx="350" cy="176" r="5" fill="#5EEAD4" />
          <circle cx="52" cy="226" r="3.5" fill="#8B7CF6" />
        </g>

        {/* orbit 2 */}
        <g className="animate-orbit-fast" style={{ transformOrigin: '200px 200px' }}>
          <ellipse cx="200" cy="200" rx="132" ry="118" fill="none" stroke="rgba(139,124,246,0.30)" strokeWidth="1" transform="rotate(64 200 200)" />
          <circle cx="252" cy="80" r="4" fill="#A99DFF" />
        </g>

        {/* dashed measurement ring */}
        <circle cx="200" cy="200" r="182" fill="none" stroke="rgba(148,163,184,0.14)" strokeWidth="1" strokeDasharray="3 7" />
      </svg>

      {/* floating data tags */}
      <div className="absolute left-2 top-16 hidden animate-fade-in md:block [animation-delay:0.6s]">
        <div className="panel-flat px-3 py-2 font-mono text-[11px] leading-tight text-fog-300">
          <span className="text-accent">ΔG</span> −8.42 kcal/mol
        </div>
      </div>
      <div className="absolute bottom-20 right-0 hidden animate-fade-in md:block [animation-delay:0.9s]">
        <div className="panel-flat px-3 py-2 font-mono text-[11px] leading-tight text-fog-300">
          <span className="text-quantum">VQE</span> E₀ = −0.4521 Eh
        </div>
      </div>
      <div className="absolute bottom-6 left-10 hidden animate-fade-in md:block [animation-delay:1.2s]">
        <div className="panel-flat px-3 py-2 font-mono text-[11px] leading-tight text-fog-300">
          <span className="text-amber-soft">ADMET</span> grade A · 0 violations
        </div>
      </div>
    </div>
  )
}
