import { useEffect, useState } from 'react'
import {
  Atom,
  BookOpen,
  Dna,
  ExternalLink,
  Ruler,
  Sparkles,
  X,
} from 'lucide-react'
import type { Candidate } from '../../lib/api'
import { api } from '../../lib/api'
import MoleculeViewer from './MoleculeViewer'
import { gradeColor } from './ResultsTable'

const KIND_STYLE: Record<string, { label: string; cls: string }> = {
  hbond: { label: 'H-bond', cls: 'text-amber-soft border-amber-400/30 bg-amber-400/10' },
  hydrophobic: { label: 'Hydrophobic', cls: 'text-fog-300 border-line bg-ink-800' },
  aromatic: { label: 'π-stacking', cls: 'text-quantum-bright border-quantum/30 bg-quantum/10' },
  electrostatic: { label: 'Salt bridge', cls: 'text-sky-300 border-sky-400/30 bg-sky-400/10' },
}

function Metric({ label, value, unit }: { label: string; value: string | number; unit?: string }) {
  return (
    <div className="rounded-lg border border-line bg-ink-800 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-fog-600">{label}</div>
      <div className="tabular mt-0.5 font-mono text-[13px] text-fog-100">
        {value}
        {unit && <span className="ml-0.5 text-[10px] text-fog-500">{unit}</span>}
      </div>
    </div>
  )
}

function ScoreRow({ label, value, weight, color }: { label: string; value: number; weight: number; color: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-24 text-xs text-fog-400">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-700">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      <span className="tabular w-12 text-right font-mono text-[11px] text-fog-300">{value.toFixed(3)}</span>
      <span className="w-8 text-right font-mono text-[10px] text-fog-600">×{weight}</span>
    </div>
  )
}

export default function DrugDetail({
  candidate,
  jobId,
  pocketResidues,
  onClose,
}: {
  candidate: Candidate
  jobId: string
  pocketResidues: string[]
  onClose: () => void
}) {
  const [proteinText, setProteinText] = useState<string | null>(null)
  const [poseText, setPoseText] = useState<string | null>(null)
  const c = candidate
  const drug = c.drug

  useEffect(() => {
    let alive = true
    setProteinText(null)
    setPoseText(null)
    fetch(api.proteinUrl(jobId))
      .then((r) => (r.ok ? r.text() : Promise.reject()))
      .then((t) => alive && setProteinText(t))
      .catch(() => alive && setProteinText(null))
    fetch(api.poseUrl(jobId, c.rank))
      .then((r) => (r.ok ? r.text() : Promise.reject()))
      .then((t) => alive && setPoseText(t))
      .catch(() => alive && setPoseText(null))
    return () => {
      alive = false
    }
  }, [jobId, c.rank])

  const d = c.docking
  const a = c.admet
  const q = c.quantum

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-[620px] flex-col overflow-y-auto border-l border-line bg-ink-900 shadow-2xl animate-fade-in">
        {/* header */}
        <div className="sticky top-0 z-10 border-b border-line bg-ink-900/95 px-6 py-4 backdrop-blur">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2.5">
                <span className="tabular rounded-lg border border-accent/30 bg-accent/10 px-2 py-0.5 font-mono text-xs text-accent-bright">
                  #{c.rank}
                </span>
                <h2 className="font-display text-xl font-600 tracking-tight text-white">{drug.name}</h2>
              </div>
              <p className="mt-1 text-xs text-fog-500">
                {drug.drug_class}
                {drug.drugbank_id && <> · {drug.drugbank_id}</>} · originally for {drug.indication}
              </p>
            </div>
            <button
              onClick={onClose}
              className="rounded-lg border border-line p-1.5 text-fog-400 transition-colors hover:border-lineBright hover:text-white"
              aria-label="Close"
            >
              <X size={16} />
            </button>
          </div>
          {drug.known_repurposing && (
            <div className="mt-3 rounded-xl border border-accent/25 bg-accent/[0.06] px-3.5 py-2.5">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-accent-bright">
                <Sparkles size={13} /> Documented repurposing: {drug.known_repurposing.to}
              </div>
              <p className="mt-1 text-[11.5px] leading-relaxed text-fog-400">{drug.known_repurposing.note}</p>
            </div>
          )}
        </div>

        <div className="space-y-6 px-6 py-5">
          {/* 3D viewer */}
          <section>
            <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest2 text-fog-500">
              <Atom size={13} className="text-accent" /> Docked pose in binding pocket
            </h3>
            <div className="mt-3">
              <MoleculeViewer
                proteinText={proteinText}
                poseText={poseText}
                pocketResidues={pocketResidues}
                interactions={d.interactions}
                height={300}
              />
            </div>
          </section>

          {/* score breakdown */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-widest2 text-fog-500">
              Composite score · {c.scores.composite.toFixed(3)}
            </h3>
            <div className="mt-3 space-y-2 rounded-xl border border-line bg-ink-850 p-4">
              <ScoreRow label="Docking" value={c.scores.docking} weight={0.55} color="bg-accent" />
              <ScoreRow label="ADMET" value={c.scores.admet} weight={0.20} color="bg-emerald-400" />
              <ScoreRow label="Quantum" value={c.scores.quantum} weight={0.15} color="bg-quantum" />
              <ScoreRow label="ML drug-like" value={c.scores.ml} weight={0.10} color="bg-sky-400" />
            </div>
          </section>

          {/* docking numbers */}
          <section>
            <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest2 text-fog-500">
              <Ruler size={13} className="text-accent" /> Docking
            </h3>
            <div className="mt-3 grid grid-cols-3 gap-2">
              <Metric label="ΔG (empirical)" value={d.score.toFixed(1)} unit="kcal/mol" />
              <Metric label="Ligand efficiency" value={d.ligand_efficiency.toFixed(2)} />
              <Metric label="Placements" value={`${d.n_clash_free}/${d.n_placements}`} />
              <Metric label="VdW" value={d.components.vdw.toFixed(1)} />
              <Metric label="H-bonds" value={d.components.hbond.toFixed(1)} />
              <Metric label="Hydrophobic" value={d.components.hydrophobic.toFixed(1)} />
            </div>
          </section>

          {/* quantum */}
          <section>
            <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest2 text-fog-500">
              <Dna size={13} className="text-quantum" /> VQE quantum refinement
            </h3>
            {q.used && q.vqe ? (
              <div className="mt-3 space-y-3">
                <div className="grid grid-cols-3 gap-2">
                  <Metric label="ΔE interaction" value={q.delta_e_ev!.toFixed(3)} unit="eV" />
                  <Metric label="ΔE" value={q.delta_e_hartree!.toFixed(5)} unit="Eh" />
                  <Metric label="Contact" value={`${q.contact!.ligand_atom}···${q.contact!.protein_element}`} />
                  <Metric label="Distance" value={q.contact!.distance.toFixed(2)} unit="Å" />
                  <Metric label="Hopping t" value={q.params!.t.toFixed(4)} unit="Eh" />
                  <Metric label="VQE error" value={q.vqe.error_eh.toExponential(1)} unit="Eh" />
                </div>
                <div className="rounded-xl border border-quantum/25 bg-quantum/[0.06] px-4 py-3 font-mono text-[11.5px] leading-relaxed text-fog-300">
                  <span className="text-quantum-bright">
                    {q.vqe.n_qubits} qubits · {q.vqe.n_pauli_terms} Pauli terms · depth {q.vqe.ansatz_depth}
                  </span>
                  <br />
                  E<sub>VQE</sub> = {q.vqe.energy_eh.toFixed(6)} Eh vs E<sub>exact</sub> ={' '}
                  {q.vqe.exact_energy_eh.toFixed(6)} Eh · {q.vqe.iterations} iterations ·{' '}
                  {q.vqe.evaluations} circuit evaluations
                </div>
              </div>
            ) : (
              <p className="mt-3 rounded-xl border border-line bg-ink-850 px-4 py-3 text-xs text-fog-500">
                Not quantum-refined (outside the top-M poses of this run).
              </p>
            )}
          </section>

          {/* interactions */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-widest2 text-fog-500">
              Protein–ligand interactions
            </h3>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {d.interactions.length === 0 && (
                <span className="text-xs text-fog-600">No notable contacts recorded.</span>
              )}
              {d.interactions.map((it, i) => {
                const st = KIND_STYLE[it.kind] ?? KIND_STYLE.hydrophobic
                return (
                  <span key={i} className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] ${st.cls}`}>
                    {it.kind === 'aromatic' ? (
                      <>{it.protein} <span className="font-mono opacity-70">{it.distance.toFixed(1)}Å</span></>
                    ) : (
                      <>
                        <span className="font-mono">{it.ligand_atom}</span>···{it.protein}
                        <span className="font-mono opacity-70">{it.distance.toFixed(1)}Å</span>
                      </>
                    )}
                    <span className="text-[9px] uppercase tracking-wider opacity-60">{st.label}</span>
                  </span>
                )
              })}
            </div>
          </section>

          {/* ADMET */}
          {a && (
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-widest2 text-fog-500">
                ADMET profile
                <span className={`ml-2 inline-flex items-center rounded-md border px-2 py-0.5 font-mono text-[11px] ${gradeColor(a.grade)}`}>
                  grade {a.grade}
                </span>
              </h3>
              <div className="mt-3 grid grid-cols-4 gap-2">
                <Metric label="MW" value={a.mw} unit="Da" />
                <Metric label="logP" value={a.logp} />
                <Metric label="TPSA" value={a.tpsa} unit="Å²" />
                <Metric label="HBD / HBA" value={`${a.hbd}/${a.hba}`} />
                <Metric label="Rot. bonds" value={a.rotatable_bonds} />
                <Metric label="Lipinski viol." value={a.lipinski_violations} />
                <Metric label="Solubility" value={a.log_s_mg_ml.toFixed(1)} unit="mg/mL" />
                <Metric label="GI absorption" value={a.gi_absorption} />
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
                <span className={`rounded-md border px-2 py-0.5 ${a.veber_pass ? 'border-accent/30 bg-accent/10 text-accent-bright' : 'border-rose-400/30 bg-rose-400/10 text-rose-300'}`}>
                  Veber {a.veber_pass ? 'pass' : 'fail'}
                </span>
                <span className={`rounded-md border px-2 py-0.5 ${a.bbb_permeant ? 'border-quantum/30 bg-quantum/10 text-quantum-bright' : 'border-line bg-ink-800 text-fog-500'}`}>
                  BBB {a.bbb_permeant ? 'permeant' : 'non-permeant'}
                </span>
                {a.pains_alerts.map((p) => (
                  <span key={p} className="rounded-md border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 text-amber-soft">
                    alert: {p}
                  </span>
                ))}
              </div>
            </section>
          )}

          {/* links */}
          <section>
            <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest2 text-fog-500">
              <BookOpen size={13} className="text-accent" /> Evidence & references
            </h3>
            <div className="mt-3 space-y-2">
              {drug.drugbank_id && (
                <a
                  href={`https://go.drugbank.com/drugs/${drug.drugbank_id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-between rounded-xl border border-line bg-ink-850 px-4 py-2.5 text-sm text-fog-200 transition-colors hover:border-accent/40"
                >
                  DrugBank entry · {drug.drugbank_id}
                  <ExternalLink size={14} className="text-fog-500" />
                </a>
              )}
              <a
                href={`https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(drug.name)}+repurposing`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between rounded-xl border border-line bg-ink-850 px-4 py-2.5 text-sm text-fog-200 transition-colors hover:border-accent/40"
              >
                PubMed · {drug.name} repurposing literature
                <ExternalLink size={14} className="text-fog-500" />
              </a>
              <a
                href={`https://www.rcsb.org/ligand/${drug.drugbank_id || ''}`}
                target="_blank"
                rel="noreferrer"
                className={`flex items-center justify-between rounded-xl border border-line bg-ink-850 px-4 py-2.5 text-sm transition-colors ${drug.drugbank_id ? 'text-fog-200 hover:border-accent/40' : 'pointer-events-none text-fog-600'}`}
              >
                RCSB ligand page
                <ExternalLink size={14} className="text-fog-500" />
              </a>
            </div>
          </section>

          <p className="pb-2 text-[11px] leading-relaxed text-fog-600">
            Computational estimates only — hypothesis generation for research. Not medical
            evidence; not for clinical use.
          </p>
        </div>
      </aside>
    </div>
  )
}
