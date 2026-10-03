"""ADMET + ML tests."""

import pytest
from rdkit import Chem


def _mol(smiles: str):
    return Chem.MolFromSmiles(smiles)


def test_aspirin_profile():
    from app.core.admet import compute_admet

    prof = compute_admet(_mol("CC(=O)Oc1ccccc1C(=O)O"))
    assert 170 < prof.mw < 190
    assert 1.0 < prof.logp < 2.2
    assert prof.hba == 3
    assert prof.hbd == 1
    assert prof.lipinski_violations == 0
    assert prof.veber_pass
    assert prof.grade() in ("A", "B")


def test_big_lipophilic_molecule_flagged():
    from app.core.admet import compute_admet

    # a fat, greasy molecule should violate Lipinski
    prof = compute_admet(_mol("CCCCCCCCCCCCCCCCCC(=O)OCCCCCCCCCCCCCCCCCC"))
    assert prof.lipinski_violations >= 1
    assert prof.mw > 500


def test_esol_reasonable():
    from app.core.admet import esol_log_s

    # aspirin: measured logS ~ -1.8 mol/L; ESOL should be within ~1 log unit
    v = esol_log_s(mw=180.16, logp=1.43, rotb=3, aromatic_proportion=0.46)
    assert -4 < v < -0.5


def test_ml_model_ranks_drug_above_chemical():
    from app.core.ml import load_model

    model = load_model()
    from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors

    def feats(mol):
        mw = Descriptors.MolWt(mol)
        logp = Crippen.MolLogP(mol)
        tpsa = rdMolDescriptors.CalcTPSA(mol)
        rotb = Lipinski.NumRotatableBonds(mol)
        arom = rdMolDescriptors.CalcNumAromaticRings(mol)
        heavy = mol.GetNumHeavyAtoms()
        fcsp3 = rdMolDescriptors.CalcFractionCSP3(mol)
        ap = sum(1 for a in mol.GetAtoms() if a.GetIsAromatic()) / max(heavy, 1)
        return {"mw": mw, "logp": logp, "tpsa": tpsa,
                "hbd": Lipinski.NumHDonors(mol), "hba": Lipinski.NumHAcceptors(mol),
                "rotb": rotb, "aromatic_rings": arom, "fraction_csp3": fcsp3,
                "heavy_atoms": heavy, "formal_charge": Chem.GetFormalCharge(mol),
                "esol_log_s": 0.16 - 0.63 * logp - 0.0062 * mw + 0.066 * rotb - 0.74 * ap}

    p_drug = model.predict_proba(feats(_mol("CC(=O)Oc1ccccc1C(=O)O")))
    p_chem = model.predict_proba(feats(_mol("c1ccccc1")))
    assert p_drug > p_chem
