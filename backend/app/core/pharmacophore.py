"""Pharmacophore typing for receptor atoms (name-based) and ligand atoms (SMARTS-based).

Both sides produce the same four feature classes — hydrogen-bond donors,
hydrogen-bond acceptors, hydrophobic points and aromatic ring centroids — which
are used for placement anchors, the docking scoring function and the reported
protein–ligand interaction map.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from rdkit import Chem

from .pdb import Atom

# --------------------------------------------------------------------------- #
# Receptor-side (PDB atom-name heuristics)
# --------------------------------------------------------------------------- #

# Atom names that act as H-bond donors (heavy atom bonded to a polar hydrogen)
_DONOR_BY_RESIDUE: dict[str, set[str]] = {
    "ARG": {"NE", "NH1", "NH2"},
    "LYS": {"NZ"},
    "ASN": {"ND2"},
    "GLN": {"NE2"},
    "HIS": {"ND1", "NE2"},
    "TRP": {"NE1"},
    "SER": {"OG"},
    "THR": {"OG1"},
    "TYR": {"OH"},
    "CYS": {"SG"},
}
# Atom names that act as H-bond acceptors
_ACCEPTOR_BY_RESIDUE: dict[str, set[str]] = {
    "ASP": {"OD1", "OD2"},
    "GLU": {"OE1", "OE2"},
    "ASN": {"OD1"},
    "GLN": {"OE1"},
    "HIS": {"ND1", "NE2"},
    "SER": {"OG"},
    "THR": {"OG1"},
    "TYR": {"OH"},
}
# Aromatic ring atom names (centroids are computed per residue)
_AROMATIC_RINGS: dict[str, list[list[str]]] = {
    "PHE": [["CG", "CD1", "CD2", "CE1", "CE2", "CZ"]],
    "TYR": [["CG", "CD1", "CD2", "CE1", "CE2", "CZ"]],
    "TRP": [["CG", "CD1", "CD2", "NE1", "CE2"],
            ["CE2", "CE3", "CZ2", "CZ3", "CH2"]],
    "HIS": [["CG", "ND1", "CD2", "CE1", "NE2"]],
}


@dataclass
class FeatureSet:
    donors: list[tuple[str, np.ndarray]] = field(default_factory=list)      # (label, coord)
    acceptors: list[tuple[str, np.ndarray]] = field(default_factory=list)
    hydrophobes: list[tuple[str, np.ndarray]] = field(default_factory=list)
    aromatics: list[tuple[str, np.ndarray]] = field(default_factory=list)   # ring centroids

    def counts(self) -> dict:
        return {"donors": len(self.donors), "acceptors": len(self.acceptors),
                "hydrophobes": len(self.hydrophobes), "aromatics": len(self.aromatics)}


def receptor_features(atoms: list[Atom]) -> FeatureSet:
    """Type pocket atoms by residue + atom name."""
    fs = FeatureSet()
    by_res: dict[tuple, list[Atom]] = {}
    for a in atoms:
        by_res.setdefault((a.resname, a.chain, a.resseq), []).append(a)

    for (resname, chain, resseq), res_atoms in by_res.items():
        label_src = res_atoms[0]
        names = {a.name: a for a in res_atoms}
        donor_names = _DONOR_BY_RESIDUE.get(resname, set())
        acceptor_names = _ACCEPTOR_BY_RESIDUE.get(resname, set())
        # Backbone
        if "N" in names and resname != "PRO":
            fs.donors.append((label_src.label, names["N"].coord))
        if "O" in names:
            fs.acceptors.append((label_src.label, names["O"].coord))
        # Side chains
        for n in donor_names:
            if n in names:
                fs.donors.append((label_src.label, names[n].coord))
        for n in acceptor_names:
            if n in names:
                fs.acceptors.append((label_src.label, names[n].coord))
        # Hydrophobes: carbon atoms (skip carbonyl C)
        for a in res_atoms:
            if a.element == "C" and a.name != "C":
                fs.hydrophobes.append((label_src.label, a.coord))
        # Aromatic centroids
        for ring_names in _AROMATIC_RINGS.get(resname, []):
            ring_atoms = [names[n] for n in ring_names if n in names]
            if len(ring_atoms) >= 5:
                centroid = np.mean([a.coord for a in ring_atoms], axis=0)
                fs.aromatics.append((label_src.label, centroid))
    return fs


# --------------------------------------------------------------------------- #
# Ligand-side (RDKit SMARTS)
# --------------------------------------------------------------------------- #

_HBD_SMARTS = [
    Chem.MolFromSmarts("[NX3;H2,H1,H0;!$(NC=[O,S]);!$(N=C=O)]"),   # amines/amides
    Chem.MolFromSmarts("[OX2H]"),                                   # hydroxyl
    Chem.MolFromSmarts("[nX3H1]"),                                  # aromatic NH
    Chem.MolFromSmarts("[SX2H]"),
]
_HBA_SMARTS = [
    Chem.MolFromSmarts("[O;H0;X1,X2]"),                             # carbonyl, ether, ester, anion, furan
    Chem.MolFromSmarts("[OX2H1]"),                                  # hydroxyl O (accepts too)
    Chem.MolFromSmarts("[N;H0;X2,X3;!$(NC=O);!$([N+])]"),           # tertiary/aromatic N (not amide)
    Chem.MolFromSmarts("[SX2;H0]"),
]
_HYDROPHOBE_SMARTS = Chem.MolFromSmarts("[#6;!$([#6]~[#7,#8,#9,#15,#16])]")


def ligand_features(mol: Chem.Mol, conf_id: int = -1) -> FeatureSet:
    """Compute pharmacophore features for one conformer of an RDKit molecule."""
    fs = FeatureSet()
    conf = mol.GetConformer(conf_id)
    seen_donors: set[int] = set()
    seen_acceptors: set[int] = set()
    seen_hydrophobes: set[int] = set()

    def add(patterns, bucket, seen):
        for p in patterns:
            if p is None:
                continue
            for idx in mol.GetSubstructMatches(p):
                atom = mol.GetAtomWithIdx(idx[0])
                if atom.GetIdx() in seen:
                    continue
                seen.add(atom.GetIdx())
                pos = conf.GetAtomPosition(atom.GetIdx())
                bucket.append((atom.GetSymbol(), np.array([pos.x, pos.y, pos.z])))

    add(_HBD_SMARTS, fs.donors, seen_donors)
    add(_HBA_SMARTS, fs.acceptors, seen_acceptors)
    if _HYDROPHOBE_SMARTS is not None:
        add([_HYDROPHOBE_SMARTS], fs.hydrophobes, seen_hydrophobes)

    # Aromatic ring centroids
    ring_info = mol.GetRingInfo()
    for ring in ring_info.AtomRings():
        atoms = [mol.GetAtomWithIdx(i) for i in ring]
        if len(ring) in (5, 6) and all(a.GetIsAromatic() for a in atoms):
            pts = np.array([list(conf.GetAtomPosition(i)) for i in ring])
            fs.aromatics.append(("lig", pts.mean(axis=0)))
    return fs


def gasteiger_charges(mol: Chem.Mol) -> np.ndarray:
    from rdkit.Chem import AllChem
    charges = np.zeros(mol.GetNumAtoms())
    try:
        AllChem.ComputeGasteigerCharges(mol, nIter=25, throwOnParamFailure=False)
        for i, atom in enumerate(mol.GetAtoms()):
            charges[i] = float(atom.GetDoubleProp("_GasteigerCharge"))
    except Exception:
        pass  # Missing parameters for exotic atoms — fall back to neutral
    return np.nan_to_num(charges, nan=0.0, posinf=0.0, neginf=0.0)
