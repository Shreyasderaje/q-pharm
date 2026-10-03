"""Empirical protein–ligand scoring function.

Follows the classical structure of empirical scoring functions introduced by
LUDI (Böhm 1994) and used in variants by most docking engines: a weighted sum
of steric-clash, van der Waals, hydrogen-bond, hydrophobic-contact,
electrostatic, aromatic-stacking and rotatable-bond-entropy terms.

All heavy-atom distances are evaluated with a KD-tree so a full pose can be
scored in well under a millisecond for typical drug-sized ligands.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from .pharmacophore import FeatureSet, gasteiger_charges

# Weight constants (kcal/mol-ish units, calibrated against co-crystal complexes)
W_CLASH = 8.0
CLASH_DIST = 2.55
W_VDW = 0.062
VDW_MIN = 3.8
VDW_SIGMA2 = 0.8
W_HB = 2.6
HB_MIN = 2.85
HB_SIGMA2 = 0.20
HB_RANGE = (2.3, 3.8)
W_HYD = 0.105
HYD_MIN = 4.0
HYD_SIGMA2 = 0.9
HYD_RANGE = (3.2, 5.6)
W_ELEC = 332.0 / 4.0        # Coulomb constant with a distance-dependent dielectric (eps ~ 4r)
W_AROM = 1.2
AROM_RANGE = 6.0
W_ROT = 0.35

# Formal charges on specific atoms (delocalized charges split per atom)
FORMAL_ATOM_CHARGES: dict[tuple[str, str], float] = {
    ("ASP", "OD1"): -0.5, ("ASP", "OD2"): -0.5,
    ("GLU", "OE1"): -0.5, ("GLU", "OE2"): -0.5,
    ("LYS", "NZ"): +1.0,
    ("ARG", "NH1"): +0.34, ("ARG", "NH2"): +0.34, ("ARG", "NE"): +0.34,
    ("HIS", "ND1"): +0.1, ("HIS", "NE2"): +0.1,
}


def _gauss(d: np.ndarray, center: float, sigma2: float) -> np.ndarray:
    return np.exp(-((d - center) ** 2) / sigma2)


class Receptor:
    """Pre-computed receptor representation for fast pose scoring.

    Features and interaction scoring cover the pocket atoms; the optional
    ``full_atoms`` tree (entire protein) is used for clash checks so poses
    cannot overlap protein regions outside the pocket.
    """

    def __init__(self, pocket_atoms, features: FeatureSet, full_atoms=None):
        self.atoms = list(pocket_atoms)
        self.coords = np.array([[a.x, a.y, a.z] for a in self.atoms], dtype=float)
        self.tree = cKDTree(self.coords)
        if full_atoms:
            self.full_atoms = list(full_atoms)
            full_coords = np.array([[a.x, a.y, a.z] for a in self.full_atoms], dtype=float)
            self.full_tree = cKDTree(full_coords)
        else:
            self.full_atoms = self.atoms
            self.full_tree = self.tree
        self.features = features

        # Formal charges per atom from residue + atom name
        self.charges = np.zeros(len(self.coords))
        for i, a in enumerate(self.atoms):
            self.charges[i] = FORMAL_ATOM_CHARGES.get((a.resname, a.name), 0.0)

        self.donor_labels = [lab for lab, _ in features.donors]
        self.acceptor_labels = [lab for lab, _ in features.acceptors]
        self.hydrophobe_labels = [lab for lab, _ in features.hydrophobes]
        self.aromatic_labels = [lab for lab, _ in features.aromatics]
        self.donor_coords = np.array([c for _, c in features.donors]) if features.donors else np.zeros((0, 3))
        self.acceptor_coords = np.array([c for _, c in features.acceptors]) if features.acceptors else np.zeros((0, 3))
        self.hydrophobe_coords = np.array([c for _, c in features.hydrophobes]) if features.hydrophobes else np.zeros((0, 3))
        self.aromatic_coords = np.array([c for _, c in features.aromatics]) if features.aromatics else np.zeros((0, 3))

    def min_distance(self, coords: np.ndarray) -> float:
        d, _ = self.full_tree.query(coords, k=1, workers=-1)
        return float(d.min())


class LigandModel:
    """Pre-computed ligand representation (atom typing + charges)."""

    def __init__(self, coords: np.ndarray, features: FeatureSet, charges: np.ndarray, rotatable_bonds: int):
        self.coords = coords
        self.features = features
        self.charges = charges
        self.rotatable_bonds = rotatable_bonds

        def indices(points):
            return np.array(sorted({self._nearest_idx(c) for _, c in points}), dtype=int) if points else np.zeros(0, dtype=int)

        self.donor_idx = indices(features.donors)
        self.acceptor_idx = indices(features.acceptors)
        self.hydrophobe_idx = indices(features.hydrophobes)
        self.aromatic_centroids = (
            np.array([c for _, c in features.aromatics]) if features.aromatics else np.zeros((0, 3))
        )

    def _nearest_idx(self, coord: np.ndarray) -> int:
        return int(np.argmin(np.linalg.norm(self.coords - coord, axis=1)))

    @classmethod
    def from_conformer(cls, mol, conf_id: int, features: FeatureSet, rotatable_bonds: int) -> "LigandModel":
        conf = mol.GetConformer(conf_id)
        coords = np.array(
            [list(conf.GetAtomPosition(i)) for i in range(mol.GetNumAtoms())], dtype=float
        )
        return cls(coords, features, gasteiger_charges(mol), rotatable_bonds)


@dataclass
class ScoreBreakdown:
    total: float
    clash: float
    vdw: float
    hbond: float
    hydrophobic: float
    electrostatic: float
    aromatic: float
    rotatable: float

    def as_dict(self) -> dict:
        return {
            "total": round(self.total, 2), "clash": round(self.clash, 2),
            "vdw": round(self.vdw, 2), "hbond": round(self.hbond, 2),
            "hydrophobic": round(self.hydrophobic, 2),
            "electrostatic": round(self.electrostatic, 2),
            "aromatic": round(self.aromatic, 2), "rotatable": round(self.rotatable, 2),
        }


def score_pose(lig: LigandModel, pose: np.ndarray, rec: Receptor) -> ScoreBreakdown:
    """Score one ligand pose (heavy+H atom coordinates in the PDB frame)."""
    k = min(24, len(rec.coords))
    pair_d = rec.tree.query(pose, k=k, distance_upper_bound=6.5, workers=-1)[0]
    flat = pair_d[np.isfinite(pair_d)]

    # Steric clash — any heavy-atom pair below CLASH_DIST
    clash = 0.0
    near = flat[flat < CLASH_DIST]
    if len(near):
        clash = W_CLASH * float(np.sum((CLASH_DIST - near) ** 2))

    # Van der Waals attraction over all close pairs
    vdw_pairs = flat[(flat >= CLASH_DIST) & (flat <= 5.2)]
    vdw = -W_VDW * float(np.sum(_gauss(vdw_pairs, VDW_MIN, VDW_SIGMA2))) if len(vdw_pairs) else 0.0

    # Hydrogen bonds: ligand donor -> receptor acceptor and vice versa
    hbond = 0.0
    for lig_idx, rec_coords in (
        (lig.donor_idx, rec.acceptor_coords),
        (lig.acceptor_idx, rec.donor_coords),
    ):
        if len(lig_idx) == 0 or len(rec_coords) == 0:
            continue
        d = np.linalg.norm(pose[lig_idx][:, None, :] - rec_coords[None, :, :], axis=2)
        mask = (d >= HB_RANGE[0]) & (d <= HB_RANGE[1])
        if mask.any():
            hbond += -W_HB * float(np.sum(_gauss(d[mask], HB_MIN, HB_SIGMA2)))

    # Hydrophobic contacts
    hyd = 0.0
    if len(lig.hydrophobe_idx) and len(rec.hydrophobe_coords):
        d = np.linalg.norm(pose[lig.hydrophobe_idx][:, None, :] - rec.hydrophobe_coords[None, :, :], axis=2)
        mask = (d >= HYD_RANGE[0]) & (d <= HYD_RANGE[1])
        if mask.any():
            hyd = -W_HYD * float(np.sum(_gauss(d[mask], HYD_MIN, HYD_SIGMA2)))

    # Distance-dependent electrostatics (formal charges only — cheap and stable)
    elec = 0.0
    if np.any(lig.charges != 0) and np.any(rec.charges != 0):
        for i in np.where(lig.charges != 0)[0]:
            neigh = rec.tree.query_ball_point(pose[i], r=9.0, workers=-1)
            if not neigh:
                continue
            j = np.array(sorted(neigh), dtype=int)
            mask = rec.charges[j] != 0.0
            if not mask.any():
                continue
            d = np.linalg.norm(rec.coords[j[mask]] - pose[i], axis=1)
            ok = d > 2.2
            if ok.any():
                elec += W_ELEC * float(
                    np.sum(lig.charges[i] * rec.charges[j[mask]][ok] / (d[ok] ** 2))
                )

    # Aromatic stacking between ring centroids
    arom = 0.0
    if len(lig.aromatic_centroids) and len(rec.aromatic_coords):
        d = np.linalg.norm(lig.aromatic_centroids[:, None, :] - rec.aromatic_coords[None, :, :], axis=2)
        arom = -W_AROM * float(np.sum(d < AROM_RANGE))

    rot = W_ROT * lig.rotatable_bonds
    total = clash + vdw + hbond + hyd + elec + arom + rot
    return ScoreBreakdown(total, clash, vdw, hbond, hyd, elec, arom, rot)
