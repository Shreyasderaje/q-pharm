"""End-to-end screening pipeline orchestrator.

Stages
  1. structure   — fetch/parse the target protein (RCSB or user upload)
  2. pocket      — define the binding pocket (co-crystal ligand or cavity detection)
  3. prefilter   — rank the library by pharmacophore complementarity, keep top K
  4. docking     — sample + score ligand placements (progress reported per drug)
  5. quantum     — VQE refinement of the strongest contact for the top M poses
  6. admet       — ADMET profiling + ML drug-likeness re-ranking
  7. report      — composite scoring, ranking, pose export
"""

from __future__ import annotations

import time
import traceback
from pathlib import Path

import numpy as np
from rdkit import Chem
from scipy.spatial import cKDTree

from . import jobs
from .admet import compute_admet
from .config import (
    DEFAULT_LIBRARY_SIZE,
    DEFAULT_QUANTUM_TOP,
    MAX_LIBRARY_SIZE,
    MAX_PLACEMENTS,
    MAX_QUANTUM_TOP,
)
from .docking import dock_ligand, pose_to_sdf, prepare_ligand
from .ml import load_model
from .pdb import (
    PDBError,
    Atom,
    detect_pocket_abinitio,
    fetch_pdb,
    parse_pdb,
    pocket_from_ligand,
    protein_atoms,
    resolve_pocket,
)
from .pharmacophore import receptor_features
from .quantum import interaction_energy
from .scoring import Receptor

# Composite-score weights (transparent by design)
W_DOCKING = 0.55
W_ADMET = 0.20
W_QUANTUM = 0.15
W_ML = 0.10


class ScreeningError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# Structure resolution
# --------------------------------------------------------------------------- #

def resolve_structure(target: dict) -> tuple[str, list[Atom], str]:
    """Return (pdb_text, parsed_atoms, source_description)."""
    mode = target.get("mode", "pdb_id")
    if mode == "pdb_id":
        pdb_id = (target.get("pdb_id") or "").strip()
        if not pdb_id:
            raise ScreeningError("No PDB ID provided.")
        text = fetch_pdb(pdb_id)
        return text, parse_pdb(text), f"RCSB PDB {pdb_id.upper()}"
    if mode == "upload":
        content = target.get("content") or ""
        if not content.strip():
            raise ScreeningError("Uploaded PDB file is empty.")
        if len(content) > 30_000_000:
            raise ScreeningError("Uploaded PDB file is too large.")
        return content, parse_pdb(content), "uploaded structure"
    if mode == "curated":
        curated_id = (target.get("pdb_id") or "").strip().upper()
        text = fetch_pdb(curated_id)
        return text, parse_pdb(text), f"curated target {curated_id}"
    raise ScreeningError(f"Unknown target mode '{mode}'.")


# --------------------------------------------------------------------------- #
# Prefilter
# --------------------------------------------------------------------------- #

def _prefilter(library: list[dict], pocket_feature_counts: dict, size: int) -> list[dict]:
    """Cheap 2D complementarity ranking to select which drugs get docked."""
    pocket_donors = pocket_feature_counts.get("donors", 0)
    pocket_acceptors = pocket_feature_counts.get("acceptors", 0)
    pocket_aroms = pocket_feature_counts.get("aromatics", 0)
    scored: list[tuple[float, dict]] = []
    for drug in library:
        mol = Chem.MolFromSmiles(drug["smiles"])
        if mol is None:
            continue
        from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors

        hbd = Lipinski.NumHDonors(mol)
        hba = Lipinski.NumHAcceptors(mol)
        aroms = rdMolDescriptors.CalcNumAromaticRings(mol)
        mw = Descriptors.MolWt(mol)
        rotb = Lipinski.NumRotatableBonds(mol)
        logp = Crippen.MolLogP(mol)
        heavy = mol.GetNumHeavyAtoms()

        # Complementarity: how much of the pocket's chemistry can this drug address
        score = 0.0
        score += 1.2 * min(hba, pocket_donors)
        score += 1.2 * min(hbd, pocket_acceptors)
        score += 0.6 * min(aroms, max(pocket_aroms, 1))
        score += 0.012 * mw / 10.0                    # mild bulk preference
        score -= 0.10 * max(0, heavy - 55)            # too big for most pockets
        score -= 0.3 * max(0, rotb - 12)              # very floppy molecules dock poorly
        score -= 0.5 * max(0, logp - 6)               # extreme lipophilicity
        if drug.get("known_repurposing"):
            score += 0.8                              # literature-prioritised compounds
        scored.append((score, drug))
    scored.sort(key=lambda t: -t[0])
    return [d for _, d in scored[:size]]


# --------------------------------------------------------------------------- #
# Quantum stage
# --------------------------------------------------------------------------- #

def _best_contact(lig, model, pose, rec: Receptor, pocket_atoms: list[Atom]) -> dict | None:
    """Strongest ligand<->protein polar contact of the pose (for VQE refinement)."""
    pocket_tree = cKDTree(np.array([[a.x, a.y, a.z] for a in pocket_atoms]))
    best = None
    for lig_idx, rec_coords in ((model.donor_idx, rec.acceptor_coords),
                                (model.acceptor_idx, rec.donor_coords)):
        if len(lig_idx) == 0 or len(rec_coords) == 0:
            continue
        d = np.linalg.norm(pose[lig_idx][:, None, :] - rec_coords[None, :, :], axis=2)
        for a, b in zip(*np.where(d <= 3.6)):
            dist = float(d[a, b])
            li = int(lig_idx[a])
            _, p_idx = pocket_tree.query(rec_coords[b])
            lig_elem = lig.mol.GetAtomWithIdx(li).GetSymbol()
            prot_elem = pocket_atoms[int(p_idx)].element if int(p_idx) < len(pocket_atoms) else "O"
            cand = {"distance": dist, "ligand_element": lig_elem,
                    "protein_element": prot_elem,
                    "ligand_atom": f"{lig_elem}{li + 1}"}
            if best is None or dist < best["distance"]:
                best = cand
    return best


# --------------------------------------------------------------------------- #
# Normalisation helpers
# --------------------------------------------------------------------------- #

def _minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if abs(hi - lo) < 1e-9:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


# --------------------------------------------------------------------------- #
# Main entry
# --------------------------------------------------------------------------- #

def run_screening(job_id: str, target: dict, params: dict) -> None:
    started = time.time()
    try:
        _run(job_id, target, params, started)
    except Exception as exc:  # surface any failure to the client
        jobs.update(job_id, status="failed", error=str(exc) or exc.__class__.__name__)
        traceback.print_exc()


def _run(job_id: str, target: dict, params: dict, started: float) -> None:
    # Enrich curated targets with verified metadata
    if target.get("mode") == "curated":
        from .drugs import load_targets

        want = (target.get("pdb_id") or "").strip().upper()
        for t in load_targets():
            if t["pdb_id"] == want:
                target = {**target, "name": t["name"], "organism": t["organism"],
                          "disease": t["disease"], "pocket_ligand": t.get("pocket_ligand")}
                break

    library_size = int(min(max(params.get("library_size", DEFAULT_LIBRARY_SIZE), 5), MAX_LIBRARY_SIZE))
    quantum_enabled = bool(params.get("quantum_enabled", True))
    quantum_top = int(min(max(params.get("quantum_top", DEFAULT_QUANTUM_TOP), 0), MAX_QUANTUM_TOP))
    placements = int(min(max(params.get("placements", 300), 60), MAX_PLACEMENTS))
    seed = int(params.get("seed", 42))

    # --- 1. structure -------------------------------------------------------- #
    jobs.update(job_id, status="running", stage_key="structure",
                stage="Resolving target structure", progress=0.02)
    pdb_text, atoms, source_desc = resolve_structure(target)
    job_dir = Path(jobs.get_job(job_id).dir)
    (job_dir / "protein.pdb").write_text(pdb_text, encoding="utf-8")

    # --- 2. pocket ------------------------------------------------------------ #
    jobs.update(job_id, stage_key="pocket", stage="Detecting binding pocket", progress=0.08)
    prot = protein_atoms(atoms)
    ligands = None
    try:
        pocket, ligands = resolve_pocket(atoms, prefer_resname=target.get("pocket_ligand"))
    except PDBError:
        pocket = detect_pocket_abinitio(prot)
    features = receptor_features(pocket.atoms)
    rec = Receptor(pocket.atoms, features, full_atoms=prot)

    # --- 3. prefilter --------------------------------------------------------- #
    jobs.update(job_id, stage_key="prefilter", stage="Ranking drug library", progress=0.12)
    from .drugs import load_library

    library = load_library()
    selected = _prefilter(library, features.counts(), library_size)

    # --- 4. docking ----------------------------------------------------------- #
    docked: list[dict] = []
    failed: list[str] = []
    total_placements = 0
    for i, drug in enumerate(selected):
        jobs.update(job_id, stage_key="docking",
                    stage=f"Docking {drug['name']} ({i + 1}/{len(selected)})",
                    progress=0.15 + 0.55 * (i + 1) / len(selected))
        try:
            lig = prepare_ligand(drug["smiles"], max_confs=0, seed=seed)  # 0 = adaptive
            if lig is None:
                failed.append(drug["name"])
                continue
            result = dock_ligand(lig, pocket, rec, placements=placements, seed=seed + i)
            total_placements += result.n_placements
            docked.append({
                "drug": drug,
                "lig": lig,
                "result": result,
            })
        except Exception:
            failed.append(drug["name"])
            continue

    if not docked:
        raise ScreeningError("No drug in the selected library could be docked into this pocket.")

    docked.sort(key=lambda d: d["result"].best_score.total)

    # --- 5. quantum refinement ------------------------------------------------ #
    quantum_by_name: dict[str, dict] = {}
    if quantum_enabled and quantum_top > 0:
        quantum_pool = [d for d in docked if d["result"].n_clash_free > 0] or docked
        top_m = quantum_pool[:quantum_top]
        for i, entry in enumerate(top_m):
            name = entry["drug"]["name"]
            jobs.update(job_id, stage_key="quantum",
                        stage=f"VQE refinement: {name} ({i + 1}/{len(top_m)})",
                        progress=0.72 + 0.18 * (i + 1) / len(top_m))
            try:
                r = entry["result"]
                lig = entry["lig"]
                model = lig.models[r.conf_id]
                contact = _best_contact(lig, model, r.best_pose, rec, pocket.atoms)
                if contact is None:
                    continue
                qres = interaction_energy(contact["distance"], contact["ligand_element"],
                                          contact["protein_element"], maxiter=250)
                quantum_by_name[name] = {**qres, "contact": contact}
            except Exception:
                continue

    # --- 6. ADMET + ML -------------------------------------------------------- #
    jobs.update(job_id, stage_key="admet", stage="ADMET profiling & ML re-ranking",
                progress=0.92)
    ml_model = load_model()
    profiles: dict[str, dict] = {}
    for entry in docked:
        drug = entry["drug"]
        name = drug["name"]
        if name in profiles:
            continue
        mol = Chem.MolFromSmiles(drug["smiles"])
        if mol is None:
            continue
        admet = compute_admet(mol)
        from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors

        feats = {
            "mw": Descriptors.MolWt(mol), "logp": Crippen.MolLogP(mol),
            "tpsa": admet.tpsa, "hbd": admet.hbd, "hba": admet.hba,
            "rotb": admet.rotatable_bonds, "aromatic_rings": admet.aromatic_rings,
            "fraction_csp3": admet.fraction_csp3, "heavy_atoms": admet.heavy_atoms,
            "formal_charge": admet.formal_charge, "esol_log_s": admet.esol_log_s,
        }
        profiles[name] = {"admet": admet.as_dict(), "ml": {"p_druglike": round(ml_model.predict_proba(feats), 4)}}

    # --- 7. composite ranking -------------------------------------------------- #
    jobs.update(job_id, stage_key="report", stage="Compiling ranked report", progress=0.97)
    raw_scores = [float(d["result"].best_score.total) for d in docked]
    # docking: more negative = better → invert before min-max
    n_dock = _minmax([-s for s in raw_scores])
    q_values = [-(v["delta_e_hartree"]) for v in quantum_by_name.values()]  # more stabilisation -> higher
    q_rank = _minmax(q_values) if q_values else []
    q_score_by_name = {name: q_rank[i] for i, name in enumerate(quantum_by_name.keys())} if q_values else {}

    candidates: list[dict] = []
    pose_blocks: dict[str, str] = {}
    for i, entry in enumerate(docked):
        drug = entry["drug"]
        name = drug["name"]
        r = entry["result"]
        try:
            pose_blocks[name] = pose_to_sdf(entry["lig"], r.best_pose, r.conf_id)
        except Exception:
            pass
        prof = profiles.get(name, {"admet": None, "ml": {"p_druglike": 0.5}})
        qinfo = quantum_by_name.get(name)
        no_fit = r.n_clash_free == 0     # ligand could not be placed without steric clash
        s_dock = n_dock[i]
        s_admet = prof["admet"]["score"] if prof["admet"] else 0.4
        s_q = q_score_by_name.get(name, 0.0)
        s_ml = prof["ml"]["p_druglike"]
        composite = (W_DOCKING * s_dock + W_ADMET * s_admet + W_QUANTUM * s_q + W_ML * s_ml)
        if no_fit:
            composite *= 0.3              # steric incompatibility dominates any score

        candidates.append({
            "rank": i + 1,
            "drug": drug,
            "docking": {
                "score": round(float(r.best_score.total), 2),
                "components": r.best_score.as_dict(),
                "ligand_efficiency": r.ligand_efficiency,
                "n_placements": r.n_placements,
                "n_clash_free": r.n_clash_free,
                "no_fit": no_fit,
                "interactions": [it.as_dict() for it in r.interactions],
            },
            "quantum": {
                "used": qinfo is not None,
                **({k: qinfo[k] for k in ("delta_e_hartree", "delta_e_ev", "delta_e_exact_eh", "vqe", "params", "contact", "decoupled_energy_eh")}
                   if qinfo else {}),
            },
            "admet": prof["admet"],
            "ml": prof["ml"],
            "scores": {
                "docking": round(s_dock, 4),
                "admet": round(s_admet, 4),
                "quantum": round(s_q, 4),
                "ml": round(s_ml, 4),
                "composite": round(composite, 4),
            },
        })

    candidates.sort(key=lambda c: -c["scores"]["composite"])
    for rank, c in enumerate(candidates, start=1):
        c["rank"] = rank
        sdf = pose_blocks.get(c["drug"]["name"])
        if sdf:
            (job_dir / f"pose_{rank}.sdf").write_text(sdf, encoding="utf-8")

    evidence = {}
    try:
        from .drugs import load_evidence

        evidence = load_evidence()
    except Exception:
        pass

    result = {
        "target": {
            "pdb_id": (target.get("pdb_id") or "").upper(),
            "name": target.get("name") or "Custom target",
            "organism": target.get("organism", ""),
            "disease": target.get("disease", ""),
            "source": source_desc,
        },
        "pocket": {
            "center": [round(v, 1) for v in pocket.center],
            "radius": round(pocket.radius, 1),
            "n_residues": len(pocket.residues),
            "residues": [r["label"] for r in pocket.residues],
            "source": pocket.source,
            "reference": pocket.reference,
            "features": features.counts(),
        },
        "screening": {
            "library_size": len(library),
            "selected_for_docking": len(selected),
            "docked": len(docked),
            "failed": failed,
            "total_placements": total_placements,
            "quantum_enabled": quantum_enabled,
            "quantum_screened": len(quantum_by_name),
            "runtime_s": round(time.time() - started, 1),
        },
        "composite_weights": {
            "docking": W_DOCKING, "admet": W_ADMET, "quantum": W_QUANTUM, "ml": W_ML,
        },
        "evidence": evidence.get((target.get("pdb_id") or "").upper(), []),
        "candidates": candidates,
    }

    jobs.update(job_id, status="completed", stage_key="done", stage="Screening complete",
                progress=1.0, result=result)
