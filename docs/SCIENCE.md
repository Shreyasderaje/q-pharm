# The science behind Q-Pharm

This document explains each stage of the pipeline, the models it uses, and — just as
importantly — where the approximations are.

## 1. Drug repurposing

Approved drugs have already cleared the hardest attrition funnel: human safety. Finding
a *new* target for an *old* molecule skips most of the 12–15 years and ~$2.6B of de novo
development. Landmark cases include zidovudine (cancer candidate → first AIDS drug),
sildenafil (angina → erectile dysfunction/PAH), minoxidil (antihypertensive → alopecia),
thalidomide (withdrawn sedative → myeloma/leprosy), and remdesivir (Ebola asset →
COVID-19). Computational target–ligand screening is the systematic way to generate such
hypotheses.

## 2. Target acquisition and pocket detection

Structures stream from [RCSB](https://www.rcsb.org) in PDB format. The parser keeps the
first model, handles altlocs, maps modified residues (MSE→MET, SEC→CYS, …) into the
protein and classifies every `HETATM` group.

**Pocket definition** uses two strategies:

1. **Co-crystal ligand** — if a drug-like ligand (6–70 heavy atoms, not water/ion/
   buffer/glycan) is bound, the pocket is every protein residue with an atom within
   6.5 Å of it. For curated targets the reference ligand is pinned explicitly (e.g.
   `PJE` = inhibitor N3 in 6LU7, `F86` = remdesivir monophosphate in 7BV2,
   `G39` = oseltamivir in 2HU4).
2. **Geometric cavity detection** (LIGSITE-style) — otherwise, a 1.4 Å voxel grid is
   sampled; voxels ≥ 3 Å from any protein atom but inside the protein's convex hull are
   candidate cavity points, which are flood-fill clustered. The largest cluster defines
   the pocket.

**Atom typing** produces four pharmacophore classes on both sides of the interaction:

| class | receptor rule | ligand rule (SMARTS) |
|---|---|---|
| H-bond donor | backbone N (not PRO) + side-chain donors (Arg/Lys/Asn/Gln/His/Trp/Ser/Thr/Tyr/Cys) | `NX3(H)`, `OX2H`, `nX3H`, `SX2H` |
| H-bond acceptor | backbone O + Asp/Glu/Asn/Gln/His/Ser/Thr/Tyr side chains | `O(H0)`, `OX2H`, `N(H0, not amide)`, `S(H0)` |
| hydrophobe | carbon atoms | C not bonded to N/O/F/P/S |
| aromatic | Phe/Tyr/Trp/His ring centroids | 5–6 membered aromatic ring centroids |

## 3. Docking engine

**Ligand preparation.** RDKit ETKDGv3 generates 3–6 conformers (adaptive to molecule
size), relaxed with MMFF94 (UFF fallback). Gasteiger charges provide ligand partial
charges.

**Placement.** Docking is rigid-receptor with rigid-body ligand sampling:

* *Cavity anchors* — lattice points inside the pocket sphere that are themselves ≥ 3 Å
  from every receptor atom, so most placements start geometrically feasible;
* random rotations (quaternion sampling) + small jitter around each anchor;
* a fast KD-tree clash filter rejects poses with any atom pair < 2.35 Å.

**Scoring.** An empirical function in the LUDI tradition — a weighted sum of physically
interpretable terms (units are "kcal/mol-like"):

```
E = 8.0·Σ(clash²)            steric clashes < 2.55 Å
  − 0.062·Σ gauss(d; 3.8)    all close heavy-atom pairs (vdW attraction)
  − 2.6·Σ gauss(d; 2.85)     donor···acceptor pairs in 2.3–3.8 Å (H-bonds)
  − 0.105·Σ gauss(d; 4.0)    hydrophobe···hydrophobe pairs in 3.2–5.6 Å
  + 83·Σ q_i·q_j / (4 d²)    ligand Gasteiger × receptor formal charges
  − 1.2·(π-stacks < 6 Å)     aromatic ring centroids
  + 0.35·(rotatable bonds)   conformational entropy penalty
```

**Refinement.** The best raw placement is polished by 80 greedy moves: alternating
random perturbations with *pharmacophore snap moves* — a ligand donor/acceptor is
translated onto the ideal 2.85 Å H-bond distance from a complementary pocket atom.
Only score-improving moves are accepted.

**What this is not.** No side-chain flexibility, no explicit waters, no protonation
states, no induced fit. Scores are comparable *within* one run; treat absolute numbers
as qualitative.

## 4. Quantum refinement (VQE)

The strongest polar contact of each top pose becomes a two-site electronic model — the
**Hubbard dimer** in second quantization (modes: site1↑, site2↑, site1↓, site2↓):

```
H = −t Σσ (c†₁σ c₂σ + h.c.)      hopping (charge transfer)
  + U Σσ n₁σ n₁σ̄                 on-site repulsion
  + (δ/2) Σσ (n₁σ − n₂σ)         site energy offset
```

Parameterization from the docking geometry:

| parameter | model |
|---|---|
| `t` | `t₀ · exp(−(d − 2.9 Å)/0.9)`, `t₀ = 0.045 Eh` — overlap decays exponentially with donor–acceptor distance |
| `U` | `0.28 Eh` — chemical-hardness scale |
| `δ` | `1.4 · (χ_ligand − χ_protein)` — Pauling electronegativity difference |

The 4-mode Hamiltonian is mapped to **4 qubits** by an exact Pauli-basis decomposition
(equivalent to Jordan-Wigner for this system; verified numerically against the fermionic
matrix in the test suite). The ground state is found by **VQE**:

* hardware-efficient RY ansatz (depth 2, 12 parameters) with a CX ring,
* L-BFGS-B optimizer driven by **exact parameter-shift gradients**,
* a particle-number penalty `λ(N−2)²` (`λ = 0.6 Eh`) pins the physics to the
  two-electron (half-filled) sector — standard practice when the ansatz does not
  conserve particle number,
* two random restarts; statevector backend.

The interaction energy is `ΔE = E_coupled − E_decoupled` — negative ΔE means the
charge-transfer channel *stabilizes* the contact. The half-filled dimer has the known
analytic ground state `E = U/2 − √((U/2)² + 4t²)` (δ = 0), which the tests check to
10⁻⁹ Eh; VQE itself converges to < 10⁻⁶ Eh in practice.

**Honest framing.** This is a *model* Hamiltonian with phenomenological parameters — the
point is the working hybrid quantum-classical loop (contact → fermionic model → qubit
Hamiltonian → VQE → interpretable ΔE), which is exactly the architecture proposed for
near-term quantum advantage in drug discovery. Production systems would replace the
Hubbard dimer with active-space Hamiltonians from ab initio methods; nothing else in the
loop would change.

## 5. ADMET profiling & ML re-ranking

* **Lipinski Rule of 5** violations (MW, logP, HBD, HBA),
* **Veber** oral-bioavailability rules (TPSA ≤ 140 Å², rotatable bonds ≤ 10),
* **PAINS + BRENK** structural alerts via RDKit's FilterCatalog (with SMARTS fallback),
* **ESOL / Delaney** estimated aqueous solubility:
  `log S = 0.16 − 0.63 cLogP − 0.0062 MW + 0.066 rotB − 0.74 AP`,
* qualitative GI absorption and BBB-permeability heuristics.

The **ML layer** is a compact logistic regression over 11 RDKit descriptors, trained at
build time on the 294-compound drug library (positives) vs curated non-drug chemicals —
industrial solvents, dyes, pesticides, alkylating toxophores (negatives, with jitter
augmentation). It estimates a *drug-likeness prior* `p(drug-like) ∈ [0,1]`. It is a
transparent illustration of the re-ranking stage, not a production QSAR ensemble.

## 6. Composite ranking

Everything is fused with fixed, published weights so no step is a black box:

```
S = 0.55 · docking(min-max normalized)
  + 0.20 · ADMET score
  + 0.15 · quantum stabilization (normalized −ΔE)
  + 0.10 · ML drug-likeness
```

Every candidate exposes its full decomposition — per-term score components, the
interaction map with distances, the VQE report (qubits, Pauli terms, iterations, error
vs exact diagonalization), the ADMET panel and literature links.

## 7. Data provenance

* Drug structures resolved from **PubChem** by name/CID and validated with RDKit
  (canonical SMILES, exact mass); ~294 compounds spanning antivirals, antibacterials,
  antiparasitics, CNS, cardiovascular, oncology and anti-inflammatory classes; 38 carry
  a documented repurposing annotation.
* `scripts/build_data.py` rebuilds everything deterministically (PubChem + RCSB +
  RDKit) and retrains the ML model.
* Literature links per target combine specific citations (e.g. Jin et al., *Nature*
  2020 for 6LU7) with curated PubMed search queries.
