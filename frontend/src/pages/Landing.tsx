import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Boxes,
  Database,
  FlaskConical,
  Globe2,
  HeartPulse,
  Landmark,
  Orbit,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Workflow,
} from 'lucide-react'
import Nav from '../components/Nav'
import Footer from '../components/Footer'
import Reveal from '../components/Reveal'
import MoleculeHero from '../components/MoleculeHero'

const PIPELINE = [
  {
    icon: Database,
    step: '01',
    title: 'Target acquisition',
    body: 'Fetch any structure from the RCSB Protein Data Bank by ID, upload a PDB file, or start from one of ten curated disease targets — from SARS-CoV-2 protease to malaria DHFR.',
  },
  {
    icon: ScanSearch,
    step: '02',
    title: 'Pocket & pharmacophore',
    body: 'The engine locates the binding cavity — via the co-crystallized ligand or geometric cavity detection — and types every pocket atom into donors, acceptors, hydrophobes and aromatic rings.',
  },
  {
    icon: Workflow,
    step: '03',
    title: 'Quantum-classical docking',
    body: 'Thousands of ligand placements are scored with an empirical LUDI-style function (H-bonds, hydrophobic contacts, electrostatics, stacking), then the top poses are refined with VQE on a 4-qubit Hamiltonian.',
  },
  {
    icon: ShieldCheck,
    step: '04',
    title: 'ADMET & ML re-ranking',
    body: 'Survivors pass Lipinski, Veber and PAINS filters, are scored by a classical ML drug-likeness model, and are fused into a single transparent composite ranking with literature evidence.',
  },
]

const IMPACT = [
  {
    icon: HeartPulse,
    title: 'Pandemic preparedness',
    body: 'The next outbreak response should take weeks, not years. Remdesivir — a repurposed Ebola drug — was COVID-19\'s first authorized therapy. Q-Pharm automates that search for whatever comes next.',
  },
  {
    icon: Globe2,
    title: 'Neglected tropical diseases',
    body: 'Malaria, dengue and kala-azar kill hundreds of thousands a year, yet attract almost no commercial drug discovery. Repurposing approved drugs is the only economically viable path.',
  },
  {
    icon: Landmark,
    title: 'Open access, worldwide',
    body: 'No licenses, no fees, no supercomputer. A laptop runs the full pipeline — putting serious screening capacity in the hands of researchers in India, Africa and everywhere pharma capital rarely goes.',
  },
]

const TECH = [
  ['Qiskit 2.x', 'VQE + Jordan-Wigner mapping'],
  ['RDKit 2026', 'Cheminformatics & conformers'],
  ['FastAPI', 'Async screening API'],
  ['React 18', 'Console & visualization'],
  ['3Dmol.js', 'WebGL molecular viewer'],
  ['NumPy / SciPy', 'Sampling & optimization'],
  ['RCSB PDB', 'Live structure fetching'],
  ['PubChem', 'Validated drug structures'],
]

export default function Landing() {
  return (
    <div className="min-h-screen bg-ink-950">
      <Nav />

      {/* ============================== HERO ============================== */}
      <section className="relative overflow-hidden pt-16">
        <div className="absolute inset-0 bg-grid" />
        <div className="absolute inset-0 glow-accent" />
        <div className="relative mx-auto grid max-w-7xl items-center gap-12 px-6 pb-20 pt-16 md:pt-24 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="animate-fade-up">
            <div className="inline-flex items-center gap-2 rounded-full border border-accent/25 bg-accent/5 px-3.5 py-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-accent animate-blink" />
              <span className="text-[11px] font-medium uppercase tracking-widest2 text-accent-bright">
                Quantum-accelerated drug repurposing
              </span>
            </div>

            <h1 className="mt-6 font-display text-5xl font-700 leading-[1.04] tracking-tightest text-white md:text-[64px]">
              Tomorrow's cures are
              <br />
              already on the shelf.
              <span className="mt-3 block text-2xl font-500 leading-snug text-fog-400 md:text-[26px]">
                We just never tested them against{' '}
                <span className="text-gradient font-600">this disease.</span>
              </span>
            </h1>

            <p className="mt-6 max-w-xl text-[15px] leading-relaxed text-fog-400 md:text-base">
              Q-Pharm screens FDA-approved drugs against new disease targets using
              quantum-refined molecular docking. A pipeline that took a lab, a cluster and
              a licensing budget now runs from a single browser tab — free and open.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Link to="/platform" className="btn-primary">
                Run a screening
                <ArrowRight size={16} strokeWidth={2.2} />
              </Link>
              <a href="#quantum" className="btn-ghost">
                <Orbit size={16} className="text-quantum" />
                See the quantum core
              </a>
            </div>

            <div className="mt-10 flex flex-wrap gap-x-7 gap-y-2 text-xs text-fog-500">
              <span className="flex items-center gap-1.5"><i className="h-1 w-1 rounded-full bg-accent" />294 validated drug structures</span>
              <span className="flex items-center gap-1.5"><i className="h-1 w-1 rounded-full bg-accent" />4-qubit VQE refinement</span>
              <span className="flex items-center gap-1.5"><i className="h-1 w-1 rounded-full bg-accent" />Minutes per screen, not months</span>
            </div>
          </div>

          <div className="animate-fade-in [animation-delay:0.25s]">
            <MoleculeHero />
          </div>
        </div>

        {/* stats band */}
        <div className="relative border-y border-line bg-ink-900/60">
          <div className="mx-auto grid max-w-7xl grid-cols-2 divide-x divide-line px-6 md:grid-cols-4">
            {[
              ['$2.6B', 'average cost to bring one new drug to market'],
              ['12–15 yrs', 'typical discovery-to-approval timeline'],
              ['~90%', 'of drug candidates fail in clinical trials'],
              ['1,500+', 'approved drugs awaiting re-testing against new targets'],
            ].map(([big, small]) => (
              <div key={big} className="px-4 py-7 text-center md:px-8">
                <div className="font-display text-2xl font-600 tracking-tight text-white md:text-3xl">{big}</div>
                <div className="mx-auto mt-1.5 max-w-[220px] text-[11.5px] leading-snug text-fog-500">{small}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ============================ PROBLEM ============================= */}
      <section className="mx-auto max-w-7xl px-6 py-24">
        <div className="grid items-center gap-14 lg:grid-cols-2">
          <Reveal>
            <span className="eyebrow">The problem</span>
            <h2 className="mt-4 font-display text-3xl font-600 tracking-tight text-white md:text-4xl">
              The drugs exist.
              <br />
              The connections don't — <span className="text-fog-500">yet.</span>
            </h2>
            <p className="mt-5 text-[15px] leading-relaxed text-fog-400">
              Thousands of approved molecules have already passed safety testing that took a
              decade each. When a new disease appears, one of them may bind its target
              perfectly — but simulating how 1,500 candidates fit into a single protein
              pocket has always demanded months of specialized computation.
            </p>
            <p className="mt-4 text-[15px] leading-relaxed text-fog-400">
              So we guess. We screen a handful of candidates, miss most of the shelf, and
              the life-saving combination goes undiscovered. COVID-19 proved how costly
              that blindness is — and how valuable a shortcut would be.
            </p>
          </Reveal>

          <Reveal delay={120}>
            <div className="panel relative overflow-hidden p-8">
              <div className="absolute inset-0 bg-dots opacity-60" />
              <div className="relative">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium uppercase tracking-widest2 text-fog-500">
                    The re-testing matrix
                  </span>
                  <span className="chip !py-0.5 text-[10px]">
                    <FlaskConical size={11} className="text-accent" /> live example
                  </span>
                </div>

                {/* matrix visual: diseases x drugs */}
                <div className="mt-6 space-y-2.5">
                  {[
                    { disease: 'COVID-19', hit: 'Remdesivir', prev: 'Ebola' },
                    { disease: 'Erectile dysfunction', hit: 'Sildenafil', prev: 'Angina' },
                    { disease: 'Multiple myeloma', hit: 'Thalidomide', prev: 'Sedative' },
                    { disease: 'Alopecia', hit: 'Minoxidil', prev: 'Hypertension' },
                  ].map((row, i) => (
                    <div
                      key={row.disease}
                      className="flex items-center justify-between gap-3 rounded-lg border border-line bg-ink-800/80 px-4 py-3"
                      style={{ animationDelay: `${i * 90}ms` }}
                    >
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-fog-100">{row.disease}</div>
                        <div className="text-[11px] text-fog-600">originally for {row.prev}</div>
                      </div>
                      <div className="flex items-center gap-2 whitespace-nowrap">
                        <div className="h-px w-8 bg-gradient-to-r from-transparent to-accent/60" />
                        <span className="rounded-md border border-accent/30 bg-accent/10 px-2 py-1 font-mono text-[11px] text-accent-bright">
                          {row.hit}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                <p className="mt-6 text-xs leading-relaxed text-fog-600">
                  Every row was found the hard way — by luck, side-effect reports or heroic
                  intuition. Q-Pharm's job is to make these rows findable by computation,
                  before the next crisis starts.
                </p>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ============================ PIPELINE ============================ */}
      <section id="pipeline" className="border-y border-line bg-ink-900/40 py-24">
        <div className="mx-auto max-w-7xl px-6">
          <Reveal className="max-w-2xl">
            <span className="eyebrow">How it works</span>
            <h2 className="mt-4 font-display text-3xl font-600 tracking-tight text-white md:text-4xl">
              A screening pipeline in four moves
            </h2>
            <p className="mt-4 text-[15px] leading-relaxed text-fog-400">
              From a PDB ID to a ranked, evidence-linked shortlist — every stage transparent,
              every score inspectable.
            </p>
          </Reveal>

          <div className="mt-12 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            {PIPELINE.map((p, i) => (
              <Reveal key={p.step} delay={i * 90}>
                <div className="panel group relative h-full overflow-hidden p-6 transition-colors duration-300 hover:border-accent/30">
                  <div className="absolute -right-4 -top-6 font-display text-[88px] font-700 leading-none text-fog-100/[0.04] transition-colors group-hover:text-accent/10">
                    {p.step}
                  </div>
                  <div className="relative">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-accent/25 bg-accent/10 text-accent">
                      <p.icon size={19} strokeWidth={1.8} />
                    </div>
                    <h3 className="mt-5 font-display text-lg font-600 text-white">{p.title}</h3>
                    <p className="mt-2.5 text-[13.5px] leading-relaxed text-fog-400">{p.body}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>

          <Reveal delay={200}>
            <div className="mt-10 flex flex-wrap items-center gap-x-8 gap-y-3 rounded-2xl border border-line bg-ink-850 px-6 py-5">
              <span className="flex items-center gap-2 text-sm text-fog-300">
                <Sparkles size={15} className="text-accent" /> Composite ranking
              </span>
              <span className="font-mono text-xs text-fog-500">
                S = 0.55·docking + 0.20·ADMET + 0.15·quantum + 0.10·ML
              </span>
              <span className="ml-auto text-xs text-fog-600">
                weights are explicit — no black box
              </span>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ============================ QUANTUM ============================= */}
      <section id="quantum" className="relative overflow-hidden py-24">
        <div className="absolute inset-0 glow-quantum" />
        <div className="relative mx-auto grid max-w-7xl items-center gap-14 px-6 lg:grid-cols-[1fr_1.1fr]">
          <Reveal>
            <span className="eyebrow !text-quantum">The quantum core</span>
            <h2 className="mt-4 font-display text-3xl font-600 tracking-tight text-white md:text-4xl">
              Where classical docking
              <br />
              stops, VQE starts.
            </h2>
            <p className="mt-5 text-[15px] leading-relaxed text-fog-400">
              Classical scoring treats electrons as invisible. But binding is an electronic
              event: charge sloshing between the drug and the protein across a hydrogen bond.
              Q-Pharm extracts the strongest polar contact of each top-ranked pose and maps
              it onto a two-site Hubbard Hamiltonian — four orbitals, four qubits.
            </p>
            <p className="mt-4 text-[15px] leading-relaxed text-fog-400">
              A variational quantum eigensolver, running on Qiskit's statevector simulator
              with a hardware-efficient ansatz and parameter-shift gradient optimization,
              computes the
              ground-state charge-transfer stabilization of that contact. The result becomes
              a quantum correction to the classical score.
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              {['Jordan-Wigner mapping', '4 qubits · 16 Pauli terms', 'parameter-shift gradients', 'Statevector backend', 'Exact-diagonalization validated'].map((c) => (
                <span key={c} className="chip !border-quantum/25 !bg-quantum/10 !text-quantum-bright">{c}</span>
              ))}
            </div>
          </Reveal>

          <Reveal delay={140}>
            <div className="panel overflow-hidden">
              <div className="border-b border-line bg-ink-800/70 px-6 py-3">
                <span className="font-mono text-xs text-fog-500">
                  quantum.py — effective two-site Hamiltonian
                </span>
              </div>
              <div className="p-6 font-mono text-[13px] leading-loose">
                <div className="text-fog-500"># the model</div>
                <div className="text-fog-100">
                  H = −t Σ<sub className="text-fog-500">σ</sub> (c†<sub className="text-fog-500">1σ</sub>c<sub className="text-fog-500">2σ</sub> + h.c.)
                </div>
                <div className="pl-12 text-fog-100">
                  + U Σ<sub className="text-fog-500">σ</sub> n<sub className="text-fog-500">1σ</sub>n<sub className="text-fog-500">1σ̄</sub>
                </div>
                <div className="pl-12 text-fog-100">
                  + (δ/2) Σ<sub className="text-fog-500">σ</sub> (n<sub className="text-fog-500">1σ</sub> − n<sub className="text-fog-500">2σ</sub>)
                </div>
                <div className="mt-5 text-fog-500"># physics of the contact</div>
                <div className="text-accent-bright">t = t₀ · exp(−(d − 2.9Å) / 0.9)</div>
                <div className="text-accent-bright">δ = 1.4 · (χ_ligand − χ_protein)</div>
                <div className="mt-5 text-fog-500"># VQE loop</div>
                <div className="text-fog-300">
                  θ* ← argmin ⟨ψ(θ)|H|ψ(θ)⟩&nbsp;&nbsp;<span className="text-quantum">// L-BFGS-B · parameter-shift</span>
                </div>
                <div className="text-fog-300">
                  ΔE = E<sub className="text-fog-500">coupled</sub> − E<sub className="text-fog-500">decoupled</sub>
                </div>
                <div className="mt-2 text-quantum">
                  ΔE &lt; 0 → charge transfer stabilizes the pose
                </div>
              </div>
              <div className="border-t border-line bg-ink-900/70 px-6 py-3 text-[11px] leading-relaxed text-fog-600">
                Proof-of-concept refinement: a real VQE workflow on an effective Hamiltonian,
                cross-checked against exact diagonalization — not a production ab initio engine.
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ============================= IMPACT ============================= */}
      <section id="impact" className="border-y border-line bg-ink-900/40 py-24">
        <div className="mx-auto max-w-7xl px-6">
          <Reveal className="max-w-2xl">
            <span className="eyebrow">Why it matters</span>
            <h2 className="mt-4 font-display text-3xl font-600 tracking-tight text-white md:text-4xl">
              Built for the diseases
              <br />
              the market forgot
            </h2>
          </Reveal>
          <div className="mt-12 grid gap-5 md:grid-cols-3">
            {IMPACT.map((c, i) => (
              <Reveal key={c.title} delay={i * 100}>
                <div className="panel h-full p-7 transition-colors duration-300 hover:border-accent/30">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-accent/25 bg-accent/10 text-accent">
                    <c.icon size={20} strokeWidth={1.8} />
                  </div>
                  <h3 className="mt-5 font-display text-lg font-600 text-white">{c.title}</h3>
                  <p className="mt-2.5 text-sm leading-relaxed text-fog-400">{c.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ============================= TECH =============================== */}
      <section id="tech" className="mx-auto max-w-7xl px-6 py-24">
        <div className="grid gap-14 lg:grid-cols-[1fr_1.2fr]">
          <Reveal>
            <span className="eyebrow">Technology</span>
            <h2 className="mt-4 font-display text-3xl font-600 tracking-tight text-white md:text-4xl">
              Open tools, end to end
            </h2>
            <p className="mt-5 text-[15px] leading-relaxed text-fog-400">
              Every component is free and open — Qiskit for the quantum layer, RDKit for
              chemistry, FastAPI and React for the product. Structures stream live from the
              RCSB PDB; drug structures are resolved from PubChem and validated locally.
            </p>
            <p className="mt-4 text-[15px] leading-relaxed text-fog-400">
              The software-only MVP runs entirely on simulators and public databases, so the
              barrier to running a serious screen is a laptop and curiosity.
            </p>
            <Link to="/platform" className="btn-primary mt-7">
              <Boxes size={16} />
              Open the console
            </Link>
          </Reveal>
          <Reveal delay={120}>
            <div className="grid gap-3 sm:grid-cols-2">
              {TECH.map(([name, role]) => (
                <div
                  key={name}
                  className="panel-flat flex items-center gap-4 px-5 py-4 transition-colors duration-300 hover:border-accent/25"
                >
                  <span className="font-mono text-[13px] font-600 text-accent-bright">{name}</span>
                  <span className="ml-auto text-right text-[11px] text-fog-600">{role}</span>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* ============================== CTA =============================== */}
      <section className="relative overflow-hidden border-t border-line py-24">
        <div className="absolute inset-0 bg-grid opacity-70" />
        <div className="absolute inset-0 glow-accent" />
        <Reveal className="relative mx-auto max-w-3xl px-6 text-center">
          <h2 className="font-display text-3xl font-600 tracking-tight text-white md:text-5xl">
            Screen the shelf.
            <span className="block text-gradient">Find the overlooked cure.</span>
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-[15px] text-fog-400">
            Pick a target, run the pipeline, and watch the quantum scores land — usually in
            under two minutes.
          </p>
          <div className="mt-8 flex justify-center">
            <Link to="/platform" className="btn-primary !px-7 !py-3 text-[15px]">
              Launch Q-Pharm
              <ArrowRight size={17} strokeWidth={2.2} />
            </Link>
          </div>
        </Reveal>
      </section>

      <Footer />
    </div>
  )
}
