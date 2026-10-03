"""Docking engine tests: ligand prep, pose scoring, placement."""

import numpy as np
import pytest

from app.core.docking import dock_ligand, prepare_ligand
from app.core.pharmacophore import receptor_features
from app.core.pdb import Atom, Pocket
from app.core.scoring import Receptor, score_pose


def _simple_receptor(extent: float) -> tuple[Receptor, Pocket]:
    """A receptor 'slab': two planes of atoms with donors/acceptors facing a
    dockable cavity in between.  Plane distance adapts to the ligand extent so
    the cavity is physically accessible (≈3.1 A clearance per side)."""
    plane = extent + 3.1
    atoms = []
    i = 0
    for x in np.arange(-7, 7.5, 3.0):
        for y in np.arange(-7, 7.5, 3.0):
            atoms.append(Atom("ATOM", i, "CA", "VAL", "A", i + 1, " ", x, y, plane + 0.8, "C"))
            i += 1
            atoms.append(Atom("ATOM", i, "O", "ASP", "A", i + 1, " ", x, y, plane, "O"))
            i += 1
            atoms.append(Atom("ATOM", i, "N", "LYS", "A", i + 1, " ", x, y, -plane, "N"))
            i += 1
            atoms.append(Atom("ATOM", i, "CA", "PHE", "A", i + 1, " ", x, y, -(plane + 0.8), "C"))
            i += 1
    feats = receptor_features(atoms)
    rec = Receptor(atoms, feats)
    pocket = Pocket(center=np.array([0.0, 0.0, 0.0]), radius=plane + 1.0, atoms=atoms,
                    residues=[], source="test", reference="test")
    return rec, pocket


@pytest.fixture(scope="module")
def receptor_pair():
    lig = prepare_ligand("CC(=O)Oc1ccccc1C(=O)O", max_confs=1, seed=42)
    model = lig.models[lig.conf_ids[0]]
    extent = float(np.abs(model.coords - model.coords.mean(axis=0)).max())
    return _simple_receptor(extent)


def test_prepare_ligand_aspirin():
    lig = prepare_ligand("CC(=O)Oc1ccccc1C(=O)O", max_confs=2)
    assert lig is not None
    assert lig.num_atoms >= 13          # 13 heavy atoms
    assert len(lig.conf_ids) >= 1
    assert lig.rotatable_bonds >= 2
    # donors/acceptors typed
    assert len(lig.models[lig.conf_ids[0]].features.acceptors) >= 3


def test_docking_produces_clash_free_pose(receptor_pair):
    rec, pocket = receptor_pair
    lig = prepare_ligand("CC(=O)Oc1ccccc1C(=O)O", max_confs=2)
    result = dock_ligand(lig, pocket, rec, placements=120, seed=3)
    assert np.isfinite(result.best_score.total)
    assert result.n_clash_free > 0
    # pose must not clash with receptor
    assert rec.min_distance(result.best_pose) >= 2.3
    # docking score should be negative (favourable) for a compatible pocket
    assert result.best_score.total < 0


def test_good_pose_scores_better_than_far_pose(receptor_pair):
    rec, pocket = receptor_pair
    lig = prepare_ligand("CC(=O)Oc1ccccc1C(=O)O", max_confs=2)
    result = dock_ligand(lig, pocket, rec, placements=200, seed=11)
    model = lig.models[result.conf_id]
    far = _place(model.coords, np.array([0.0, 0.0, 30.0]))
    s_far = score_pose(model, far, rec)
    # the optimized pose inside the cavity must beat a disjoint pose and be
    # net-favourable: contacts, H-bonds or electrostatics all contribute
    assert result.best_score.total < s_far.total
    assert result.best_score.total < 0


def _place(coords: np.ndarray, target: np.ndarray) -> np.ndarray:
    c = coords - coords.mean(axis=0)
    return c + target


def test_pose_sdf_export(receptor_pair):
    rec, pocket = receptor_pair
    lig = prepare_ligand("CC(=O)Oc1ccccc1C(=O)O", max_confs=1)
    result = dock_ligand(lig, pocket, rec, placements=80, seed=5)
    from app.core.docking import pose_to_sdf

    sdf = pose_to_sdf(lig, result.best_pose, result.conf_id)
    assert "$$$$" not in sdf  # MolToMolBlock emits a single block, no $$$$ terminator
    # coordinates of first heavy atom should appear in the block
    assert np.isfinite(result.best_pose[0]).all()
