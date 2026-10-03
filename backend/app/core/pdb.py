"""PDB acquisition, parsing, ligand detection and binding-pocket detection.

The module is intentionally self-contained: it talks to RCSB over plain HTTPS and
parses the legacy PDB text format, which every experimental structure provides.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

import numpy as np
from scipy.spatial import ConvexHull, cKDTree

import requests

from .config import MAX_PDB_BYTES, RCSB_PDB_URL, REQUEST_TIMEOUT_S

WATER_NAMES = {"HOH", "WAT", "H2O", "DOD", "TIP3", "TIP", "SPC"}

ION_NAMES = {
    "NA", "CL", "K", "MG", "CA", "ZN", "FE", "FE2", "MN", "MN3", "CU", "CU1", "CO",
    "NI", "CD", "HG", "BR", "IOD", "I", "F", "BA", "SR", "CS", "RB", "LI", "AL",
    "AU", "AG", "PT", "HG", "PB", "SN", "SE4", "MO6", "WO4", "VO4", "SO4", "PO4",
    "BO4", "CO3", "NO3", "NH4", "NCO", "SCN", "OZN", "BEN",
}

# Small-molecule additives / buffers — never used as a pocket-defining ligand
BUFFER_NAMES = {
    "GOL", "EDO", "PG4", "PEG", "1PE", "PGE", "ACT", "ACE", "BME", "DMS", "MPD",
    "TRS", "EPE", "MES", "CIT", "FLC", "TLA", "CAD", "PE4", "IPA", "EtOH", "ETH",
    "ACN", "DXT", "BMA", "NAG", "NDG", "MAN", "FUC", "BGC", "GAL", "XYP", "SIA",
    "AME", "MRD", "UNL", "HOH", "MOH", "EOH", "C2E", "PE5", "PE8", "P6G", "1PG",
    "2PE", "1P6", "2P6", "P1P", "SEP", "SCN", "LMT", "OCT", "NU3", "MSE0",
}

# Modified amino acids treated as part of the protein (map to parent residue)
MODIFIED_AA = {
    "MSE": "MET", "SEC": "CYS", "PYL": "LYS", "HYP": "PRO", "CSO": "CYS",
    "CME": "CYS", "OCS": "CYS", "SEP": "SER", "TPO": "THR", "PTR": "TYR",
    "MLY": "LYS", "KCX": "LYS", "LLP": "LYS", "CAS": "CYS", "CSS": "CYS",
    "OAS": "SER", "MEN": "ASN", "ALY": "LYS", "M3L": "LYS", "CGU": "GLU",
}

STANDARD_AA = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE", "LEU",
    "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
}
PROTEIN_RESNAMES = STANDARD_AA | set(MODIFIED_AA)

PDB_ID_RE = re.compile(r"^[0-9A-Za-z]{4}$")


class PDBError(ValueError):
    """Raised when a structure cannot be fetched or parsed."""


@dataclass
class Atom:
    record: str
    serial: int
    name: str
    resname: str
    chain: str
    resseq: int
    icode: str
    x: float
    y: float
    z: float
    element: str
    occupancy: float = 1.0
    bfactor: float = 0.0

    @property
    def coord(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z], dtype=float)

    @property
    def label(self) -> str:
        icode = self.icode.strip()
        chain = f":{self.chain}" if self.chain.strip() else ""
        return f"{self.resname}{self.resseq}{icode}{chain}"


@dataclass
class LigandInstance:
    """One residue-level instance of a bound hetero compound."""

    resname: str
    chain: str
    resseq: int
    atoms: list[Atom] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.resname} {self.resseq}:{self.chain}" if self.chain.strip() else f"{self.resname} {self.resseq}"

    @property
    def coords(self) -> np.ndarray:
        return np.array([[a.x, a.y, a.z] for a in self.atoms], dtype=float)


@dataclass
class Pocket:
    """Binding pocket description in the coordinate frame of the source PDB."""

    center: np.ndarray
    radius: float
    atoms: list[Atom]
    residues: list[dict]
    source: str  # "ligand" | "abinitio"
    reference: str  # reference ligand label or "cavity detection"

    def feature_anchor_points(self) -> np.ndarray:
        """Return a point cloud used for ligand placement anchors."""
        return np.array([[a.x, a.y, a.z] for a in self.atoms], dtype=float)


# --------------------------------------------------------------------------- #
# Fetch + parse
# --------------------------------------------------------------------------- #

def fetch_pdb(pdb_id: str) -> str:
    pdb_id = pdb_id.strip().upper()
    if not PDB_ID_RE.match(pdb_id):
        raise PDBError(f"'{pdb_id}' is not a valid 4-character PDB ID.")
    url = RCSB_PDB_URL.format(pdb_id=pdb_id)
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT_S, headers={"User-Agent": "Q-Pharm/1.0"})
    except requests.RequestException as exc:
        raise PDBError(f"Could not reach RCSB ({exc.__class__.__name__}). "
                       f"Check connectivity or upload a PDB file instead.") from exc
    if resp.status_code == 404:
        raise PDBError(f"PDB entry {pdb_id} was not found on RCSB.")
    if resp.status_code != 200:
        raise PDBError(f"RCSB returned HTTP {resp.status_code} for {pdb_id}.")
    if len(resp.content) > MAX_PDB_BYTES:
        raise PDBError("Structure exceeds the 25 MB size limit.")
    return resp.text


def parse_pdb(text: str) -> list[Atom]:
    atoms: list[Atom] = []
    model_seen = False
    for line in text.splitlines():
        rec = line[:6].strip()
        if rec == "ENDMDL":
            # Keep only the first model for NMR entries
            break
        if rec == "MODEL":
            if model_seen:
                continue
            model_seen = True
        if rec not in ("ATOM", "HETATM"):
            continue
        if len(line) < 54:
            continue
        try:
            x = float(line[30:38]); y = float(line[38:46]); z = float(line[46:54])
        except ValueError:
            continue
        altloc = line[16]
        if altloc not in (" ", "A"):
            continue
        name = line[12:16].strip()
        resname = line[17:20].strip()
        element = (line[76:78].strip() or name.lstrip("0123456789")[0]).upper()
        if element == "H" or name.startswith("H") and element == "H":
            continue
        atoms.append(Atom(
            record=rec,
            serial=int(line[6:11] or 0),
            name=name,
            resname=resname,
            chain=line[21].strip() or "A",
            resseq=int(line[22:26] or 0),
            icode=line[26] or " ",
            x=x, y=y, z=z,
            element=element,
            occupancy=float(line[54:60] or 1.0),
            bfactor=float(line[60:66] or 0.0),
        ))
    if len(atoms) < 5:
        raise PDBError("Structure contains too few atoms to be a usable protein target.")
    return atoms


# --------------------------------------------------------------------------- #
# Classification helpers
# --------------------------------------------------------------------------- #

def protein_atoms(atoms: Iterable[Atom]) -> list[Atom]:
    out = []
    for a in atoms:
        if a.record == "ATOM" or a.resname in MODIFIED_AA:
            out.append(a)
    return out


def is_excluded_ligand_resname(resname: str) -> bool:
    return resname in WATER_NAMES or resname in ION_NAMES or resname in BUFFER_NAMES or resname in PROTEIN_RESNAMES


def detect_ligands(atoms: Iterable[Atom], min_heavy: int = 6, max_heavy: int = 70) -> list[LigandInstance]:
    """Group HETATM records into ligand instances suitable for pocket definition."""
    groups: dict[tuple, LigandInstance] = {}
    for a in atoms:
        if a.record != "HETATM" or a.element == "H":
            continue
        if is_excluded_ligand_resname(a.resname):
            continue
        key = (a.resname, a.chain, a.resseq)
        inst = groups.setdefault(key, LigandInstance(a.resname, a.chain, a.resseq))
        inst.atoms.append(a)
    valid = [g for g in groups.values() if min_heavy <= len(g.atoms) <= max_heavy]
    # Largest first — the main bound ligand is usually the biggest drug-like molecule
    valid.sort(key=lambda g: -len(g.atoms))
    return valid


# --------------------------------------------------------------------------- #
# Pocket definition
# --------------------------------------------------------------------------- #

def _residue_table(pocket_atoms: list[Atom]) -> list[dict]:
    seen: dict[tuple, dict] = {}
    for a in pocket_atoms:
        key = (a.resname, a.chain, a.resseq)
        if key not in seen:
            seen[key] = {"resname": a.resname, "chain": a.chain, "resseq": a.resseq, "label": a.label}
    return list(seen.values())


def pocket_from_ligand(lig: LigandInstance, prot: list[Atom], cutoff: float = 6.5) -> Pocket:
    lig_coords = lig.coords
    center = lig_coords.mean(axis=0)
    prot_coords = np.array([[a.x, a.y, a.z] for a in prot], dtype=float)
    tree = cKDTree(prot_coords)
    near = tree.query_ball_point(lig_coords, r=cutoff)
    idx = sorted({i for lst in near for i in lst})
    pocket_atoms = [prot[i] for i in idx]
    radius = float(np.max(np.linalg.norm(prot_coords[idx] - center, axis=1))) if idx else 10.0
    radius = float(min(max(radius, 6.0), 14.0))
    return Pocket(center=center, radius=radius, atoms=pocket_atoms,
                  residues=_residue_table(pocket_atoms), source="ligand",
                  reference=f"co-crystallized ligand {lig.label}")


def detect_pocket_abinitio(prot: list[Atom]) -> Pocket:
    """Detect the largest buried cavity using a grid + convex-hull interior test.

    This is a deliberately simple geometric detector (similar in spirit to
    LIGSITE): voxels further than 3 A from any protein atom but inside the
    protein's convex hull are candidate cavity points; connected clusters are
    ranked by volume and buriedness.
    """
    coords = np.array([[a.x, a.y, a.z] for a in prot], dtype=float)
    tree = cKDTree(coords)
    lo = coords.min(axis=0) - 2.0
    hi = coords.max(axis=0) + 2.0
    step = 1.4
    xs = np.arange(lo[0], hi[0] + step, step)
    ys = np.arange(lo[1], hi[1] + step, step)
    zs = np.arange(lo[2], hi[2] + step, step)
    grid = np.stack(np.meshgrid(xs, ys, zs, indexing="ij"), axis=-1).reshape(-1, 3)

    dist, _ = tree.query(grid, k=1, workers=-1)
    void = grid[(dist > 3.0) & (dist < 7.0)]
    if len(void) == 0:
        raise PDBError("No binding cavity could be detected in this structure.")

    try:
        hull = ConvexHull(coords)
        inside = np.all(void @ hull.equations[:, :3].T + hull.equations[:, 3] <= 0.6, axis=1)
        void = void[inside]
    except Exception:
        pass  # Degenerate hulls (flat structures) — keep all near-surface voids

    if len(void) < 30:
        raise PDBError("No buried cavity large enough to dock into was found.")

    # Flood-fill connected clusters on the voxel grid
    vox = set(map(tuple, np.round(void / step).astype(int)))
    seen: set[tuple] = set()
    clusters: list[list[tuple]] = []
    for v in list(vox):
        if v in seen:
            continue
        stack, cluster = [v], []
        seen.add(v)
        while stack:
            cur = stack.pop()
            cluster.append(cur)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        nxt = (cur[0] + dx, cur[1] + dy, cur[2] + dz)
                        if nxt in vox and nxt not in seen:
                            seen.add(nxt)
                            stack.append(nxt)
        clusters.append(cluster)

    clusters.sort(key=len, reverse=True)
    best = clusters[0]
    if len(best) < 25:
        raise PDBError("Cavities found are too small for drug-like ligands.")

    pts = np.array(best) * step
    center = pts.mean(axis=0)
    d = np.linalg.norm(pts - center, axis=1)
    radius = float(min(np.percentile(d, 95) + 2.0, 13.0))
    near = tree.query_ball_point(pts, r=radius + 2.0, workers=-1)
    idx = sorted({i for lst in near for i in lst})
    pocket_atoms = [prot[i] for i in idx]
    return Pocket(center=center, radius=radius, atoms=pocket_atoms,
                  residues=_residue_table(pocket_atoms), source="abinitio",
                  reference="geometric cavity detection")


def resolve_pocket(atoms: list[Atom], prefer_resname: str | None = None) -> tuple[Pocket, Optional[LigandInstance]]:
    """Pocket resolution strategy: preferred co-crystal ligand, then largest
    remaining ligand, then geometric cavity detection."""
    prot = protein_atoms(atoms)
    if len(prot) < 50:
        raise PDBError("No protein residues found in structure.")
    ligands = detect_ligands(atoms)
    chosen: Optional[LigandInstance] = None
    if prefer_resname:
        prefer = prefer_resname.strip().upper()
        chosen = next((l for l in ligands if l.resname.upper() == prefer), None)
    if chosen is None and ligands:
        chosen = ligands[0]
    if chosen is not None:
        return pocket_from_ligand(chosen, prot), chosen
    return detect_pocket_abinitio(prot), None
