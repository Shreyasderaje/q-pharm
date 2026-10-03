"""HTTP API surface for Q-Pharm."""

from __future__ import annotations

import csv
import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import qiskit
import rdkit
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from ..core import jobs
from ..core.config import APP_VERSION, DEFAULT_LIBRARY_SIZE, DEFAULT_QUANTUM_TOP
from ..core.drugs import library_stats, load_evidence, load_targets, search_drugs
from ..core.pdb import PDBError, parse_pdb, protein_atoms, resolve_pocket
from ..core.pharmacophore import receptor_features
from ..core.pipeline import run_screening

router = APIRouter(prefix="/api")
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="qpharm")


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #

class TargetSpec(BaseModel):
    mode: str = Field("pdb_id", description="pdb_id | upload")
    pdb_id: Optional[str] = None
    content: Optional[str] = None
    name: Optional[str] = None
    organism: Optional[str] = None
    disease: Optional[str] = None
    pocket_ligand: Optional[str] = None


class ScreeningParams(BaseModel):
    library_size: int = Field(DEFAULT_LIBRARY_SIZE, ge=5, le=150)
    quantum_enabled: bool = True
    quantum_top: int = Field(DEFAULT_QUANTUM_TOP, ge=0, le=25)
    placements: int = Field(300, ge=60, le=800)
    seed: int = 42


class JobRequest(BaseModel):
    target: TargetSpec
    params: ScreeningParams = ScreeningParams()


class InspectRequest(TargetSpec):
    pass


# --------------------------------------------------------------------------- #
# Meta endpoints
# --------------------------------------------------------------------------- #

@router.get("/health")
def health():
    return {
        "status": "ok",
        "version": APP_VERSION,
        "rdkit": rdkit.__version__,
        "qiskit": qiskit.__version__,
    }


@router.get("/stats")
def stats():
    s = library_stats()
    s["quantum"] = {"method": "VQE (L-BFGS-B + parameter-shift gradients)",
                    "qubits": 4, "backend": "statevector simulator"}
    return s


@router.get("/targets")
def curated_targets():
    return load_targets()


@router.get("/evidence")
def evidence():
    return load_evidence()


@router.get("/drugs")
def drugs(q: str = "", limit: int = 50, offset: int = 0):
    items, total = search_drugs(q, min(limit, 200), max(offset, 0))
    return {"total": total, "items": items}


# --------------------------------------------------------------------------- #
# Structure inspection (pocket preview before running a screen)
# --------------------------------------------------------------------------- #

@router.post("/targets/inspect")
def inspect_target(req: InspectRequest):
    """Pocket preview for a PDB ID before launching a screen."""
    try:
        from ..core.pdb import fetch_pdb

        pdb_id = (req.pdb_id or "").strip()
        if not pdb_id:
            raise PDBError("Provide a PDB ID.")
        text = fetch_pdb(pdb_id)
        atoms = parse_pdb(text)
        return _inspect_payload(atoms, f"RCSB PDB {pdb_id.upper()}")
    except PDBError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/targets/upload-inspect")
async def upload_inspect(file: UploadFile = File(...)):
    """Pocket preview for an uploaded PDB file."""
    try:
        content = (await file.read()).decode("utf-8", errors="replace")
        atoms = parse_pdb(content)
        return _inspect_payload(atoms, f"uploaded {file.filename or 'structure'}")
    except PDBError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _inspect_payload(atoms, source: str) -> dict:
    pocket, ligand = resolve_pocket(atoms)
    features = receptor_features(pocket.atoms)
    return {
        "source": source,
        "n_protein_atoms": len(protein_atoms(atoms)),
        "pocket": {
            "center": [round(v, 1) for v in pocket.center],
            "radius": round(pocket.radius, 1),
            "n_residues": len(pocket.residues),
            "residues": [r["label"] for r in pocket.residues],
            "source": pocket.source,
            "reference": pocket.reference,
            "features": features.counts(),
        },
    }


# --------------------------------------------------------------------------- #
# Screening jobs
# --------------------------------------------------------------------------- #

@router.post("/jobs")
def create_job(req: JobRequest):
    job = jobs.create_job()
    _pool.submit(run_screening, job.id, req.target.model_dump(), req.params.model_dump())
    return {"job_id": job.id}


@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job id.")
    return job.as_dict()


@router.get("/jobs/{job_id}/protein.pdb")
def job_protein(job_id: str):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job id.")
    path = Path(job.dir) / "protein.pdb"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Structure not ready yet.")
    return FileResponse(path, media_type="chemical/x-pdb", filename=f"{job_id}.pdb")


@router.get("/jobs/{job_id}/poses/{rank}.sdf")
def job_pose(job_id: str, rank: int):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job id.")
    path = Path(job.dir) / f"pose_{rank}.sdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Pose not available.")
    return FileResponse(path, media_type="chemical/x-mdl-molfile", filename=f"pose_{rank}.sdf")


@router.get("/jobs/{job_id}/export.csv")
def job_csv(job_id: str):
    job = jobs.get_job(job_id)
    if job is None or job.result is None:
        raise HTTPException(status_code=404, detail="Job not finished.")
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["rank", "drug", "drugbank_id", "drug_class", "indication",
                     "docking_score_kcal_mol", "composite", "docking_norm", "admet_score",
                     "quantum_delta_e_eh", "ml_druglikeness", "MW", "logP", "TPSA",
                     "HBD", "HBA", "rotB", "lipinski_violations", "pains_alerts"])
    for c in job.result["candidates"]:
        d, a, s, q = c["drug"], c["admet"] or {}, c["scores"], c["quantum"]
        writer.writerow([
            c["rank"], d["name"], d.get("drugbank_id") or "", d.get("drug_class") or "",
            d.get("indication") or "", c["docking"]["score"], s["composite"], s["docking"],
            (a or {}).get("score", ""), q.get("delta_e_hartree", "") if q.get("used") else "",
            s["ml"], (a or {}).get("mw", ""), (a or {}).get("logp", ""), (a or {}).get("tpsa", ""),
            (a or {}).get("hbd", ""), (a or {}).get("hba", ""), (a or {}).get("rotatable_bonds", ""),
            (a or {}).get("lipinski_violations", ""), ";".join((a or {}).get("pains_alerts", []) or []),
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=qpharm_{job_id}.csv"},
    )
