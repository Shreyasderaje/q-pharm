"""Debug docking failures: prepare + dock each drug against the 6LU7 pocket."""
import sys
import traceback

sys.path.insert(0, "backend")

from app.core.docking import DockingError, dock_ligand, prepare_ligand
from app.core.pdb import fetch_pdb, parse_pdb, protein_atoms, resolve_pocket
from app.core.pharmacophore import receptor_features
from app.core.scoring import Receptor
from app.core.pipeline import _prefilter
from app.core.drugs import load_library

text = fetch_pdb("6LU7")
atoms = parse_pdb(text)
pocket, _ = resolve_pocket(atoms, prefer_resname="PJE")
feats = receptor_features(pocket.atoms)
rec = Receptor(pocket.atoms, feats)

selected = _prefilter(load_library(), feats.counts(), 60)
failed_names = ['Vancomycin', 'Daptomycin', 'Amphotericin B', 'Rifampicin', 'Docetaxel',
                'Paclitaxel', 'Doxorubicin', 'Clarithromycin', 'Remdesivir', 'Everolimus',
                'Cyclosporine', 'Sirolimus', 'Etoposide', 'Vincristine', 'Vinblastine',
                'Tacrolimus', 'Atazanavir', 'Telaprevir', 'Lopinavir', 'Baloxavir marboxil']
by_name = {d["name"]: d for d in selected}

for name in failed_names[:8]:
    drug = by_name.get(name)
    if drug is None:
        print(f"{name}: not in prefiltered set")
        continue
    try:
        lig = prepare_ligand(drug["smiles"], max_confs=0, seed=42)
        if lig is None:
            print(f"{name}: prepare_ligand returned None (RDKit embed failed)")
            continue
        heavy = sum(1 for a in lig.mol.GetAtoms() if a.GetSymbol() != "H")
        print(f"{name}: prepared ok (heavy={heavy}, confs={len(lig.conf_ids)}) ", end="")
        try:
            r = dock_ligand(lig, pocket, rec, placements=200, seed=42)
            print(f"-> docked score {r.best_score.total:.2f}, clash_free {r.n_clash_free}/{r.n_placements}")
        except DockingError as de:
            print(f"-> DockingError: {de}")
    except Exception:
        print(f"{name}: UNEXPECTED")
        traceback.print_exc()
