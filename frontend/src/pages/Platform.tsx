import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Activity,
  Atom,
  CheckCircle2,
  CircleDashed,
  FileUp,
  FlaskConical,
  Loader2,
  Play,
  Radar,
  RotateCcw,
  Search,
  Server,
  ShieldCheck,
  TriangleAlert,
  XCircle,
} from 'lucide-react'
import {
  api,
  type Candidate,
  type CuratedTarget,
  type InspectResult,
  type JobState,
  type PlatformStats,
} from '../lib/api'
import Logo from '../components/Logo'
import ResultsTable from '../components/platform/ResultsTable'
import DrugDetail from '../components/platform/DrugDetail'

const STAGES = [
  { key: 'structure', label: 'Resolve structure' },
  { key: 'pocket', label: 'Detect pocket' },
  { key: 'prefilter', label: 'Rank library' },
  { key: 'docking', label: 'Dock library' },
  { key: 'quantum', label: 'VQE refinement' },
  { key: 'admet', label: 'ADMET + ML' },
  { key: 'report', label: 'Compile report' },
] as const

type Mode = 'curated' | 'pdb_id' | 'upload'

const LIBRARY_PRESETS = [
  { label: 'Fast', size: 25, hint: '~2 min' },
  { label: 'Standard', size: 60, hint: '~5 min' },
  { label: 'Deep', size: 120, hint: '~10 min' },
]

export default function Platform() {
  const [targets, setTargets] = useState<CuratedTarget[]>([])
  const [stats, setStats] = useState<PlatformStats | null>(null)
  const [mode, setMode] = useState<Mode>('curated')
  const [selectedTarget, setSelectedTarget] = useState<string>('6LU7')
  const [pdbId, setPdbId] = useState('')
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [inspect, setInspect] = useState<InspectResult | null>(null)
  const [inspecting, setInspecting] = useState(false)
  const [inspectError, setInspectError] = useState<string | null>(null)

  const [libSize, setLibSize] = useState(60)
  const [quantumEnabled, setQuantumEnabled] = useState(true)
  const [quantumTop, setQuantumTop] = useState(8)

  const [job, setJob] = useState<JobState | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [detail, setDetail] = useState<Candidate | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [searchParams, setSearchParams] = useSearchParams()

  // shareable permalinks: /platform?job=<id> restores a finished run
  useEffect(() => {
    const jid = searchParams.get('job')
    if (jid) setJobId(jid)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    api.targets().then(setTargets).catch(() => {})
    api.stats().then(setStats).catch(() => {})
  }, [])

  // poll running jobs
  useEffect(() => {
    if (!jobId) return
    if (pollRef.current) clearInterval(pollRef.current)
    const tick = () =>
      api.jobStatus(jobId)
        .then((j) => {
          setJob(j)
          if (j.status === 'completed' || j.status === 'failed') {
            if (pollRef.current) clearInterval(pollRef.current)
            pollRef.current = null
          }
        })
        .catch(() => {})
    tick()
    pollRef.current = setInterval(tick, 2000)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [jobId])

  const runInspect = useCallback(async () => {
    setInspect(null)
    setInspectError(null)
    setInspecting(true)
    try {
      if (mode === 'curated') {
        const t = targets.find((x) => x.pdb_id === selectedTarget)
        const res = await api.inspectPdbId(selectedTarget)
        setInspect({ ...res, source: `${t?.name ?? selectedTarget} · ${res.source}` })
      } else if (mode === 'pdb_id') {
        if (!pdbId.trim()) throw new Error('Enter a 4-character PDB ID first.')
        setInspect(await api.inspectPdbId(pdbId.trim()))
      } else if (uploadFile) {
        setInspect(await api.inspectUpload(uploadFile))
      } else {
        throw new Error('Choose a .pdb file first.')
      }
    } catch (e) {
      setInspectError(e instanceof Error ? e.message : 'Inspection failed')
    } finally {
      setInspecting(false)
    }
  }, [mode, pdbId, selectedTarget, targets, uploadFile])

  const startScreening = useCallback(async () => {
    setSubmitting(true)
    setJob(null)
    setDetail(null)
    setJobId(null)
    try {
      let target: Record<string, unknown>
      if (mode === 'curated') {
        target = { mode: 'curated', pdb_id: selectedTarget }
      } else if (mode === 'pdb_id') {
        target = { mode: 'pdb_id', pdb_id: pdbId.trim() }
      } else {
        if (!uploadFile) throw new Error('Choose a .pdb file first.')
        target = { mode: 'upload', content: await uploadFile.text(), name: uploadFile.name }
      }
      const { job_id } = await api.startJob(target, {
        library_size: libSize,
        quantum_enabled: quantumEnabled,
        quantum_top: quantumTop,
      })
      setJobId(job_id)
      setSearchParams({ job: job_id })
    } catch (e) {
      setJob({
        job_id: '-', status: 'failed', stage: 'Could not start', stage_key: 'error',
        progress: 0, error: e instanceof Error ? e.message : 'Request failed',
      })
    } finally {
      setSubmitting(false)
    }
  }, [mode, pdbId, selectedTarget, uploadFile, libSize, quantumEnabled, quantumTop])

  const result = job?.status === 'completed' ? job.result ?? null : null
  const running = job?.status === 'running' || job?.status === 'queued'

  return (
    <div className="min-h-screen bg-ink-950">
      {/* header */}
      <header className="sticky top-0 z-40 border-b border-line bg-ink-950/90 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-[1440px] items-center justify-between px-5">
          <div className="flex items-center gap-5">
            <Link to="/" aria-label="Back to Q-Pharm home"><Logo compact /></Link>
            <span className="hidden text-sm text-fog-500 sm:inline">/ Screening console</span>
          </div>
          <div className="flex items-center gap-4 text-xs text-fog-500">
            {stats && (
              <span className="hidden items-center gap-1.5 md:flex">
                <Server size={13} className="text-accent" />
                {stats.total} drugs · {stats.with_repurposing_evidence} with repurposing history
              </span>
            )}
            <span className="flex items-center gap-1.5">
              <Atom size={13} className="text-quantum" /> {stats?.quantum.qubits ?? 4}-qubit VQE
            </span>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1440px] gap-6 px-5 py-6 lg:grid-cols-[380px_1fr]">
        {/* ============================ LEFT PANEL ============================ */}
        <div className="space-y-5">
          {/* target selection */}
          <section className="panel p-5">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-accent/15 font-mono text-[11px] font-semibold text-accent">1</span>
              <h2 className="text-sm font-semibold text-white">Choose a target</h2>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-1 rounded-xl border border-line bg-ink-900 p-1">
              {(['curated', 'pdb_id', 'upload'] as Mode[]).map((m) => (
                <button
                  key={m}
                  onClick={() => { setMode(m); setInspect(null); setInspectError(null) }}
                  className={`rounded-lg px-2 py-1.5 text-xs font-medium transition-colors ${
                    mode === m ? 'bg-ink-700 text-white' : 'text-fog-500 hover:text-fog-200'
                  }`}
                >
                  {m === 'curated' ? 'Curated' : m === 'pdb_id' ? 'PDB ID' : 'Upload'}
                </button>
              ))}
            </div>

            {mode === 'curated' && (
              <div className="mt-4 max-h-72 space-y-1.5 overflow-y-auto pr-1">
                {targets.map((t) => (
                  <button
                    key={t.pdb_id}
                    onClick={() => { setSelectedTarget(t.pdb_id); setInspect(null); setInspectError(null) }}
                    className={`w-full rounded-xl border px-3.5 py-2.5 text-left transition-colors ${
                      selectedTarget === t.pdb_id
                        ? 'border-accent/50 bg-accent/[0.08]'
                        : 'border-line bg-ink-850 hover:border-lineBright'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[13px] font-medium text-fog-100">{t.name}</span>
                      <span className="tabular rounded bg-ink-700 px-1.5 py-0.5 font-mono text-[10px] text-fog-400">{t.pdb_id}</span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-2 text-[11px] text-fog-500">
                      <span className="text-accent-deep">{t.disease}</span>·<span className="truncate">{t.organism}</span>
                    </div>
                  </button>
                ))}
                {targets.length === 0 && (
                  <div className="flex items-center gap-2 px-2 py-6 text-xs text-fog-600">
                    <Loader2 size={13} className="animate-spin" /> loading targets…
                  </div>
                )}
              </div>
            )}

            {mode === 'pdb_id' && (
              <div className="mt-4">
                <div className="flex gap-2">
                  <input
                    className="input font-mono uppercase"
                    placeholder="e.g. 7BV2"
                    maxLength={4}
                    value={pdbId}
                    onChange={(e) => setPdbId(e.target.value.toUpperCase())}
                  />
                </div>
                <p className="mt-2 text-[11px] text-fog-600">
                  Any structure from rcsb.org. The pocket is detected from a co-crystal ligand
                  when present, or geometrically otherwise.
                </p>
              </div>
            )}

            {mode === 'upload' && (
              <label className="mt-4 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-lineBright bg-ink-900 px-4 py-8 text-center transition-colors hover:border-accent/40">
                <FileUp size={20} className="text-fog-500" />
                <span className="text-xs text-fog-300">
                  {uploadFile ? uploadFile.name : 'Click to choose a .pdb file'}
                </span>
                <input
                  type="file"
                  accept=".pdb,.txt"
                  className="hidden"
                  onChange={(e) => { setUploadFile(e.target.files?.[0] ?? null); setInspect(null); setInspectError(null) }}
                />
              </label>
            )}

            <button
              onClick={runInspect}
              disabled={inspecting || (mode === 'upload' && !uploadFile) || (mode === 'pdb_id' && !pdbId.trim())}
              className="btn-ghost mt-4 w-full !py-2 text-[13px]"
            >
              {inspecting ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
              Preview binding pocket
            </button>

            {inspectError && (
              <div className="mt-3 flex items-start gap-2 rounded-xl border border-rose-400/30 bg-rose-400/10 px-3.5 py-2.5 text-xs text-rose-300">
                <TriangleAlert size={14} className="mt-0.5 shrink-0" /> {inspectError}
              </div>
            )}

            {inspect && (
              <div className="mt-3 rounded-xl border border-accent/25 bg-accent/[0.05] px-4 py-3 animate-fade-in">
                <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-accent-bright">
                  <CheckCircle2 size={12} /> Pocket ready
                </div>
                <p className="mt-1 text-[11.5px] text-fog-400">{inspect.source}</p>
                <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-[11px] text-fog-300">
                  <span>{inspect.pocket.n_residues} pocket residues</span>
                  <span>r = {inspect.pocket.radius} Å</span>
                  <span>{inspect.pocket.features.donors} donors</span>
                  <span>{inspect.pocket.features.acceptors} acceptors</span>
                  <span>{inspect.pocket.features.hydrophobes} hydrophobes</span>
                  <span>{inspect.pocket.features.aromatics} aromatics</span>
                </div>
                <p className="mt-1.5 text-[10.5px] text-fog-600">
                  defined by {inspect.pocket.reference} ({inspect.pocket.source})
                </p>
              </div>
            )}
          </section>

          {/* engine params */}
          <section className="panel p-5">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-accent/15 font-mono text-[11px] font-semibold text-accent">2</span>
              <h2 className="text-sm font-semibold text-white">Engine settings</h2>
            </div>

            <div className="mt-4">
              <div className="flex items-center justify-between text-xs text-fog-400">
                <span>Library size</span>
                <span className="font-mono text-fog-200">{libSize} drugs</span>
              </div>
              <div className="mt-2 grid grid-cols-3 gap-1 rounded-xl border border-line bg-ink-900 p-1">
                {LIBRARY_PRESETS.map((p) => (
                  <button
                    key={p.label}
                    onClick={() => setLibSize(p.size)}
                    className={`rounded-lg px-2 py-1.5 text-xs font-medium transition-colors ${
                      libSize === p.size ? 'bg-ink-700 text-white' : 'text-fog-500 hover:text-fog-200'
                    }`}
                  >
                    {p.label}
                    <span className="ml-1 text-[9px] text-fog-600">{p.hint}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-4 flex items-center justify-between">
              <div>
                <div className="text-xs font-medium text-fog-200">Quantum refinement (VQE)</div>
                <div className="text-[10.5px] text-fog-600">4-qubit Hubbard-dimer correction</div>
              </div>
              <button
                onClick={() => setQuantumEnabled((v) => !v)}
                role="switch"
                aria-checked={quantumEnabled}
                className={`relative h-6 w-11 rounded-full transition-colors ${quantumEnabled ? 'bg-quantum' : 'bg-ink-600'}`}
              >
                <span
                  className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all ${quantumEnabled ? 'left-[22px]' : 'left-0.5'}`}
                />
              </button>
            </div>
            {quantumEnabled && (
              <div className="mt-3 flex items-center justify-between">
                <span className="text-xs text-fog-400">Refine top poses</span>
                <div className="flex items-center gap-1.5">
                  {[4, 8, 12].map((n) => (
                    <button
                      key={n}
                      onClick={() => setQuantumTop(n)}
                      className={`rounded-md border px-2 py-0.5 font-mono text-[11px] transition-colors ${
                        quantumTop === n ? 'border-quantum/50 bg-quantum/15 text-quantum-bright' : 'border-line text-fog-500 hover:text-fog-200'
                      }`}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <button
              onClick={startScreening}
              disabled={submitting || running}
              className="btn-primary mt-5 w-full !py-3 text-[15px]"
            >
              {submitting || running ? (
                <><Loader2 size={16} className="animate-spin" /> Screening…</>
              ) : (
                <><Play size={16} /> Run screening</>
              )}
            </button>
            <p className="mt-2 text-center text-[10.5px] text-fog-600">
              Docking + ADMET always run. VQE adds ~4 s per refined pose.
            </p>
          </section>

          {/* pipeline legend */}
          <section className="panel p-5">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-white">
              <Activity size={14} className="text-accent" /> Pipeline
            </h2>
            <ol className="mt-3 space-y-2">
              {STAGES.map((s, i) => {
                const idx = STAGES.findIndex((x) => x.key === job?.stage_key)
                const done = job && (idx > i || job.status === 'completed')
                const active = job?.status === 'running' && idx === i
                return (
                  <li key={s.key} className="flex items-center gap-2.5 text-xs">
                    {done ? (
                      <CheckCircle2 size={14} className="text-accent" />
                    ) : active ? (
                      <Loader2 size={14} className="animate-spin text-accent" />
                    ) : (
                      <CircleDashed size={14} className="text-fog-600" />
                    )}
                    <span className={done || active ? 'text-fog-200' : 'text-fog-600'}>{s.label}</span>
                    {active && <span className="ml-auto font-mono text-[10px] text-fog-500">{job?.stage}</span>}
                  </li>
                )
              })}
            </ol>
          </section>
        </div>

        {/* ============================ RIGHT PANEL ============================ */}
        <div className="min-w-0 space-y-6">
          {/* progress / error */}
          {running && (
            <section className="panel p-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm font-medium text-fog-100">
                  <Radar size={15} className="animate-pulse text-accent" />
                  Screening {job?.job_id && <span className="font-mono text-xs text-fog-500">#{job.job_id}</span>}
                </div>
                <span className="tabular font-mono text-sm text-accent-bright">
                  {Math.round((job?.progress ?? 0) * 100)}%
                </span>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-ink-700">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-accent-deep via-accent to-accent-bright transition-all duration-500"
                  style={{ width: `${Math.round((job?.progress ?? 0) * 100)}%` }}
                />
              </div>
              <p className="mt-3 font-mono text-xs text-fog-400">{job?.stage}…</p>
              <p className="mt-1 text-[11px] text-fog-600">
                Large drugs (macrolides, peptides) take the longest — the engine is generating
                conformers and sampling placements.
              </p>
            </section>
          )}

          {job?.status === 'failed' && (
            <section className="panel border-rose-400/30 p-6">
              <div className="flex items-start gap-3">
                <XCircle size={18} className="mt-0.5 shrink-0 text-rose-400" />
                <div>
                  <h3 className="text-sm font-semibold text-rose-300">Screening failed</h3>
                  <p className="mt-1 font-mono text-xs text-fog-400">{job.error}</p>
                  <button onClick={() => { setJob(null); setJobId(null) }} className="btn-ghost mt-4 !py-1.5 text-xs">
                    <RotateCcw size={13} /> Reset
                  </button>
                </div>
              </div>
            </section>
          )}

          {/* results */}
          {result && jobId && (
            <>
              <section className="panel p-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <FlaskConical size={15} className="text-accent" />
                      <h2 className="font-display text-lg font-600 text-white">{result.target.name}</h2>
                    </div>
                    <p className="mt-1 text-xs text-fog-500">
                      {result.target.pdb_id && <span className="font-mono">{result.target.pdb_id} · </span>}
                      {result.target.organism} · {result.target.disease}
                    </p>
                  </div>
                  <div className="grid grid-cols-4 gap-x-6 gap-y-1 text-right">
                    {[
                      ['docked', `${result.screening.docked}`],
                      ['placements', `${result.screening.total_placements.toLocaleString()}`],
                      ['VQE runs', `${result.screening.quantum_screened}`],
                      ['runtime', `${result.screening.runtime_s}s`],
                    ].map(([k, v]) => (
                      <div key={k}>
                        <div className="tabular font-mono text-sm text-fog-100">{v}</div>
                        <div className="text-[10px] uppercase tracking-wider text-fog-600">{k}</div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2 border-t border-line pt-4 text-[11px] text-fog-400">
                  <span className="chip">pocket: {result.pocket.n_residues} residues</span>
                  <span className="chip">{result.pocket.features.donors} donors · {result.pocket.features.acceptors} acceptors</span>
                  <span className="chip">{result.pocket.reference}</span>
                  {result.evidence.map((e) => (
                    <a key={e.url} href={e.url} target="_blank" rel="noreferrer" className="chip !border-accent/30 !text-accent-bright hover:!bg-accent/10">
                      {e.title.length > 58 ? e.title.slice(0, 58) + '…' : e.title}
                    </a>
                  ))}
                </div>
              </section>

              <ResultsTable
                candidates={result.candidates}
                selectedRank={detail?.rank ?? null}
                onSelect={setDetail}
                jobId={jobId}
              />

              <section className="panel p-5">
                <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest2 text-fog-500">
                  <ShieldCheck size={13} className="text-accent" /> How to read this ranking
                </h3>
                <p className="mt-2.5 text-xs leading-relaxed text-fog-400">
                  Composite = 0.55 × normalized docking + 0.20 × ADMET + 0.15 × quantum
                  stabilization + 0.10 × ML drug-likeness. Top hits are hypotheses worth
                  literature follow-up — not treatment options. Check the documented-repurposing
                  badge and the linked evidence before taking a hit seriously.
                </p>
              </section>
            </>
          )}

          {/* empty state */}
          {!result && !running && job?.status !== 'failed' && (
            <section className="panel flex min-h-[420px] flex-col items-center justify-center p-10 text-center">
              <div className="relative">
                <div className="absolute inset-0 rounded-full bg-accent/10 blur-2xl" />
                <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl border border-accent/25 bg-accent/[0.07]">
                  <FlaskConical size={34} className="text-accent" strokeWidth={1.5} />
                </div>
              </div>
              <h2 className="mt-6 font-display text-xl font-600 text-white">
                No screening yet
              </h2>
              <p className="mt-2 max-w-sm text-sm leading-relaxed text-fog-500">
                Pick a target on the left — start with{' '}
                <span className="text-fog-200">SARS-CoV-2 Mpro</span> — adjust the engine, and
                run your first quantum-refined screen.
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2 text-[11px] text-fog-500">
                <span className="chip">{stats?.total ?? 294} FDA drugs</span>
                <span className="chip">10 curated targets</span>
                <span className="chip !border-quantum/30 !text-quantum-bright">VQE refinement</span>
                <span className="chip">3D poses</span>
              </div>
            </section>
          )}
        </div>
      </div>

      {detail && jobId && (
        <DrugDetail
          candidate={detail}
          jobId={jobId}
          pocketResidues={result?.pocket.residues ?? []}
          onClose={() => setDetail(null)}
        />
      )}
    </div>
  )
}
