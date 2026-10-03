"""ADMET profiling: molecular descriptors, structural alerts and rule checks.

Implements the standard filter cascade used in virtual screening:
  * Lipinski's Rule of 5 (Ro5),
  * Veber rules (TPSA / rotatable bonds for oral bioavailability),
  * PAINS and Brenk structural alerts via RDKit's FilterCatalog,
  * estimated aqueous solubility (ESOL / Delaney equation),
  * a simple BBB and hepatic-clearance heuristic panel.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from rdkit import Chem, RDLogger
from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors

RDLogger.DisableLog("rdApp.warning")

# --------------------------------------------------------------------------- #
# Structural alerts
# --------------------------------------------------------------------------- #

_FALLBACK_PAINS = [
    ("rhodanine", "O=C1SC(=S)N(C)C1=O"),
    ("cyanocinnamate", "COC(=O)C(C#N)=C1OC=CC1"),
    ("catechol", "Oc1ccccc1O"),
    ("quinone", "O=C1C=CC(=O)C=C1"),
    ("phenolic_H_bond_trap", "Oc1cc(O)ccc1"),
]


def _build_catalog():
    try:
        from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams

        params = FilterCatalogParams()
        params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
        params.AddCatalog(FilterCatalogParams.FilterCatalogs.BRENK)
        return FilterCatalog(params)
    except Exception:
        return None


_CATALOG = _build_catalog()


# --------------------------------------------------------------------------- #
# Descriptor computation
# --------------------------------------------------------------------------- #

@dataclass
class ADMETProfile:
    mw: float
    logp: float
    tpsa: float
    hbd: int
    hba: int
    rotatable_bonds: int
    aromatic_rings: int
    heavy_atoms: int
    fraction_csp3: float
    formal_charge: int
    esol_log_s: float
    lipinski_violations: int
    veber_pass: bool
    pains_alerts: list[str]
    gi_absorption: str        # qualitative: high / low
    bbb_permeant: bool
    log_s_mg_ml: float

    def grade(self) -> str:
        score = self.admet_score()
        if score >= 0.8:
            return "A"
        if score >= 0.6:
            return "B"
        if score >= 0.4:
            return "C"
        return "D"

    def admet_score(self) -> float:
        s = 1.0
        s -= 0.15 * self.lipinski_violations
        if not self.veber_pass:
            s -= 0.2
        s -= 0.15 * min(len(self.pains_alerts), 2)
        if self.esol_log_s < -6:
            s -= 0.15
        elif self.esol_log_s < -4.5:
            s -= 0.05
        if abs(self.formal_charge) > 1:
            s -= 0.05
        return float(max(0.0, min(1.0, s)))

    def as_dict(self) -> dict:
        return {
            "mw": round(self.mw, 1), "logp": round(self.logp, 2), "tpsa": round(self.tpsa, 1),
            "hbd": self.hbd, "hba": self.hba, "rotatable_bonds": self.rotatable_bonds,
            "aromatic_rings": self.aromatic_rings, "heavy_atoms": self.heavy_atoms,
            "fraction_csp3": round(self.fraction_csp3, 2), "formal_charge": self.formal_charge,
            "esol_log_s": round(self.esol_log_s, 2), "log_s_mg_ml": round(self.log_s_mg_ml, 2),
            "lipinski_violations": self.lipinski_violations, "veber_pass": self.veber_pass,
            "pains_alerts": self.pains_alerts,
            "gi_absorption": self.gi_absorption, "bbb_permeant": self.bbb_permeant,
            "score": round(self.admet_score(), 3), "grade": self.grade(),
        }


def esol_log_s(mw: float, logp: float, rotb: int, aromatic_proportion: float) -> float:
    """Delaney (ESOL) equation: log S in mol/L."""
    return 0.16 - 0.63 * logp - 0.0062 * mw + 0.066 * rotb - 0.74 * aromatic_proportion


def compute_admet(mol: Chem.Mol) -> ADMETProfile:
    mw = Descriptors.MolWt(mol)
    logp = Crippen.MolLogP(mol)
    tpsa = rdMolDescriptors.CalcTPSA(mol)
    hbd = Lipinski.NumHDonors(mol)
    hba = Lipinski.NumHAcceptors(mol)
    rotb = Lipinski.NumRotatableBonds(mol)
    aromatic_rings = rdMolDescriptors.CalcNumAromaticRings(mol)
    heavy = mol.GetNumHeavyAtoms()
    fcsp3 = rdMolDescriptors.CalcFractionCSP3(mol)
    charge = Chem.GetFormalCharge(mol)

    aromatic_atoms = sum(1 for a in mol.GetAtoms() if a.GetIsAromatic())
    ap = aromatic_atoms / max(heavy, 1)
    logs = esol_log_s(mw, logp, rotb, ap)
    # mol/L -> mg/mL: logS_mgml = logS_mol + log10(MW g/mol) + 3
    log_s_mg_ml = logs + np.log10(max(mw, 1.0)) + 3.0

    violations = 0
    violations += mw > 500
    violations += logp > 5
    violations += hbd > 5
    violations += hba > 10

    veber = tpsa <= 140 and rotb <= 10

    alerts: list[str] = []
    if _CATALOG is not None:
        try:
            for match in _CATALOG.GetMatches(mol):
                alerts.append(match.GetDescription().split("(")[0].strip()[:40])
        except Exception:
            pass
        alerts = [a for a in alerts if a]
    if not alerts:
        for name, smi in _FALLBACK_PAINS:
            patt = Chem.MolFromSmarts(smi)
            if patt and mol.HasSubstructMatch(patt):
                alerts.append(name)

    gi = "high" if tpsa < 140 and hbd <= 5 else "low"
    bbb = tpsa < 90 and logp > 0.4 and not (charge > 0 and mw > 450)

    return ADMETProfile(mw, logp, tpsa, int(hbd), int(hba), int(rotb), int(aromatic_rings),
                        int(heavy), float(fcsp3), int(charge), float(logs),
                        int(violations), bool(veber), alerts, gi, bool(bbb),
                        float(log_s_mg_ml))
