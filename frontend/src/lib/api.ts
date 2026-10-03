// API client + shared types for the Q-Pharm platform.

export interface RepurposingNote {
  to: string
  note: string
}

export interface Drug {
  id: string
  name: string
  drugbank_id: string | null
  drug_class: string
  indication: string
  smiles: string
  mw: number
  known_repurposing: RepurposingNote | null
}

export interface CuratedTarget {
  pdb_id: string
  name: string
  organism: string
  disease: string
  priority: number
  description: string
  n_protein_atoms?: number
  reference_ligand?: string
  n_ligand_atoms?: number
}

export interface EvidenceLink {
  title: string
  url: string
}

export interface ScoreComponents {
  total: number
  clash: number
  vdw: number
  hbond: number
  hydrophobic: number
  electrostatic: number
  aromatic: number
  rotatable: number
}

export interface Interaction {
  kind: 'hbond' | 'hydrophobic' | 'aromatic' | 'electrostatic'
  ligand_atom: string
  ligand_coord: number[]
  protein: string
  protein_atom: string
  protein_coord: number[]
  distance: number
}

export interface VQEDetail {
  energy_eh: number
  exact_energy_eh: number
  error_eh: number
  iterations: number
  evaluations: number
  n_qubits: number
  n_pauli_terms: number
  ansatz_depth: number
}

export interface QuantumInfo {
  used: boolean
  delta_e_hartree?: number
  delta_e_ev?: number
  delta_e_exact_eh?: number
  decoupled_energy_eh?: number
  params?: { t: number; U: number; delta: number; distance: number }
  contact?: { distance: number; ligand_element: string; protein_element: string; ligand_atom: string }
  vqe?: VQEDetail
}

export interface AdmetProfile {
  mw: number
  logp: number
  tpsa: number
  hbd: number
  hba: number
  rotatable_bonds: number
  aromatic_rings: number
  heavy_atoms: number
  fraction_csp3: number
  formal_charge: number
  esol_log_s: number
  log_s_mg_ml: number
  lipinski_violations: number
  veber_pass: boolean
  pains_alerts: string[]
  gi_absorption: string
  bbb_permeant: boolean
  score: number
  grade: string
}

export interface Candidate {
  rank: number
  drug: Drug
  docking: {
    score: number
    components: ScoreComponents
    ligand_efficiency: number
    n_placements: number
    n_clash_free: number
    no_fit: boolean
    interactions: Interaction[]
  }
  quantum: QuantumInfo
  admet: AdmetProfile | null
  ml: { p_druglike: number }
  scores: {
    docking: number
    admet: number
    quantum: number
    ml: number
    composite: number
  }
}

export interface ScreeningResult {
  target: {
    pdb_id: string
    name: string
    organism: string
    disease: string
    source: string
  }
  pocket: {
    center: number[]
    radius: number
    n_residues: number
    residues: string[]
    source: string
    reference: string
    features: { donors: number; acceptors: number; hydrophobes: number; aromatics: number }
  }
  screening: {
    library_size: number
    selected_for_docking: number
    docked: number
    failed: string[]
    total_placements: number
    quantum_enabled: boolean
    quantum_screened: number
    runtime_s: number
  }
  composite_weights: Record<string, number>
  evidence: EvidenceLink[]
  candidates: Candidate[]
}

export interface JobState {
  job_id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  stage: string
  stage_key: string
  progress: number
  error: string | null
  result?: ScreeningResult
}

export interface InspectResult {
  source: string
  n_protein_atoms: number
  pocket: {
    center: number[]
    radius: number
    n_residues: number
    residues: string[]
    source: string
    reference: string
    features: { donors: number; acceptors: number; hydrophobes: number; aromatics: number }
  }
}

export interface PlatformStats {
  total: number
  classes: [string, number][]
  with_repurposing_evidence: number
  quantum: { method: string; qubits: number; backend: string }
}

// --------------------------------------------------------------------------- //

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {
      /* keep statusText */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => fetch('/api/health').then(handle),
  stats: () => fetch('/api/stats').then(handle<PlatformStats>),
  targets: () => fetch('/api/targets').then(handle<CuratedTarget[]>),
  inspectPdbId: (pdbId: string) =>
    fetch('/api/targets/inspect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'pdb_id', pdb_id: pdbId }),
    }).then(handle<InspectResult>),
  inspectUpload: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch('/api/targets/upload-inspect', { method: 'POST', body: form })
    return handle<InspectResult>(res)
  },
  startJob: (target: object, params: object) =>
    fetch('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target, params }),
    }).then(handle<{ job_id: string }>),
  jobStatus: (jobId: string) => fetch(`/api/jobs/${jobId}`).then(handle<JobState>),
  proteinUrl: (jobId: string) => `/api/jobs/${jobId}/protein.pdb`,
  poseUrl: (jobId: string, rank: number) => `/api/jobs/${jobId}/poses/${rank}.sdf`,
  csvUrl: (jobId: string) => `/api/jobs/${jobId}/export.csv`,
}
