"""Rigid-receptor docking engine: conformer generation, pocket placement and pose refinement.

Algorithm per drug:
  1. Generate a small ensemble of low-energy 3D conformers (ETKDG + MMFF/UFF).
  2. Sample placements — random rigid-body rotations + translations onto
     pharmacophore anchor points inside the pocket — with a fast clash filter.
  3. Score every non-clashing placement with the empirical function and keep
     the best; polish it with a short stochastic hill-climb (micro-rotations
     and translations).
  4. Extract the protein–ligand interaction map of the final pose.

Poses are produced directly in the coordinate frame of the source PDB, so the
docked ligand overlays the receptor without any post-hoc alignment.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, rdMolDescriptors
from scipy.spatial.transform import Rotation

from .pdb import Pocket
from .pharmacophore import FeatureSet, gasteiger_charges, ligand_features, receptor_features
from .scoring import LigandModel, Receptor, ScoreBreakdown, score_pose


class DockingError(RuntimeError):
    pass


@dataclass
class PreparedLigand:
    smiles: str
    mol: Chem.Mol
    conf_ids: list[int]
    rotatable_bonds: int
    features_by_conf: dict[int, FeatureSet]
    models: dict[int, LigandModel]

    @property
    def num_atoms(self) -> int:
        return self.mol.GetNumAtoms()


@dataclass
class Interaction:
    kind: str            # "hbond" | "hydrophobic" | "aromatic" | "electrostatic"
    ligand_atom: str     # atom symbol + index (1-based)
    ligand_coord: list[float]
    protein: str         # residue label
    protein_atom: str    # atom name when available
    protein_coord: list[float]
    distance: float

    def as_dict(self) -> dict:
        return {
            "kind": self.kind, "ligand_atom": self.ligand_atom,
            "ligand_coord": [round(v, 2) for v in self.ligand_coord],
            "protein": self.protein, "protein_atom": self.protein_atom,
            "protein_coord": [round(v, 2) for v in self.protein_coord],
            "distance": round(self.distance, 2),
        }


@dataclass
class DockResult:
    best_score: ScoreBreakdown
    best_pose: np.ndarray            # atom coordinates of the best pose
    conf_id: int
    interactions: list[Interaction]
    n_placements: int
    n_clash_free: int
    ligand_efficiency: float         # score per heavy atom


# --------------------------------------------------------------------------- #
# Ligand preparation
# --------------------------------------------------------------------------- #

def prepare_ligand(smiles: str, max_confs: int = 6, seed: int = 42) -> Optional[PreparedLigand]:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    mol = Chem.AddHs(mol)
    # Large molecules: fewer conformers — ETKDG + MMFF cost grows steeply
    heavy = sum(1 for a in mol.GetAtoms() if a.GetSymbol() != "H")
    if not max_confs:
        max_confs = 6 if heavy <= 40 else (4 if heavy <= 70 else 3)
    params = AllChem.ETKDGv3()
    params.randomSeed = seed
    params.useRandomCoords = False
    try:
        conf_ids = list(AllChem.EmbedMultipleConfs(mol, numConfs=max_confs, params=params))
    except Exception:
        return None
    if not conf_ids:
        params.useRandomCoords = True
        try:
            conf_ids = list(AllChem.EmbedMultipleConfs(mol, numConfs=max_confs, params=params))
        except Exception:
            return None
        if not conf_ids:
            return None

    # Relax conformers: MMFF when parameters exist, otherwise UFF
    try:
        if AllChem.MMFFHasAllMoleculeParams(mol):
            AllChem.MMFFOptimizeMoleculeConfs(mol, maxIters=250)
        else:
            AllChem.UFFOptimizeMoleculeConfs(mol, maxIters=250)
    except Exception:
        pass  # Keep un-optimized ETKDG conformers

    try:
        rotb = rdMolDescriptors.CalcNumRotatableBonds(mol)
    except Exception:
        rotb = 0

    features_by_conf: dict[int, FeatureSet] = {}
    models: dict[int, LigandModel] = {}
    for cid in conf_ids:
        feats = ligand_features(mol, cid)
        features_by_conf[cid] = feats
        models[cid] = LigandModel.from_conformer(mol, cid, feats, rotb)

    canonical = Chem.MolToSmiles(Chem.RemoveHs(mol))
    return PreparedLigand(canonical, mol, list(conf_ids), rotb, features_by_conf, models)


# --------------------------------------------------------------------------- #
# Placement sampling + refinement
# --------------------------------------------------------------------------- #

def _placement_anchors(pocket: Pocket, rec: Receptor, rng: np.random.Generator) -> np.ndarray:
    """Cavity points inside the pocket that are themselves clash-free (>= 3 A
    from every receptor atom).  Ligand centroids are translated onto these,
    so a large fraction of placements start geometrically feasible."""
    r = max(min(pocket.radius * 0.85, 11.0), 4.0)
    step = 1.2
    xs = np.arange(pocket.center[0] - r, pocket.center[0] + r, step)
    ys = np.arange(pocket.center[1] - r, pocket.center[1] + r, step)
    zs = np.arange(pocket.center[2] - r, pocket.center[2] + r, step)
    grid = np.stack(np.meshgrid(xs, ys, zs, indexing="ij"), axis=-1).reshape(-1, 3)
    inside = np.linalg.norm(grid - pocket.center, axis=1) <= r
    grid = grid[inside]
    if len(grid):
        dist, _ = rec.tree.query(grid, k=1, workers=-1)
        grid = grid[dist >= 3.0]
    if len(grid) < 8:
        # tiny/occluded pocket — fall back to uniform sphere sampling
        dirs = rng.normal(size=(150, 3))
        dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
        grid = pocket.center + dirs * (r * rng.uniform(0.1, 0.9, size=(150, 1)))
    if len(grid) > 160:
        sel = rng.choice(len(grid), size=160, replace=False)
        grid = grid[sel]
    return grid


def _rigid_transform(coords: np.ndarray, rot: Rotation, target: np.ndarray) -> np.ndarray:
    centroid = coords.mean(axis=0)
    return (coords - centroid) @ rot.as_matrix().T + target


def _hbond_seeded_pose(base: np.ndarray, model: LigandModel, rec: Receptor,
                       rng: np.random.Generator) -> Optional[np.ndarray]:
    """Place one ligand donor/acceptor at the ideal H-bond distance from a
    complementary pocket atom, with a random orientation about that axis —
    guarantees at least one geometrically valid H-bond."""
    if rng.random() < 0.5 and len(model.donor_idx) and len(rec.acceptor_coords):
        li = int(model.donor_idx[int(rng.integers(0, len(model.donor_idx)))])
        rc = rec.acceptor_coords[int(rng.integers(0, len(rec.acceptor_coords)))]
    elif len(model.acceptor_idx) and len(rec.donor_coords):
        li = int(model.acceptor_idx[int(rng.integers(0, len(model.acceptor_idx)))])
        rc = rec.donor_coords[int(rng.integers(0, len(rec.donor_coords)))]
    else:
        return None
    direction = rng.normal(size=3)
    norm = np.linalg.norm(direction)
    if norm < 1e-6:
        return None
    target = rc + direction / norm * 2.85
    pose = base + (target - base[li])
    # random spin about the axis through the anchored atom
    axis = rng.normal(size=3)
    axis /= (np.linalg.norm(axis) + 1e-9)
    R = Rotation.from_rotvec(axis * rng.uniform(0, 2 * np.pi)).as_matrix()
    return (pose - pose[li]) @ R.T + pose[li]


def dock_ligand(lig: PreparedLigand, pocket: Pocket, rec: Receptor,
                placements: int = 300, seed: int = 42) -> DockResult:
    rng = np.random.default_rng(seed)
    anchors = _placement_anchors(pocket, rec, rng)
    max_offset = max(pocket.radius * 0.10, 0.5)
    min_dist_ok = 2.35

    best_total = None
    best_pose = None
    best_conf = None
    best_model = None
    best_fallback = None          # least-clashing pose if nothing fits
    best_fallback_total = None
    n_tried = 0
    n_clash_free = 0

    per_conf = max(placements // max(len(lig.conf_ids), 1), 25)

    for cid in lig.conf_ids:
        model = lig.models[cid]
        base = model.coords
        for k in range(per_conf):
            n_tried += 1
            if k % 2 == 0:
                # pharmacophore-seeded placement off a cavity anchor
                anchor = anchors[int(rng.integers(0, len(anchors)))]
                seed_pose = _rigid_transform(base, Rotation.random(
                    random_state=int(rng.integers(0, 2**31 - 1))), anchor)
                pose = _hbond_seeded_pose(seed_pose, model, rec, rng)
                if pose is None:
                    pose = seed_pose
            else:
                rot = Rotation.random(random_state=int(rng.integers(0, 2**31 - 1)))
                anchor = anchors[int(rng.integers(0, len(anchors)))]
                offset = rng.normal(0, max_offset, size=3)
                pose = _rigid_transform(base, rot, anchor + offset)

            min_d = rec.min_distance(pose)
            s = score_pose(model, pose, rec)
            if min_d < min_dist_ok:
                if best_fallback_total is None or s.total < best_fallback_total:
                    best_fallback_total, best_fallback = s.total, pose
                continue
            n_clash_free += 1
            if best_total is None or s.total < best_total:
                best_total, best_pose, best_conf, best_model = s.total, pose, cid, model

    if best_pose is None:
        # Nothing fits without a clash (large ligand / small pocket): report the
        # least-bad pose — the clash penalty will rank it accordingly.
        best_pose, best_conf = best_fallback, lig.conf_ids[0]
        best_model = lig.models[best_conf]
        best_total = best_fallback_total
        if best_pose is None:
            raise DockingError("No usable placement was found for this ligand.")

    # Greedy + annealed refinement: alternate random perturbations with
    # pharmacophore "snap" moves; improvements always accepted, small
    # regressions accepted early (Metropolis) to escape 1-H-bond basins.
    rot = Rotation.from_matrix(_basis_from_pose(best_pose, best_model.coords))
    center_target = best_pose.mean(axis=0)
    current_pose, current_score = best_pose, best_total
    has_features = (len(best_model.donor_idx) + len(best_model.acceptor_idx) > 0
                    and len(rec.acceptor_coords) + len(rec.donor_coords) > 0)
    clash_free_refine = rec.min_distance(current_pose) >= min_dist_ok
    for step in range(90):
        temp = 2.0 * (1.0 - step / 100.0) + 0.05
        if has_features and step % 2 == 0:
            moved = _snap_move(best_model, current_pose, rec, rng)
        else:
            moved = None
        if moved is not None:
            cand = moved
        else:
            frac = 1.0 - step / 100.0
            ang = rng.normal(0, 0.14 * frac, size=3)
            trans = rng.normal(0, 0.38 * frac, size=3)
            cand = _rigid_transform(best_model.coords, Rotation.from_rotvec(ang) * rot,
                                    center_target + trans)
        min_d = rec.min_distance(cand)
        if min_d < (min_dist_ok if clash_free_refine else 1.9):
            continue
        s = score_pose(best_model, cand, rec)
        if s.total < current_score or rng.random() < float(np.exp(-(s.total - current_score) / temp)):
            current_pose, current_score = cand, s.total
            rot = Rotation.from_matrix(_basis_from_pose(current_pose, best_model.coords))
            center_target = current_pose.mean(axis=0)
            if s.total < best_total:
                best_pose, best_total, best_conf = cand, s.total, best_conf

    best_breakdown = score_pose(best_model, best_pose, rec)
    interactions = extract_interactions(lig, best_model, best_pose, rec)
    heavy = sum(1 for a in lig.mol.GetAtoms() if a.GetSymbol() != "H")
    eff = best_breakdown.total / max(heavy, 1)

    return DockResult(best_breakdown, best_pose, best_conf, interactions,
                      n_tried, n_clash_free, round(eff, 3))


def _snap_move(model: LigandModel, pose: np.ndarray, rec: Receptor,
               rng: np.random.Generator) -> Optional[np.ndarray]:
    """Translate the ligand so one of its donors/acceptors lands at the ideal
    H-bond distance from a complementary pocket feature."""
    if rng.random() < 0.5 and len(model.donor_idx) and len(rec.acceptor_coords):
        lig_idx = model.donor_idx[int(rng.integers(0, len(model.donor_idx)))]
        rec_coords = rec.acceptor_coords
    elif len(model.acceptor_idx) and len(rec.donor_coords):
        lig_idx = model.acceptor_idx[int(rng.integers(0, len(model.acceptor_idx)))]
        rec_coords = rec.donor_coords
    else:
        return None
    rc = rec_coords[int(rng.integers(0, len(rec_coords)))]
    d_vec = pose[lig_idx] - rc
    d = float(np.linalg.norm(d_vec))
    if d < 1e-6:
        return None
    ideal = rc + d_vec / d * 2.85
    return pose + (ideal - pose[lig_idx])


def _basis_from_pose(pose: np.ndarray, base: np.ndarray) -> np.ndarray:
    """Recover rotation applied by least squares (used to seed refinement)."""
    c0 = base - base.mean(axis=0)
    c1 = pose - pose.mean(axis=0)
    u, _, vt = np.linalg.svd(c0.T @ c1)
    d = np.sign(np.linalg.det(u @ vt))
    r = u @ np.diag([1, 1, d]) @ vt
    return r.T  # transform matrix maps base -> pose


# --------------------------------------------------------------------------- #
# Interaction extraction
# --------------------------------------------------------------------------- #

def extract_interactions(lig: PreparedLigand, model: LigandModel, pose: np.ndarray,
                         rec: Receptor) -> list[Interaction]:
    out: list[Interaction] = []
    mol = lig.mol

    def lig_label(idx: int) -> str:
        atom = mol.GetAtomWithIdx(idx)
        return f"{atom.GetSymbol()}{idx + 1}"

    # Hydrogen bonds (both directions)
    for lig_idx, rec_coords, rec_labels, kind in (
        (model.donor_idx, rec.acceptor_coords, rec.acceptor_labels, "hbond"),
        (model.acceptor_idx, rec.donor_coords, rec.donor_labels, "hbond"),
    ):
        if len(lig_idx) == 0 or len(rec_coords) == 0:
            continue
        d = np.linalg.norm(pose[lig_idx][:, None, :] - rec_coords[None, :, :], axis=2)
        for a, b in zip(*np.where((d >= 2.3) & (d <= 3.6))):
            out.append(Interaction(kind, lig_label(int(lig_idx[a])),
                                   list(pose[lig_idx[a]]), rec_labels[b], "",
                                   list(rec_coords[b]), float(d[a, b])))

    # Closest hydrophobic contacts
    if len(model.hydrophobe_idx) and len(rec.hydrophobe_coords):
        d = np.linalg.norm(pose[model.hydrophobe_idx][:, None, :] - rec.hydrophobe_coords[None, :, :], axis=2)
        pairs = [(float(d[a, b]), int(model.hydrophobe_idx[a]), b) for a, b in zip(*np.where(d <= 4.2))]
        pairs.sort()
        for dist, li, ri in pairs[:8]:
            out.append(Interaction("hydrophobic", lig_label(li), list(pose[li]),
                                   rec.hydrophobe_labels[ri], "", list(rec.hydrophobe_coords[ri]), dist))

    # Salt bridges / strong electrostatics
    charged_lig = np.where(np.abs(model.charges) > 0.45)[0]
    charged_rec = np.where(np.abs(rec.charges) > 0.5)[0]
    if len(charged_lig) and len(charged_rec):
        d = np.linalg.norm(pose[charged_lig][:, None, :] - rec.coords[None, charged_rec, :], axis=2)
        for a, b in zip(*np.where((d >= 2.5) & (d <= 5.0))):
            out.append(Interaction("electrostatic", lig_label(int(charged_lig[a])),
                                   list(pose[charged_lig[a]]), _res_label(rec, int(charged_rec[b])), "",
                                   list(rec.coords[charged_rec[b]]), float(d[a, b])))

    # Aromatic stacking
    if len(model.aromatic_centroids) and len(rec.aromatic_coords):
        d = np.linalg.norm(model.aromatic_centroids[:, None, :] - rec.aromatic_coords[None, :, :], axis=2)
        for a, b in zip(*np.where(d < 5.5)):
            out.append(Interaction("aromatic", "aromatic centroid",
                                   list(model.aromatic_centroids[a]), rec.aromatic_labels[b], "",
                                   list(rec.aromatic_coords[b]), float(d[a, b])))

    # Deduplicate and cap
    seen: set[tuple] = set()
    unique: list[Interaction] = []
    for it in out:
        key = (it.kind, it.ligand_atom, it.protein)
        if key not in seen:
            seen.add(key)
            unique.append(it)
    unique.sort(key=lambda i: i.distance)
    return unique[:16]


def _res_label(rec: Receptor, idx: int) -> str:
    atom = rec.atoms[idx]
    chain = f":{atom.chain}" if atom.chain.strip() else ""
    return f"{atom.resname}{atom.resseq}{chain}"


# --------------------------------------------------------------------------- #
# Pose export
# --------------------------------------------------------------------------- #

def pose_to_sdf(lig: PreparedLigand, pose: np.ndarray, conf_id: Optional[int] = None) -> str:
    """Serialize a docked pose as an SDF block (coordinates are overwritten)."""
    mol = Chem.Mol(lig.mol)
    conf = mol.GetConformer(conf_id if conf_id is not None else mol.GetNumConformers() - 1)
    n = min(mol.GetNumAtoms(), len(pose))
    for i in range(n):
        x, y, z = pose[i]
        conf.SetAtomPosition(i, (float(x), float(y), float(z)))
    return Chem.MolToMolBlock(mol, includeStereo=True)
