"""Runtime configuration for the Q-Pharm screening engine."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent  # backend/app
DATA_DIR = APP_DIR / "data"
REPO_ROOT = APP_DIR.parent.parent  # repo root
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

RCSB_PDB_URL = "https://files.rcsb.org/download/{pdb_id}.pdb"
REQUEST_TIMEOUT_S = 30
MAX_PDB_BYTES = 25 * 1024 * 1024

# Pipeline limits
DEFAULT_LIBRARY_SIZE = 60
MAX_LIBRARY_SIZE = 150
DEFAULT_QUANTUM_TOP = 8
MAX_QUANTUM_TOP = 25
MAX_PLACEMENTS = 800

# Job handling
JOBS_DIR = Path(
    os.environ.get("QPHARM_JOBS_DIR", Path(tempfile.gettempdir()) / "qpharm_jobs")
)
JOBS_DIR.mkdir(parents=True, exist_ok=True)
MAX_CONCURRENT_JOBS = 2

APP_VERSION = "1.0.0"
