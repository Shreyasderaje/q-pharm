import {
  ArrowDownWideNarrow,
  BadgeCheck,
  CircleAlert,
  Download,
  FlaskConical,
} from 'lucide-react'
import type { Candidate } from '../../lib/api'

export function gradeColor(grade: string | undefined): string {
  switch (grade) {
    case 'A': return 'text-accent-bright border-accent/40 bg-accent/10'
    case 'B': return 'text-emerald-300 border-emerald-400/30 bg-emerald-400/10'
    case 'C': return 'text-amber-soft border-amber-400/30 bg-amber-400/10'
    case 'D': return 'text-rose-300 border-rose-400/30 bg-rose-400/10'
    default: return 'text-fog-400 border-line bg-ink-800'
  }
}

function CompositeBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-ink-700">
        <div
          className="h-full rounded-full bg-gradient-to-r from-accent-deep to-accent-bright"
          style={{ width: `${Math.round(value * 100)}%` }}
        />
      </div>
      <span className="tabular w-9 text-right font-mono text-xs text-fog-200">
        {value.toFixed(3)}
      </span>
    </div>
  )
}

export default function ResultsTable({
  candidates,
  selectedRank,
  onSelect,
  jobId,
}: {
  candidates: Candidate[]
  selectedRank: number | null
  onSelect: (c: Candidate) => void
  jobId: string
}) {
  return (
    <div>
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2 text-sm font-medium text-fog-200">
          <ArrowDownWideNarrow size={15} className="text-accent" />
          Ranked shortlist
          <span className="text-xs font-normal text-fog-500">
            ({candidates.length} candidates)
          </span>
        </div>
        <a
          href={`/api/jobs/${jobId}/export.csv`}
          className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs text-fog-300 transition-colors hover:border-accent/40 hover:text-accent"
        >
          <Download size={13} /> Export CSV
        </a>
      </div>

      <div className="mt-3 overflow-hidden rounded-2xl border border-line">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="bg-ink-800 text-[11px] uppercase tracking-wider text-fog-500">
              <th className="px-4 py-3 font-medium">#</th>
              <th className="px-4 py-3 font-medium">Drug</th>
              <th className="hidden px-4 py-3 font-medium md:table-cell">Class</th>
              <th className="px-4 py-3 font-medium">ΔG dock</th>
              <th className="hidden px-4 py-3 font-medium lg:table-cell">ΔE quantum</th>
              <th className="hidden px-4 py-3 font-medium sm:table-cell">ADMET</th>
              <th className="px-4 py-3 font-medium">Composite</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((c, i) => {
              const admet = c.admet
              const repurposed = !!c.drug.known_repurposing
              return (
                <tr
                  key={c.drug.id}
                  onClick={() => onSelect(c)}
                  className={`cursor-pointer border-t border-line transition-colors ${
                    selectedRank === c.rank
                      ? 'bg-accent/[0.07]'
                      : i % 2
                        ? 'bg-ink-850/60 hover:bg-ink-800'
                        : 'bg-ink-900/40 hover:bg-ink-800'
                  }`}
                >
                  <td className="tabular px-4 py-3 font-mono text-xs text-fog-500">{c.rank}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className={`font-medium ${c.docking.no_fit ? 'text-fog-500' : 'text-fog-50'}`}>{c.drug.name}</span>
                      {repurposed && (
                        <span title={`Previously approved for: ${c.drug.known_repurposing?.to}`}>
                          <BadgeCheck size={14} className="text-accent" />
                        </span>
                      )}
                      {c.docking.no_fit && (
                        <span title="The ligand could not be placed in this pocket without steric clashes">
                          <span className="rounded border border-rose-400/30 bg-rose-400/10 px-1.5 py-px text-[9.5px] font-medium uppercase tracking-wider text-rose-300">
                            no fit
                          </span>
                        </span>
                      )}
                    </div>
                    {c.drug.drugbank_id && (
                      <span className="font-mono text-[10.5px] text-fog-600">{c.drug.drugbank_id}</span>
                    )}
                  </td>
                  <td className="hidden max-w-[140px] truncate px-4 py-3 text-xs text-fog-400 md:table-cell">
                    {c.drug.drug_class}
                  </td>
                  <td className="tabular px-4 py-3 font-mono text-[13px] text-fog-100">
                    {c.docking.score.toFixed(1)}
                  </td>
                  <td className="hidden px-4 py-3 lg:table-cell">
                    {c.quantum.used ? (
                      <span className="tabular font-mono text-[13px] text-quantum-bright">
                        {c.quantum.delta_e_ev!.toFixed(2)} eV
                      </span>
                    ) : (
                      <span className="text-xs text-fog-600">—</span>
                    )}
                  </td>
                  <td className="hidden px-4 py-3 sm:table-cell">
                    {admet ? (
                      <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-[11px] ${gradeColor(admet.grade)}`}>
                        {admet.grade}
                        {admet.pains_alerts.length > 0 && <CircleAlert size={11} />}
                      </span>
                    ) : (
                      <span className="text-xs text-fog-600">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <CompositeBar value={c.scores.composite} />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-3 flex items-start gap-1.5 px-1 text-[11px] leading-relaxed text-fog-600">
        <FlaskConical size={12} className="mt-0.5 shrink-0 text-fog-500" />
        ΔG is an empirical docking estimate (kcal/mol, more negative = better). ΔE is the
        VQE charge-transfer stabilization of the strongest polar contact. Click any row for
        the 3D pose, interaction map and full profile. Verified-repurposing history is marked
        with a check.
      </p>
    </div>
  )
}
