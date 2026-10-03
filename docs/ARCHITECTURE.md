# Architecture

## System overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                             Browser (React 18)                         │
│  ┌──────────────┐  ┌───────────────────┐  ┌─────────────────────────┐  │
│  │ Landing page │  │ Screening console │  │ 3Dmol.js WebGL viewer   │  │
│  └──────────────┘  └─────────┬─────────┘  └───────────┬─────────────┘  │
│        polls /api/jobs/{id}  │ fetch protein.pdb      │                │
│        every 2 s             │ + poses/{rank}.sdf     │                │
└──────────────────────────────┼────────────────────────┼────────────────┘
                               │ HTTPS (JSON / files)   │
┌──────────────────────────────▼────────────────────────▼────────────────┐
│                    FastAPI server  (uvicorn, :8010)                    │
│  ┌───────────────┐  ┌──────────────────────────────────────────────┐   │
│  │ routes.py     │  │ ThreadPoolExecutor (max 2 concurrent jobs)   │   │
│  │ + job store   │──►   pipeline.run_screening(job_id, …)           │   │
│  └───────────────┘  └───────────────┬──────────────────────────────┘   │
│                                     │                                  │
│  ┌──────────────────────────────────▼───────────────────────────────┐  │
│  │ core/ pipeline stages                                            │  │
│  │   pdb.py ─► pharmacophore.py ─► docking.py ─► scoring.py         │  │
│  │        ─► quantum.py (VQE) ─► admet.py ─► ml.py ─► ranking       │  │
│  └──────┬───────────────┬──────────────────┬────────────────────────┘  │
│         │               │                  │                           │
│  ┌──────▼─────┐  ┌──────▼──────┐   ┌───────▼────────┐                  │
│  │ data/*.json│  │ RDKit/NumPy │   │ Qiskit 2.x     │                  │
│  │ (embedded) │  │ (chemistry) │   │ statevector    │                  │
│  └────────────┘  └─────────────┘   └────────────────┘                  │
└────────────────────────────────────────────────────────────────────────┘
          │                                        │
   ┌──────▼──────┐                          ┌──────▼──────┐
   │  RCSB PDB   │                          │   PubChem   │  (build time)
   │  files.rcsb │                          │  pubchem    │
   └─────────────┘                          └─────────────┘
```

## Runtime flow

1. **Start a screen** — `POST /api/jobs {target, params}` validates the request,
   creates a job (uuid, progress state, job directory under the system temp) and
   submits `run_screening` to a small thread pool. The API returns immediately.
2. **Progress** — the pipeline updates the in-memory job store at every stage boundary
   and per docked drug; the console polls `GET /api/jobs/{id}` every 2 s and renders the
   stage list, progress bar and live stage label.
3. **Artifacts** — `protein.pdb` and one `pose_{rank}.sdf` per candidate are written to
   the job directory and served as files. Poses are expressed in the original PDB
   coordinate frame, so no alignment is needed in the browser.
4. **Result** — the completed job payload embeds the full ranking (candidates with
   docking breakdowns, quantum reports, ADMET profiles, composite decomposition and
   evidence links). Job records expire after 8 h.

## Design decisions

* **Stateless API + in-memory jobs** — simplest honest MVP; a production deployment
  would swap `jobs.py` for Redis/Celery without touching the pipeline.
* **Simulation-only quantum** — `quantum.py` depends only on `qiskit`'s core primitives
  (`QuantumCircuit`, `SparsePauliOp`, `Statevector`), avoiding heavy native
  dependencies (no PySCF/Aer) so the backend installs cleanly on Windows/Linux/macOS.
* **Data embedded, provenance scripted** — `app/data/*.json` ships with the repo so the
  product works offline; `scripts/build_data.py` reproduces it from PubChem/RCSB and
  retrains the ML model deterministically (seeded).
* **Single-process production mode** — when `frontend/dist` exists, FastAPI serves the
  SPA and the API from one port; in development, Vite proxies `/api` to the backend.

## Extending

| want to… | touch |
|---|---|
| add drugs | append to `DRUGS` in `backend/scripts/build_data.py`, rerun `python scripts/build_data.py library ml` |
| add curated targets | append to `TARGET_CANDIDATES` (pin `pocket_ligand` when a co-crystal ligand exists), rerun `targets` stage |
| swap in real ab initio VQE | replace `contact_parameters`/`hubbard_dimer_matrix` with an active-space builder (PySCF/OpenFermion) — `run_vqe` and the API contract stay |
| harden jobs for production | replace `core/jobs.py` with Redis/Celery; pipeline code is store-agnostic |
| tune scoring | constants at the top of `core/scoring.py`; re-validate against co-crystal poses |
