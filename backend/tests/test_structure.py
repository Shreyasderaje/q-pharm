"""Structural module tests: parsing, ligand detection, pocket detection, typing."""

import numpy as np
import pytest

from app.core.pdb import (
    Atom,
    LigandInstance,
    detect_ligands,
    detect_pocket_abinitio,
    parse_pdb,
    pocket_from_ligand,
    protein_atoms,
    resolve_pocket,
)

MINI_PDB = """\
HEADER    TEST STRUCTURE
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00 20.00           N
ATOM      2  CA  ALA A   1       1.458   0.000   0.000  1.00 20.00           C
ATOM      3  C   ALA A   1       2.009   1.420   0.000  1.00 20.00           C
ATOM      4  O   ALA A   1       1.201   2.348   0.000  1.00 20.00           O
ATOM      5  CB  ALA A   1       2.010  -0.900  -1.200  1.00 20.00           C
HETATM    6  O1  LIG A 800       2.000   2.000   3.500  1.00 20.00           O
HETATM    7  C1  LIG A 800       3.100   2.000   3.500  1.00 20.00           C
HETATM    8  C2  LIG A 800       3.650   3.300   3.500  1.00 20.00           C
HETATM    9  C3  LIG A 800       3.100   4.600   3.500  1.00 20.00           C
HETATM   10  C4  LIG A 800       2.000   4.600   3.500  1.00 20.00           C
HETATM   11  C5  LIG A 800       1.450   3.300   3.500  1.00 20.00           C
HETATM   12  O2  LIG A 800       2.000   2.000   4.700  1.00 20.00           O
HETATM   13  N1  LIG A 800       3.100   4.600   4.700  1.00 20.00           N
HETATM   14  C6  LIG A 800       4.200   4.000   5.000  1.00 20.00           C
END
"""


def test_parse_pdb_basic():
    atoms = parse_pdb(MINI_PDB)
    assert len(atoms) == 14
    lig = [a for a in atoms if a.record == "HETATM"]
    assert len(lig) == 9
    first = atoms[0]
    assert first.resname == "ALA" and first.chain == "A" and first.resseq == 1
    assert first.element == "N"


def test_detect_ligands_ignores_small_groups():
    atoms = parse_pdb(MINI_PDB)
    ligands = detect_ligands(atoms)
    assert len(ligands) == 1
    assert ligands[0].resname == "LIG"
    assert 6 <= len(ligands[0].atoms) <= 70


def test_pocket_from_ligand():
    atoms = parse_pdb(MINI_PDB)
    ligands = detect_ligands(atoms)
    prot = protein_atoms(atoms)
    pocket = pocket_from_ligand(ligands[0], prot)
    assert pocket.source == "ligand"
    assert len(pocket.atoms) >= 3   # ALA atoms within 6.5 A of the ligand
    center = pocket.center
    assert np.linalg.norm(center - np.array([2.73, 3.38, 3.93])) < 1.0


def _shell_protein(radius: float = 10.0, n_per_ring: int = 26) -> list[Atom]:
    """Synthetic hollow protein shell with a big cavity at the origin."""
    atoms = []
    serial = 1
    for phi in np.linspace(0, np.pi, n_per_ring):
        for theta in np.linspace(0, 2 * np.pi, n_per_ring * 2):
            x = radius * np.sin(phi) * np.cos(theta)
            y = radius * np.sin(phi) * np.sin(theta)
            z = radius * np.cos(phi)
            atoms.append(Atom("ATOM", serial, "CA", "ALA", "A", serial, " ",
                              x, y, z, "C"))
            serial += 1
    return atoms


def test_abinitio_pocket_finds_cavity():
    shell = _shell_protein()
    pocket = detect_pocket_abinitio(shell)
    assert pocket.source == "abinitio"
    # cavity center should be within a few A of the origin
    assert np.linalg.norm(pocket.center) < 5.0
    assert len(pocket.atoms) > 50


def test_receptor_feature_typing():
    from app.core.pharmacophore import receptor_features

    atoms = parse_pdb(MINI_PDB)
    prot = protein_atoms(atoms)
    feats = receptor_features(prot)
    # ALA backbone: 1 donor (N), 1 acceptor (O)
    assert feats.counts()["donors"] >= 1
    assert feats.counts()["acceptors"] >= 1
    assert feats.counts()["hydrophobes"] >= 2
